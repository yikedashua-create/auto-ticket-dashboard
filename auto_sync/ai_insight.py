# -*- coding: utf-8 -*-
"""AI 解读层（v1，2026-09-03）：日报点评 / 周报异常解释 / 新根因处置描述

设计：AI 只"解释已算好的事实"，永不产数字。五道闸门全部代码化：
  闸门1 数字核对：输出中出现的每个数字必须在输入事实里存在，否则整条丢弃
  闸门2 事实喂给：异常由确定性规则发现（daily_report 的 attention / worsen），
          AI 只解释，不发现
  闸门3 结构化输出：JSON 校验失败重试一次，再失败静默返回 None（降级）
  闸门4 允许不知道：prompt 强制"数据不足 → 正常波动/原因不明"，禁止推测
  闸门5 灰度开关：zhipu_api.yaml 加 insight_enabled: true 才进推送；
          未启用时只写预览文件供人工审查（_workbench/_ai_insight_preview.txt）

缓存：auto_sync/data/ai_insight_cache.json（key = 功能+日期/原因），同一事实永不重调。
"""
import json
import logging
import re
import time
from pathlib import Path

import requests

from .ai_classifier import _read_creds, DEFAULT_BASE_URL

log = logging.getLogger("auto_sync.ai_insight")

CACHE_PATH = Path(__file__).resolve().parent / "data" / "ai_insight_cache.json"
PREVIEW_PATH = Path(r"E:\Work\Tools\_workbench\_ai_insight_preview.txt")

INSIGHT_SYSTEM_PROMPT = """你是机票自动出票系统的值班分析员，为业务团队写日报点评。

铁律（违反任何一条输出即作废）：
1. 只能引用"事实"里出现的数字，严禁出现事实之外的任何数字（含汉字数字如"三成/一半/几十"）
2. 只解释事实、给关注建议，严禁编造原因；事实不足以下结论时，必须写"属正常波动，建议继续观察"
3. 不引用外部信息（新闻/航司公告等），只用常识解释技术术语
4. 语气克制，像值班工程师交接班，不煽情不夸大

输出 JSON：{"comment": "80字以内的点评：一句结论 + 一句建议"}。只输出 JSON。"""

REASON_NOTE_SYSTEM_PROMPT = """你是机票出票系统的运维专家。给定一条失败原因，用一句话说明这类失败的常见成因和处置方向。

铁律：不知道就说"成因待查，建议人工核实"，严禁编造；30 字以内；不出现任何数字。

输出 JSON：{"note": "..."}。只输出 JSON。"""

ANOMALY_SYSTEM_PROMPT = """你是机票出票系统的运维专家。给定一个失败环节周环比恶化的事实和该环节的原因变化，写一句归因假设和排查建议。

铁律：只能引用事实中的数字；假设必须说"疑似/可能"，不确定就写"原因待查"；50 字以内。

输出 JSON：{"explain": "..."}。只输出 JSON。"""

# 汉字数字/模糊量词黑名单（闸门1 的补充）
_CN_NUM = re.compile(r"[一二两三四五六七八九十百千万亿]+(成|倍|个|单|条)|几十|若干")


def insight_enabled() -> bool:
    """闸门5：灰度开关（zhipu_api.yaml 的 insight_enabled: true 才进推送）"""
    return _read_creds().get("insight_enabled", "").lower() in ("true", "1", "yes")


