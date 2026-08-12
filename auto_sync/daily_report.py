# -*- coding: utf-8 -*-
"""
daily_report.py — 失败订单归因分析日报/周报/月报生成器（v8 模板）

数据源: dashboard_data.json (由 gen_dashboard_data.py 生成)

v8 模板结构（2026-08-12 拍板）：
  1. 标题：自动化数据日报 · YYYY-MM-DD
  2. 【路径分布】4 路径（A 全自动成功 / B 全自动失败 / C 订单转人工 / D 订单处理中）
  3. 【失败分布】9 大环节（按 total 降序）
     每个环节：i.stage:total单(pct%) arrowdelta%（环比前一天）
     每个 reason：num reason（today/prev）arrowdelta%
                 例:`order1`、`order2`、`order3`（一行 3 单）
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DATA_PATH = Path(r"E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard\dashboard_data.json")

# 9 大环节固定顺序（用户拍板 2026-08-11）
STAGE_ORDER = ["预定", "支付", "取票", "验真", "回填", "平台", "系统", "人工", "其他"]
STAGE_FAMILY_MAP = {
    "预定": "预定环节", "支付": "支付环节", "取票": "取票环节",
    "验真": "验真环节", "回填": "回填环节", "平台": "平台环节",
    "系统": "系统环节", "人工": "人工环节", "其他": "其他环节",
}


def _load_data() -> Dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _delta_arrow(delta: float) -> str:
    if delta > 0.5:
        return "⬆️"
    elif delta < -0.5:
        return "⬇️"
    return "—"


def _merge_9_stages(day_data: Dict) -> Dict[str, int]:
    """daily_detail[date] 的 fail_families_B + fail_families_D 合并"""
    stage_total = defaultdict(int)
    for r in day_data.get("fail_families_B", []):
        stage_total[r.get("family", "")] += r.get("count", 0)
    for r in day_data.get("fail_families_D", []):
        stage_total[r.get("family", "")] += r.get("count", 0)
    return dict(stage_total)


def _get_9_stages_today_yesterday(date: str, full: Dict) -> tuple:
    """拿当天 + 前一天 9 环节 dict（fallback 到当月 fail_families）"""
    dd = full.get("daily_detail", {})
    today_data = dd.get(date, {})
    sorted_dates = sorted([d for d in dd.keys()])
    yesterday_date = None
    if date in sorted_dates:
        idx = sorted_dates.index(date)
        if idx > 0:
            yesterday_date = sorted_dates[idx - 1]
    yesterday_data = dd.get(yesterday_date, {}) if yesterday_date else {}
    return _merge_9_stages(today_data), _merge_9_stages(yesterday_data), yesterday_date


def build_report(date: str) -> Dict:
    """v8 报告：含 9 环节百分比 + 环比 + reason 比例 + 3 个案例订单"""
    full = _load_data()
    daily_list = full.get("daily", [])
    daily = next((d for d in daily_list if d.get("date") == date), None)
    if not daily:
        daily = max(daily_list, key=lambda x: x.get("date", ""))
        date = daily.get("date", "")
        logger.warning(f"找不到 {date}，用最近一天")

    today_9, yesterday_9, yesterday_date = _get_9_stages_today_yesterday(date, full)
    total_today_9 = sum(today_9.values()) or 1

    dd = full.get("daily_detail", {}).get(date, {})
    if not dd:
        # fallback 到顶层 fail_families
        months = full.get("months", {})
        month_key = date[:7]
        if month_key in months:
            dd = months[month_key]

    # 4 路径
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

    # 9 环节 sections
    stage_sections = []
    for stage in STAGE_ORDER:
        family_key = STAGE_FAMILY_MAP[stage]
        today_count = today_9.get(family_key, 0)
        yesterday_count = yesterday_9.get(family_key, 0)
        pct = today_count / total_today_9 * 100
        if yesterday_count > 0:
            delta_pct = (today_count - yesterday_count) / yesterday_count * 100
        elif today_count > 0:
            delta_pct = 100.0
        else:
            delta_pct = 0
        stage_sections.append({
            "stage": stage,
            "total": today_count,
            "pct": pct,
            "yesterday_total": yesterday_count,
            "delta_pct": delta_pct,
        })
    stage_sections.sort(key=lambda x: -x["total"])

    # 9 环节对应的 reasons
    all_reasons = []
    for r in dd.get("fail_reasons_B", []):
        all_reasons.append({**r, "_source": "B"})
    for r in dd.get("fail_reasons_D", []):
        all_reasons.append({**r, "_source": "D"})

    stage_reasons = {stage: [] for stage in STAGE_ORDER}
    unmatched = []
    for r in all_reasons:
        family = r.get("family", "")
        matched = False
        for stage, kw in STAGE_FAMILY_MAP.items():
            if kw in family:
                stage_reasons[stage].append(r)
                matched = True
                break
        if not matched:
            unmatched.append(r)
    if unmatched:
        stage_reasons["其他"].extend(unmatched)

    # 填 reason 到 stage_sections
    for sec in stage_sections:
        reasons = stage_reasons[sec["stage"]]
        reasons_sorted = sorted(reasons, key=lambda x: -x.get("count", 0))
        top = reasons_sorted[:5]
        sec["top_reasons"] = [
            {
                "reason": r.get("reason", ""),
                "count": r.get("count", 0),
                "prev_count": r.get("prev_count", 0),
                "orders": (r.get("orders") or [])[:3],
            }
            for r in top
        ]

    return {
        "date": date,
        "yesterday_date": yesterday_date,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "path_dist": {
            "total": total, "A": A, "B": B, "C": C, "D": D,
            "A_ratio": A_ratio, "B_ratio": B_ratio, "C_ratio": C_ratio, "D_ratio": D_ratio,
            "auto_succ_rate": auto_succ_rate,
        },
        "stage_dist": {
            "title": "【失败分布】",
            "sections": stage_sections,
            "total_today": total_today_9,
        },
    }


# --------------------------------------------------------------------------- #
# 渲染：钉钉 markdown（v8）
# --------------------------------------------------------------------------- #
def render_markdown(report: Dict) -> str:
    """v8 钉钉 markdown 渲染"""
    pd = report["path_dist"]
    sd = report["stage_dist"]
    date = report["date"]
    yesterday_date = report.get("yesterday_date", "?")

    lines = []
    lines.append(f"# 自动化数据日报 · {date}")
    lines.append("")
    lines.append(f"> 报告期：{date}（环比 {yesterday_date}）")
    lines.append(f"> 生成时间：{report['generated_at']}  ·  数据源：dashboard_data.json")
    lines.append("")

    lines.append("## 【路径分布】")
    lines.append("")
    lines.append(f"总订单 **{pd['total']}** 单  自动成功率 **{pd['auto_succ_rate']:.2f}%**")
    lines.append("")
    lines.append(f"A 全自动成功 **{pd['A']}** 单 (**{pd['A_ratio']:.2f}%**)")
    lines.append(f"B 全自动失败 **{pd['B']}** 单 (**{pd['B_ratio']:.2f}%**)")
    lines.append(f"C 订单转人工 **{pd['C']}** 单 (**{pd['C_ratio']:.2f}%**)")
    lines.append(f"D 订单处理中 **{pd['D']}** 单 (**{pd['D_ratio']:.2f}%**)")
    lines.append("")

    lines.append("## 【失败分布】")
    lines.append("")
    lines.append(f"> 总失败 {sd['total_today']} 单 · 环比 {yesterday_date}")
    lines.append("")

    for i, sec in enumerate(sd["sections"], 1):
        stage = sec["stage"]
        total = sec["total"]
        pct = sec["pct"]
        delta_pct = sec["delta_pct"]
        arrow = _delta_arrow(delta_pct)

        lines.append(f"### {i}.{stage}环节：{total} 单（{pct:.2f}%）{arrow}{abs(delta_pct):.0f}%")
        lines.append("")

        top = sec.get("top_reasons", [])
        if not top:
            lines.append("（无数据）")
            lines.append("")
            continue

        for j, r in enumerate(top, 1):
            num = ["①", "②", "③", "④", "⑤"][j - 1] if j <= 5 else f"{j}."
            reason = r["reason"]
            count = r["count"]
            prev_count = r["prev_count"]
            if prev_count > 0:
                r_delta = (count - prev_count) / prev_count * 100
            elif count > 0:
                r_delta = 100.0
            else:
                r_delta = 0
            r_arrow = _delta_arrow(r_delta)

            lines.append(f"**{num}{reason}（{count}/{prev_count}）{r_arrow}{abs(r_delta):.0f}%**")
            orders = r["orders"]
            if orders:
                orders_str = "、`".join(orders)
                lines.append(f"例:`{orders_str}`")
            lines.append("")

    # 钉钉 markdown 单换行被忽略，必须 \n\n 才换段
    return "\n\n".join(lines)


# --------------------------------------------------------------------------- #
# 渲染：钉钉 ActionCard
# --------------------------------------------------------------------------- #
def render_dingtalk_actioncard(report: Dict) -> Dict:
    md = render_markdown(report)
    return {
        "title": f"📊 自动化数据日报 · {report['date']}",
        "text": md,
    }


# --------------------------------------------------------------------------- #
# 渲染：飞书 interactive card（v8 降级版）
# --------------------------------------------------------------------------- #
def render_feishu_card(report: Dict) -> Dict:
    """飞书 interactive card v8（纯 div 降级版）

    自定义机器人 webhook 不支持 collapsible / table / fields / column
    只支持 div / markdown / hr。markdown 单换行保留。
    """
    pd = report["path_dist"]
    sd = report["stage_dist"]
    date = report["date"]
    yesterday_date = report.get("yesterday_date", "?")

    elements = []

    # 1. 报告期
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**报告期**：{date}（环比 {yesterday_date}）\n"
                f"**生成时间**：{report['generated_at']}"
            ),
        },
    })
    elements.append({"tag": "hr"})

    # 2. 4 路径
    path_lines = [
        "**📊 4 路径分布**",
        f"**总订单**：{pd['total']} 单 · 自动成功率 **{pd['auto_succ_rate']:.2f}%**",
        f"- ✅ A 全自动成功：**{pd['A']}** 单 ({pd['A_ratio']:.2f}%)",
        f"- 🛟 B 全自动失败：**{pd['B']}** 单 ({pd['B_ratio']:.2f}%)",
        f"- 🚧 C 订单转人工：**{pd['C']}** 单 ({pd['C_ratio']:.2f}%)",
        f"- ⚠️ D 订单处理中：**{pd['D']}** 单 ({pd['D_ratio']:.2f}%)",
    ]
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": "\n".join(path_lines)},
    })
    elements.append({"tag": "hr"})

    # 3. 9 大环节（每个 div 包含 markdown 列表）
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**📋 9 大环节**（总失败 {sd['total_today']} 单）"},
    })

    for i, sec in enumerate(sd["sections"], 1):
        stage = sec["stage"]
        total = sec["total"]
        pct = sec["pct"]
        delta_pct = sec["delta_pct"]
        arrow = _delta_arrow(delta_pct)

        lines = [f"### {i}.{stage}环节：{total} 单（{pct:.2f}%）{arrow}{abs(delta_pct):.0f}%", ""]
        top = sec.get("top_reasons", [])
        if not top:
            lines.append("（无数据）")
        else:
            for j, r in enumerate(top, 1):
                num = ["①", "②", "③", "④", "⑤"][j - 1] if j <= 5 else f"{j}."
                reason = r["reason"]
                count = r["count"]
                prev_count = r["prev_count"]
                if prev_count > 0:
                    r_delta = (count - prev_count) / prev_count * 100
                elif count > 0:
                    r_delta = 100.0
                else:
                    r_delta = 0
                r_arrow = _delta_arrow(r_delta)
                lines.append(f"- **{num}{reason}（{count}/{prev_count}）{r_arrow}{abs(r_delta):.0f}%**")
                orders = r["orders"]
                if orders:
                    orders_str = "、`".join(orders)
                    lines.append(f"  例:`{orders_str}`")

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
    r = build_report(date)
    return {
        "title": f"📊 自动化数据日报 · {r['date']}",
        "markdown": render_markdown(r),
        "dingtalk_card": render_dingtalk_actioncard(r),
        "feishu_card": render_feishu_card(r),
        "_raw": r,
    }
