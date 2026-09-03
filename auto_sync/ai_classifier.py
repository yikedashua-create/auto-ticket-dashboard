# -*- coding: utf-8 -*-
"""AI 语义归因层（v1，2026-09-03）

背景：gen_dashboard_data.py 的 REASON_FAMILY_RULES 是正则关键词表，没命中的
失败原因全部兜底进"其他环节-兜底"（历史占比可观），且规则表要人工维护。

方案：规则未命中的 unique 原因交给智谱 GLM 语义归类到 9 大环节 + 生成子分类。
设计铁律：
  1. 全量缓存（auto_sync/data/ai_classify_cache.json）：同一原因永不重复调用，
     API 成本趋近于零，且缓存后离线可跑
  2. 失败降级：无 key / 网络断 / API 错 → 返回空结果并告警日志，
     gen 继续走"其他环节-兜底"——AI 层永远不会阻塞数据管道
  3. 9 族结构不变：AI 只在 9 大环节内归类（子分类带 AI: 前缀标识），
     与前端 STAGE_ORDER / 历史数据完全兼容

凭据：E:\\Work\\Documents\\凭据\\zhipu_api.yaml（单行 key: value 格式）
    api_key: xxxxxxxx        （必填，open.bigmodel.cn 的 API key）
    model: glm-4-flash       （可选，默认免费档）
    base_url: https://open.bigmodel.cn/api/paas/v4   （可选）
"""
import json
import logging
import os
import re
import time
from pathlib import Path

import requests

log = logging.getLogger("auto_sync.ai_classifier")

CRED_PATH = Path(r"E:\Work\Documents\凭据\zhipu_api.yaml")
CACHE_PATH = Path(__file__).resolve().parent / "data" / "ai_classify_cache.json"
DEFAULT_MODEL = "glm-4-flash"
DEFAULT_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"

# 9 大环节（与 gen_dashboard_data.get_stage_only / 前端 STAGE_ORDER 完全一致，勿改）
VALID_STAGES = ["预定环节", "支付环节", "取票环节", "验真环节",
                "回填环节", "平台环节", "系统环节", "人工环节", "其他环节"]

SYSTEM_PROMPT = """你是机票自动出票系统的失败原因归因专家。把每条失败原因归类到下面 9 个环节之一，并给一个简短子分类：

环节定义：
- 预定环节：下单/询价/验价/舱位/价格规则/证件信息等预订链路问题
- 支付环节：支付/开卡/虚拟卡/订单校验等支付链路问题
- 取票环节：出票/取票/票号/航司出票接口问题
- 验真环节：客票验真/行程验证问题
- 回填环节：出票后回填原平台失败
- 平台环节：原平台状态监测/审核/平台侧操作
- 系统环节：超时/接口异常/内部错误/token/维护等技术故障
- 人工环节：需要或已被人工介入处理（辅营/重复/取消/转人工）
- 其他环节：无法判断

输出 JSON：{"results": [{"reason": "原样返回", "stage": "环节名", "sub": "不超过12字的子分类"}]}
只输出 JSON。"""


def _read_creds() -> dict:
    """读 zhipu_api.yaml（单行 key: value 格式）"""
    if not CRED_PATH.exists():
        return {}
    creds = {}
    for line in CRED_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        k, v = line.split(":", 1)
        creds[k.strip()] = v.strip().strip('"').strip("'")
    return creds


def _load_cache() -> dict:
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception as e:
        log.warning(f"AI 归因缓存写盘失败（不影响主流程）: {e}")


def _validate(result: dict) -> bool:
    return (isinstance(result, dict)
            and result.get("stage") in VALID_STAGES
            and isinstance(result.get("sub"), str) and result["sub"])


def _call_api(reasons: list, creds: dict, timeout: int = 40) -> dict:
    """调智谱 chat completions，返回 {reason: {"stage","sub"}}。异常向上抛。"""
    url = creds.get("base_url", DEFAULT_BASE_URL).rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {creds['api_key']}", "Content-Type": "application/json"}
    body = {
        "model": creds.get("model", DEFAULT_MODEL),
        "temperature": 0.1,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"失败原因列表": reasons}, ensure_ascii=False)},
        ],
    }
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    # 容错：模型可能带 ```json 包裹
    content = re.sub(r"^```(json)?\s*|\s*```$", "", content.strip())
    data = json.loads(content)
    out = {}
    for item in data.get("results", []):
        reason = item.get("reason")
        if reason in reasons and _validate(item):
            out[reason] = {"stage": item["stage"], "sub": item["sub"][:16]}
    return out


def classify_unmatched(reasons: list, batch_size: int = 20, max_batches: int = 30) -> dict:
    """把规则未命中的 unique 原因交给 AI 归类（带缓存 + 降级）。

    Args:
        reasons: unique 的未匹配原因列表
    Returns:
        {reason: family_str}，family 形如 "预定环节-AI:下单金额获取失败"。
        无 key / 全部失败时返回 {}，调用方继续走原兜底。
    """
    reasons = [r for r in dict.fromkeys(reasons) if r and r != "(无)"]
    if not reasons:
        return {}

    cache = _load_cache()
    pending = [r for r in reasons if r not in cache]
    already = {r: cache[r] for r in reasons if r in cache}
    if pending:
        creds = _read_creds()
        if not creds.get("api_key"):
            log.warning(f"AI 归因跳过：未配置 api_key（{CRED_PATH}）。{len(pending)} 条原因继续走规则兜底")
            return _to_family_map(already)

        ok, fail = 0, 0
        batches = [pending[i:i + batch_size] for i in range(0, len(pending), batch_size)][:max_batches]
        for bi, batch in enumerate(batches):
            for attempt in range(2):
                try:
                    result = _call_api(batch, creds)
                    for reason, item in result.items():
                        cache[reason] = item
                    ok += len(result)
                    break
                except Exception as e:
                    if attempt == 0:
                        time.sleep(2)
                        continue
                    fail += len(batch)
                    log.warning(f"AI 归因第 {bi + 1} 批失败（已重试）: {type(e).__name__}: {str(e)[:120]}")
        _save_cache(cache)
        log.info(f"AI 归因完成：新增 {ok} 条，失败 {fail} 条，缓存命中 {len(already)} 条")
    else:
        log.info(f"AI 归因：{len(already)} 条全部命中缓存，零 API 调用")

    merged = dict(already)
    merged.update({r: cache[r] for r in pending if r in cache})
    return _to_family_map(merged)


def _to_family_map(cache_items: dict) -> dict:
    """{reason: {stage, sub}} → {reason: 'stage-AI:sub'}（与 get_stage_only 兼容）"""
    return {r: f"{item['stage']}-AI:{item['sub']}" for r, item in cache_items.items()}


def suggest_rules(limit: int = 30) -> list:
    """从缓存里产出'建议采纳为规则'清单（按历史出现价值无法在此判断，按缓存顺序）。

    供 `python -m auto_sync ai-rules` 人工审批用：
    每条输出可直接粘贴进 gen_dashboard_data.py REASON_FAMILY_RULES 的正则规则。
    """
    cache = _load_cache()
    items = list(cache.items())[:limit]
    out = []
    for reason, item in items:
        # 取原因里最长的一段作为正则锚点（简单启发式；人工审批时可改）
        anchor = max(re.findall(r"[\u4e00-\u9fa5A-Za-z0-9]{4,}", reason), key=len, default=reason[:8])
        out.append({
            "reason": reason,
            "ai_family": f"{item['stage']}-AI:{item['sub']}",
            "suggested_rule": f'(r"{re.escape(anchor)}", "{item["stage"]}-{item["sub"]}"),',
        })
    return out