def _chat(system: str, user: str, timeout: int = 120) -> str:
    creds = _read_creds()
    if not creds.get("api_key"):
        raise RuntimeError("未配置 api_key")
    url = creds.get("base_url", DEFAULT_BASE_URL).rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {creds['api_key']}", "Content-Type": "application/json"}
    body = {
        "model": creds.get("model", "glm-4-flash"),
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    return re.sub(r"^```(json)?\s*|\s*```$", "", content.strip())


def _verify_numbers(text: str, facts_str: str) -> bool:
    """闸门1：text 里每个数字（含百分比）必须能在 facts_str 里找到相同串。"""
    if _CN_NUM.search(text):
        return False
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    return all(n in facts_str for n in nums)


def _gen_cached(key: str, system: str, user: str, facts_str: str,
                out_field: str, max_len: int) -> str:
    """带缓存的受控生成：失败/校验不过 → 返回 ''（调用方按无 AI 处理）。"""
    try:
        cache = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        cache = {}
    if key in cache:
        return cache[key]

    creds = _read_creds()
    if not creds.get("api_key"):
        return ""
    for attempt in range(2):
        try:
            raw = _chat(system, user)
            data = json.loads(raw)
            text = str(data.get(out_field, "")).strip()
            if not text or len(text) > max_len:
                raise ValueError(f"字段缺失或超长({len(text)}字)")
            if not _verify_numbers(text, facts_str):
                raise ValueError("数字核对未通过（出现事实之外的数字）")
            cache[key] = text
            try:
                CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
                CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
            except Exception as e:
                log.warning(f"AI 解读缓存写盘失败: {e}")
            _preview_log(key, text)
            return text
        except Exception as e:
            if attempt == 0:
                time.sleep(2)
                continue
            log.warning(f"AI 解读生成失败（已降级为不显示）key={key[:40]}: {type(e).__name__}: {str(e)[:100]}")
            _preview_log(key, f"[已丢弃: {str(e)[:60]}]")
            return ""
    return ""


def _preview_log(key: str, text: str):
    """闸门5：无论是否启用，所有 AI 产出写预览文件供人工审查。"""
    try:
        PREVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(PREVIEW_PATH, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {key}\n  → {text}\n\n")
    except Exception:
        pass


# ---------------- 三个公开能力 ----------------

def daily_comment(brief: dict) -> str:
    """① 日报 AI 点评（80 字内：一句结论 + 一句建议）"""
    facts = {
        "日期": brief["date"], "昨日": brief.get("yesterday_date"),
        "今日自动成功率": brief["succ"], "昨日成功率": brief["succ_prev"],
        "环比pp": round(brief["succ_delta"], 1) if brief.get("succ_delta") is not None else None,
        "总单": brief["total"], "A": brief["A"], "B失败人工介入": brief["B"],
        "C政策转人工": brief["C"], "D处理中": brief["D"],
        "值得注意": [{"类型": it["kind"], "原因": it["reason"], "单数": it["count"]} for it in brief.get("attention", [])],
        "本月累计成功率": brief.get("month_rate"),
    }
    facts_str = json.dumps(facts, ensure_ascii=False)
    return _gen_cached(
        f"daily:{brief['date']}",
        INSIGHT_SYSTEM_PROMPT,
        f"事实：{facts_str}",
        facts_str, "comment", 90,
    )


def reason_note(reason: str) -> str:
    """③ 新根因处置描述（30 字内成因+处置）"""
    return _gen_cached(
        f"note:{reason[:60]}",
        REASON_NOTE_SYSTEM_PROMPT,
        f"失败原因：{reason}",
        reason, "note", 40,
    )


def anomaly_explain(family: str, cur: int, prev: int, top_reasons: list) -> str:
    """② 周报恶化环节的归因假设（50 字内，必须带"疑似/可能"或"待查"）"""
    facts = {"环节": family, "本周单数": cur, "上周单数": prev,
             "该环节原因变化": top_reasons[:5]}
    facts_str = json.dumps(facts, ensure_ascii=False)
    text = _gen_cached(
        f"anomaly:{family}:{cur}:{prev}",
        ANOMALY_SYSTEM_PROMPT,
        f"事实：{facts_str}",
        facts_str, "explain", 60,
    )
    if text and not re.search(r"疑似|可能|待查|或与|估计", text):
        return ""  # 闸门2/4 的补充：假设句必须含不确定措辞
    return text
