# -*- coding: utf-8 -*-
"""
daily_report.py — 失败订单归因分析日报/周报/月报生成器

数据源: dashboard_data.json (由 gen_dashboard_data.py 生成)

报告结构（按用户模板 2026-08-11 拍板）：
  1. 标题：失败订单归因分析日报 · YYYY-MM-DD
  2. 【路径分布】4 路径（A 全自动成功 / B 全自动失败=已出票+有人锁 / C 订单转人工 / D 订单处理中）
                 + 总订单 + 自动成功率
  3. 【失败分布】9 大环节（预定/支付/取票/验真/回填/平台/系统/人工/其他）
                 每个环节：环节名（数量）+ Top 3 错误（每条带 1 个案例订单号）
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_PATH = Path(r"E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard\dashboard_data.json")

# 9 大环节固定顺序（用户拍板 2026-08-11）
STAGE_ORDER = ["预定", "支付", "取票", "验真", "回填", "平台", "系统", "人工", "其他"]

# 9 大环节的 family 关键词映射
STAGE_FAMILY_MAP = {
    "预定": "预定环节",
    "支付": "支付环节",
    "取票": "取票环节",
    "验真": "验真环节",
    "回填": "回填环节",
    "平台": "平台环节",
    "系统": "系统环节",
    "人工": "人工环节",
    "其他": "其他环节",
}


# --------------------------------------------------------------------------- #
# 加载数据
# --------------------------------------------------------------------------- #
def _load_data() -> Dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- #
# 4 路径分布
# --------------------------------------------------------------------------- #
def build_path_distribution(daily: Dict) -> Dict:
    """4 路径分布（A/B/C/D + 总订单 + 自动成功率）"""
    A = daily.get("A", 0)
    B = daily.get("B", 0)
    C = daily.get("C", 0)
    D = daily.get("D", 0)
    total = daily.get("total", A + B + C + D)
    auto_succ_rate = daily.get("auto_succ_rate", 0)
    A_ratio = daily.get("A_ratio", A / total * 100 if total else 0)
    B_ratio = daily.get("B_ratio", B / total * 100 if total else 0)
    C_ratio = daily.get("C_ratio", C / total * 100 if total else 0)
    D_ratio = daily.get("D_ratio", D / total * 100 if total else 0)
    return {
        "title": "【路径分布】",
        "total": total,
        "auto_succ_rate": auto_succ_rate,
        "A": A, "B": B, "C": C, "D": D,
        "A_ratio": A_ratio, "B_ratio": B_ratio, "C_ratio": C_ratio, "D_ratio": D_ratio,
    }


# --------------------------------------------------------------------------- #
# 9 大环节 × Top 3 错误
# --------------------------------------------------------------------------- #
def build_stage_distribution(date: str, full: Dict, max_top_n: int = 5) -> Dict:
    """9 大环节分布（按 family 聚合 B+D，按天切）

    数据源: daily_detail[date].fail_families_B/D + fail_reasons_B/D + fail_drill_B/D
    9 大环节 = 预定/支付/取票/验真/回填/平台/系统/人工/其他

    每个环节：
      - 环节名 + 数量（B+D 当天）
      - 1-5 个 Top 错误（按 count 降序，最多 5）
      - 每条 reason 带：案例订单号 + 平台 + 航司（渠道待补）
    """
    # 取 daily_detail[date] 里的按天数据
    dd = full.get("daily_detail", {})
    day_data = dd.get(date, {})
    if not day_data:
        logger.warning(f"daily_detail 找不到 {date}，回退到全月 fail_reasons")
        # 降级：fallback 到顶层 fail_reasons（当月累计）
        reasons_B = full.get("fail_reasons_B", [])
        reasons_D = full.get("fail_reasons_D", [])
        day_data = {
            "fail_reasons_B": reasons_B,
            "fail_reasons_D": reasons_D,
            "fail_families_B": full.get("fail_families_B", []),
            "fail_families_D": full.get("fail_families_D", []),
        }

    # 合并 B + D 的 reason
    all_reasons = []
    for r in day_data.get("fail_reasons_B", []):
        all_reasons.append({**r, "_source": "B"})
    for r in day_data.get("fail_reasons_D", []):
        all_reasons.append({**r, "_source": "D"})

    # 建 fail_reasons_B/D 索引：reason_full → {platform_top, airline_top, channel_top}
    # 2026-08-11 v8.x: gen 已给 fail_reasons_B/D 每个 reason 附加全量 platform/airline/channel
    drill_index = {}
    for r in (day_data.get("fail_reasons_B", []) or []):
        key = r.get("full", "") or r.get("reason", "")
        platform_top = (r.get("platform_dist", [{}])[0] or {}).get("name", "") if r.get("platform_dist") else ""
        airline_top = (r.get("airline_dist", [{}])[0] or {}).get("code", "") if r.get("airline_dist") else ""
        channel_top = (r.get("channel_dist", [{}])[0] or {}).get("name", "") if r.get("channel_dist") else ""
        drill_index[key] = {"platform": platform_top, "airline": airline_top, "channel": channel_top}
    for r in (day_data.get("fail_reasons_D", []) or []):
        key = r.get("full", "") or r.get("reason", "")
        platform_top = (r.get("platform_dist", [{}])[0] or {}).get("name", "") if r.get("platform_dist") else ""
        airline_top = (r.get("airline_dist", [{}])[0] or {}).get("code", "") if r.get("airline_dist") else ""
        channel_top = (r.get("channel_dist", [{}])[0] or {}).get("name", "") if r.get("channel_dist") else ""
        drill_index[key] = {"platform": platform_top, "airline": airline_top, "channel": channel_top}

    # 按 9 大环节分组
    stage_groups = {stage: [] for stage in STAGE_ORDER}
    unmatched = []
    for r in all_reasons:
        family = r.get("family", "")
        matched = False
        for stage, kw in STAGE_FAMILY_MAP.items():
            if kw in family:
                stage_groups[stage].append(r)
                matched = True
                break
        if not matched:
            unmatched.append(r)
    if unmatched:
        stage_groups["其他"].extend(unmatched)

    # 构造最终结构（按 9 大环节分桶，total 留给外部排序）
    sections = []
    for stage in STAGE_ORDER:
        reasons = stage_groups[stage]
        # 排序：count 降序
        reasons_sorted = sorted(reasons, key=lambda x: -x.get("count", 0))
        # 1-5 动态：实际 reason 数量 ≤ max_top_n 时取全部，否则取前 max_top_n
        # 至少 1 个（避免显示空环节）
        n = min(len(reasons_sorted), max_top_n)
        top_reasons = reasons_sorted[:max(1, n)]
        total_count = sum(r.get("count", 0) for r in reasons)
        sections.append({
            "stage": stage,
            "total": total_count,
            "top_reasons": [
                {
                    "reason": tr.get("reason", ""),
                    "count": tr.get("count", 0),
                    "sample_order": (tr.get("orders") or [None])[0],
                    "sample_platform": drill_index.get(tr.get("reason", ""), {}).get("platform", ""),
                    "sample_airline": drill_index.get(tr.get("reason", ""), {}).get("airline", ""),
                    "sample_channel": drill_index.get(tr.get("reason", ""), {}).get("channel", ""),
                }
                for tr in top_reasons
            ],
        })

    return {
        "title": "【失败分布】",
        "sections": sections,
    }


# --------------------------------------------------------------------------- #
# 主入口：build_report
# --------------------------------------------------------------------------- #
def build_report(date: str) -> Dict:
    """构造完整报告（按用户模板）"""
    full = _load_data()
    daily_list = full.get("daily", [])
    daily = next((d for d in daily_list if d.get("date") == date), None)
    if not daily:
        daily = max(daily_list, key=lambda x: x.get("date", ""))
        date = daily.get("date", "")
        logger.warning(f"找不到 {date}，用最近一天 {date}")

    return {
        "date": date,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "path_dist": build_path_distribution(daily),
        "stage_dist": build_stage_distribution(date, full, max_top_n=5),
    }


# --------------------------------------------------------------------------- #
# 渲染：Markdown（钉钉格式，模拟表格）
# --------------------------------------------------------------------------- #
def render_markdown(report: Dict) -> str:
    """按用户模板渲染 markdown"""
    pd = report["path_dist"]
    sd = report["stage_dist"]
    date = report["date"]

    lines = []
    lines.append(f"# 自动化数据日报 · {date}")
    lines.append("")
    lines.append(f"> 生成时间：{report['generated_at']}  ·  数据源：dashboard_data.json")
    lines.append("")

    # ---- 路径分布 ----
    lines.append(f"## {pd['title']}")
    lines.append("")
    lines.append(f"总订单 **{pd['total']}** 单  自动成功率 **{pd['auto_succ_rate']:.2f}%**")
    lines.append("")
    lines.append(f"A 全自动成功 **{pd['A']}** 单 (**{pd['A_ratio']:.2f}%**)")
    lines.append(f"B 全自动失败 **{pd['B']}** 单 (**{pd['B_ratio']:.2f}%**)")
    lines.append(f"C 订单转人工 **{pd['C']}** 单 (**{pd['C_ratio']:.2f}%**)")
    lines.append(f"D 订单处理中 **{pd['D']}** 单 (**{pd['D_ratio']:.2f}%**)")
    lines.append("")

    # ---- 失败分布（9 大环节，按 total 数量降序）----
    lines.append(f"## {sd['title']}")
    lines.append("")

    # C 改动：按 total 数量降序
    sorted_sections = sorted(sd["sections"], key=lambda x: -x["total"])

    for i, sec in enumerate(sorted_sections, 1):
        stage = sec["stage"]
        total = sec["total"]
        top = sec["top_reasons"]

        lines.append(f"### {i}.{stage}环节（{total}）")
        lines.append("")

        if not top:
            lines.append("（无数据）")
            lines.append("")
            continue

        for j, r in enumerate(top, 1):
            num_cn = ["①", "②", "③", "④", "⑤"][j - 1] if j <= 5 else f"{j}."
            reason = r["reason"]
            count = r["count"]
            sample = r["sample_order"] or "—"
            # 2026-08-12 拆 2 行：第 1 行 reason + 案例订单号，第 2 行 平台·航司·渠道
            # 第 1 行
            lines.append(f"{num_cn}{reason}（{count}） 例：{sample}")
            # 第 2 行：平台·航司·渠道（缩进 2 个全角空格对齐 ① 之后）
            platform = r.get("sample_platform", "")
            airline = r.get("sample_airline", "")
            channel = r.get("sample_channel", "")
            extras = []
            if platform:
                extras.append(f"平台：{platform}")
            if airline:
                extras.append(f"航司：{airline}")
            if channel:
                extras.append(f"渠道：{channel}")
            if extras:
                lines.append(f"　　{'　'.join(extras)}")
        lines.append("")

    # 2026-08-11: 钉钉 markdown 单换行 \n 被忽略（当空格），必须 \n\n 才换段
    # 把每行末尾再加一个 \n，确保所有行都成段
    output = "\n\n".join(lines)  # 双换行 = 段落
    return output


# --------------------------------------------------------------------------- #
# 渲染：钉钉 ActionCard
# --------------------------------------------------------------------------- #
def render_dingtalk_actioncard(report: Dict) -> Dict:
    """钉钉 ActionCard（不要 dashboard 链接，按用户要求）"""
    md = render_markdown(report)
    return {
        "title": f"📊 失败订单归因分析日报 · {report['date']}",
        "text": md,
    }


# --------------------------------------------------------------------------- #
# 渲染：飞书 interactive card（含真表格 + 折叠面板）
# --------------------------------------------------------------------------- #
def render_feishu_card(report: Dict) -> Dict:
    """飞书 interactive card v3（纯 div 降级版）

    2026-08-12：飞书自定义机器人 webhook 不支持 collapsible / table / fields / column / column_set
    只支持 div / markdown / hr / img / actions / button。
    全部用 div + markdown 重组，飞书 markdown 单换行保留（不像钉钉要 \n\n）。

    元素组成：
      - Header: 标题
      - 报告期 + 生成时间
      - 4 路径（单 div，markdown 列出）
      - 9 大环节（每个 div 含 markdown 标题 + reason 列表）
    """
    pd = report["path_dist"]
    sd = report["stage_dist"]
    date = report["date"]

    elements = []

    # 1. 报告期 + 生成时间
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**报告期**：{date}  \n"
                f"**生成时间**：{report['generated_at']}  \n"
                f"**数据源**：dashboard_data.json"
            ),
        },
    })
    elements.append({"tag": "hr"})

    # 2. 4 路径（单 div + markdown 列表）
    path_md_lines = [
        "**📊 4 路径分布**",
        f"- **总订单**：{pd['total']} 单",
        f"- **自动成功率**：{pd['auto_succ_rate']:.2f}%",
        f"- ✅ A 全自动成功：**{pd['A']}** 单 ({pd['A_ratio']:.2f}%)",
        f"- 🛟 B 全自动失败：**{pd['B']}** 单 ({pd['B_ratio']:.2f}%)",
        f"- 🚧 C 订单转人工：**{pd['C']}** 单 ({pd['C_ratio']:.2f}%)",
        f"- ⚠️ D 订单处理中：**{pd['D']}** 单 ({pd['D_ratio']:.2f}%)",
    ]
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "\n".join(path_md_lines)},
    })
    elements.append({"tag": "hr"})

    # 3. 9 大环节（每个 div，markdown 包含 reason 列表）
    sorted_sections = sorted(sd["sections"], key=lambda x: -x["total"])
    for i, sec in enumerate(sorted_sections, 1):
        stage = sec["stage"]
        total = sec["total"]
        top = sec["top_reasons"]

        lines = [f"**{i}.{stage}环节**（{total} 单）", ""]
        if not top:
            lines.append("（无数据）")
        else:
            for j, r in enumerate(top, 1):
                num = ["①", "②", "③", "④", "⑤"][j - 1] if j <= 5 else f"{j}."
                reason = r["reason"]
                count = r["count"]
                sample = r.get("sample_order") or "—"
                platform = r.get("sample_platform", "")
                airline = r.get("sample_airline", "")
                channel = r.get("sample_channel", "")
                extras = []
                if platform:
                    extras.append(f"平台:{platform}")
                if airline:
                    extras.append(f"航司:{airline}")
                if channel:
                    extras.append(f"渠道:{channel}")
                info_str = "  ".join(extras) if extras else ""
                line = f"- **{num}{reason}（{count}）** 例:`{sample}`"
                if info_str:
                    line += f"  \n　　{info_str}"
                lines.append(line)

        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(lines)},
        })

    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"📊 自动化数据日报 · {date}"},
        },
        "elements": elements,
    }


# --------------------------------------------------------------------------- #
# 包装：构造可直接 push 的 report
# --------------------------------------------------------------------------- #
def build_pushable_report(date: str) -> Dict:
    """构造可直接传给 notify.send() 的报告

    同时含钉钉 (markdown) + 飞书 (interactive card) 两种格式
    推送时由 cfg.channel 选哪种
    """
    r = build_report(date)
    return {
        "title": f"📊 自动化数据日报 · {r['date']}",
        "markdown": render_markdown(r),
        "dingtalk_card": render_dingtalk_actioncard(r),
        "feishu_card": render_feishu_card(r),
        "_raw": r,
    }
