# -*- coding: utf-8 -*-
"""
daily_report.py — 失败订单归因日报/周报/月报生成器

数据源: dashboard_data.json (由 gen_dashboard_data.py 生成)
报告维度（6 个）：
  A. Top 5 失败根因（含环比 + 责任平台/航司）
  B. 4 路径分布（A/B/C/D 占比 + 环比）
  C. 8 大环节（预定/支付/取票/回填/验真/平台/系统/其他）
  D. 需救场 Top 10 订单（B 路径下未救场成功 + D 路径下高优先级）
  E. vs 上周/上月对比
  F. 重点航司/平台预警（D 路径异常 / 自动成功率跌破阈值）

设计：
  - build_report(period, date) -> Dict  返回结构化报告
  - render_markdown(report) -> str      渲染成钉钉 markdown 文本
  - render_dingtalk_actioncard(report) -> Dict  渲染成钉钉 ActionCard
  - render_feishu_card(report) -> Dict  渲染成飞书 interactive 卡片
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

DATA_PATH = Path(r"E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard\dashboard_data.json")

# Streamlit / Dashboard 入口
DASHBOARD_URL = "https://auto-ticket-dashboard.streamlit.app/"

# 8 大环节的固定顺序和颜色（与 dashboard 保持一致）
STAGE_ORDER = ["预定", "支付", "取票", "回填", "验真", "平台", "系统", "其他"]
STAGE_COLOR = {
    "预定": "#5b8def", "支付": "#f5a623", "取票": "#ff5e5e",
    "回填": "#00b894", "验真": "#a259ff", "平台": "#7a8ba0",
    "系统": "#5b6273", "其他": "#8b95a8",
}

# A 成功率预警阈值
A_RATE_WARN = 70.0  # < 70% 触发预警
A_RATE_DANGER = 60.0  # < 60% 触发严重预警
D_RATIO_WARN = 1.5   # D 占比 > 1.5% 触发预警


# --------------------------------------------------------------------------- #
# 加载数据
# --------------------------------------------------------------------------- #
def _load_data() -> Dict:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def _format_pct(num: float, digits: int = 2) -> str:
    return f"{num:.{digits}f}%"


def _format_delta(curr: float, prev: float, digits: int = 2) -> str:
    """环比：当前 vs 上期，输出 +X.XX / -X.XX"""
    if prev == 0:
        return f"+{curr:.{digits}f}" if curr > 0 else "0.00"
    diff = curr - prev
    sign = "+" if diff >= 0 else ""
    return f"{sign}{diff:.{digits}f}"


def _arrow(emoji: str, value: str, color_hint: str = "") -> str:
    """单行数据：图标 + 值"""
    return f"{emoji} **{value}**"


# --------------------------------------------------------------------------- #
# 6 个维度的报告构造
# --------------------------------------------------------------------------- #
def section_A_top5_fail_reasons(daily: Dict, full: Dict, prev_daily: Optional[Dict] = None) -> Dict:
    """A. Top 5 失败根因（B+D 合并）"""
    reasons_B = full.get("fail_reasons_B", [])
    reasons_D = full.get("fail_reasons_D", [])
    # 合并 + 按 count 降序
    merged = []
    for r in reasons_B + reasons_D:
        merged.append({
            "reason": r.get("reason", ""),
            "family": r.get("family", ""),
            "count": r.get("count", 0),
            "prev_count": r.get("prev_count", 0),
            "prev_month": r.get("prev_month", ""),
            "platform_dist": [],
            "airline_dist": [],
        })
    merged.sort(key=lambda x: -x["count"])
    top5 = merged[:5]

    # 计算环比
    items = []
    for r in top5:
        delta = r["count"] - r["prev_count"]
        delta_pct = (delta / r["prev_count"] * 100) if r["prev_count"] > 0 else None
        items.append({
            "reason": r["reason"][:60],
            "count": r["count"],
            "prev_count": r["prev_count"],
            "delta": delta,
            "delta_pct": delta_pct,
            "family": r["family"],
        })
    return {
        "title": "A. Top 5 失败根因（含环比）",
        "items": items,
    }


def section_B_path_distribution(daily: Dict, prev_daily: Optional[Dict] = None) -> Dict:
    """B. 4 路径分布"""
    A = daily.get("A", 0)
    B = daily.get("B", 0)
    C = daily.get("C", 0)
    D = daily.get("D", 0)
    total = daily.get("total", A + B + C + D)

    A_ratio = daily.get("A_ratio", A / total * 100 if total else 0)
    B_ratio = daily.get("B_ratio", B / total * 100 if total else 0)
    C_ratio = daily.get("C_ratio", C / total * 100 if total else 0)
    D_ratio = daily.get("D_ratio", D / total * 100 if total else 0)
    auto_succ = daily.get("auto_succ_rate", 0)

    prev = {}
    if prev_daily:
        prev = {
            "A_ratio": prev_daily.get("A_ratio", 0),
            "B_ratio": prev_daily.get("B_ratio", 0),
            "C_ratio": prev_daily.get("C_ratio", 0),
            "D_ratio": prev_daily.get("D_ratio", 0),
            "auto_succ_rate": prev_daily.get("auto_succ_rate", 0),
        }

    return {
        "title": "B. 4 路径分布",
        "total": total,
        "A": A, "B": B, "C": C, "D": D,
        "A_ratio": A_ratio, "B_ratio": B_ratio, "C_ratio": C_ratio, "D_ratio": D_ratio,
        "auto_succ_rate": auto_succ,
        "prev": prev,
    }


def section_C_stages(daily: Dict, prev_daily: Optional[Dict] = None) -> Dict:
    """C. 8 大环节（仅 B+D 总数 + 占比）"""
    # 从 daily_detail 拿当天 stage 数据
    full = _load_data()
    dd = full.get("daily_detail", {})
    date = daily.get("date", "")
    detail = dd.get(date, {})
    # daily_subcategory 按"阶段-子类"形式存储，例如"预定-询价失败"
    # 这里按阶段聚合
    subcat_list = [s for s in full.get("daily_subcategory", []) if s.get("date") == date]
    if subcat_list:
        subcat = subcat_list[0]
    else:
        subcat = {}

    stage_total = {}
    for k, v in subcat.items():
        if k == "date":
            continue
        if "-" in k:
            stage, _ = k.split("-", 1)
            stage_total[stage] = stage_total.get(stage, 0) + v

    grand_total = sum(stage_total.values()) or 1
    items = []
    for stage in STAGE_ORDER:
        cnt = stage_total.get(stage, 0)
        pct = cnt / grand_total * 100
        items.append({
            "stage": stage,
            "count": cnt,
            "pct": pct,
            "color": STAGE_COLOR.get(stage, "#888"),
        })
    # 按 count 降序
    items.sort(key=lambda x: -x["count"])
    return {
        "title": "C. 8 大环节（按出票环节）",
        "items": items,
        "total": grand_total,
    }


def section_D_rescue_top10(full: Dict, daily: Dict) -> Dict:
    """D. 需救场 Top 10 订单"""
    # 优先取 B 路径下未救场成功 + D 路径下高优先级
    # fail_drill_B 的 rescued_count / rescue_rate 已统计
    items = []
    for fd in full.get("fail_drill_B", [])[:10]:
        items.append({
            "reason": fd.get("reason", "")[:50],
            "total": fd.get("total", 0),
            "rescued": fd.get("rescued_count", 0),
            "rescue_rate": fd.get("rescue_rate", 0),
            "platform_top": (fd.get("platform_dist", [{}])[0] or {}).get("name", "-"),
            "airline_top": (fd.get("airline_dist", [{}])[0] or {}).get("code", "-"),
        })
    return {
        "title": "D. 需救场 Top 10 失败原因",
        "items": items,
    }


def section_E_compare(daily: Dict, full: Dict, prev_daily: Optional[Dict] = None) -> Dict:
    """E. vs 上周/上月对比（当日 vs 昨日 vs 月均）"""
    # 当月数据均值
    month_daily = [d for d in full.get("daily", []) if d.get("date", "").startswith(daily.get("date", "")[:7])]
    if not month_daily:
        return {"title": "E. 对比", "items": []}
    month_avg_total = sum(d.get("total", 0) for d in month_daily) / len(month_daily)
    month_avg_A = sum(d.get("A", 0) for d in month_daily) / len(month_daily)
    month_avg_succ = sum(d.get("auto_succ_rate", 0) for d in month_daily) / len(month_daily)

    return {
        "title": "E. 对比（当日 vs 昨日 vs 月均）",
        "today_total": daily.get("total", 0),
        "today_A": daily.get("A", 0),
        "today_succ": daily.get("auto_succ_rate", 0),
        "month_avg_total": month_avg_total,
        "month_avg_A": month_avg_A,
        "month_avg_succ": month_avg_succ,
        "yesterday": prev_daily,  # 用 prev_daily 当昨天
    }


def section_F_warnings(daily: Dict, full: Dict) -> Dict:
    """F. 重点航司/平台预警"""
    warnings = []

    # 1. 当日 A 成功率跌破阈值
    succ = daily.get("auto_succ_rate", 100)
    if succ < A_RATE_DANGER:
        warnings.append({
            "level": "danger",
            "text": f"当日 A 成功率 **{succ:.2f}%** 跌破 {A_RATE_DANGER:.0f}%（严重）",
        })
    elif succ < A_RATE_WARN:
        warnings.append({
            "level": "warn",
            "text": f"当日 A 成功率 **{succ:.2f}%** 跌破 {A_RATE_WARN:.0f}%",
        })

    # 2. D 占比超阈
    D_ratio = daily.get("D_ratio", 0)
    if D_ratio > D_RATIO_WARN:
        warnings.append({
            "level": "warn",
            "text": f"D 路径（票未出完）占比 **{D_ratio:.2f}%** > {D_RATIO_WARN}%，需关注",
        })

    # 3. 重点航司（airline 列表里 D 占比异常高）
    for a in full.get("airline", []):
        D_pct = a.get("D_ratio", 0)
        D_count = a.get("D", 0)
        if D_count >= 5 and D_pct > 5.0:  # 5 单以上 + D 占比 > 5%
            warnings.append({
                "level": "warn",
                "text": f"航司 **{a.get('code', '')} {a.get('name', '')}** D 占比 {D_pct:.2f}%（{D_count} 单）",
            })
            if len([w for w in warnings if w.get("type") == "airline"]) >= 3:
                break  # 最多 3 条航司预警

    # 4. 重点平台
    for p in full.get("platform", []):
        D_pct = p.get("D_ratio", 0)
        D_count = p.get("D", 0)
        if D_count >= 10 and D_pct > 3.0:
            warnings.append({
                "level": "warn",
                "text": f"平台 **{p.get('name', '')}** D 占比 {D_pct:.2f}%（{D_count} 单）",
            })
            break

    return {
        "title": "F. 重点航司/平台预警",
        "warnings": warnings[:6],  # 最多 6 条
    }


# --------------------------------------------------------------------------- #
# 主入口：build_report
# --------------------------------------------------------------------------- #
def build_report(date: str, period: str = "daily", prev_date: Optional[str] = None) -> Dict:
    """构造一份完整报告（dict 形式）

    period: daily / weekly / monthly（仅 daily 完整实现，weekly/monthly 用 daily 复用）
    date:   YYYY-MM-DD（daily）/ 周一日期（weekly）/ 月初（monthly）
    """
    full = _load_data()
    daily_list = full.get("daily", [])
    daily = next((d for d in daily_list if d.get("date") == date), None)
    if not daily:
        # 找不到就用最近一天
        daily = max(daily_list, key=lambda x: x.get("date", ""))
        date = daily.get("date", "")
        logger.warning(f"找不到 {date}，用最近一天 {date}")

    # 找前一个日期（用于环比）
    prev_daily = None
    if prev_date:
        prev_daily = next((d for d in daily_list if d.get("date") == prev_date), None)
    else:
        # 自动找前一个 date
        sorted_dates = sorted([d.get("date", "") for d in daily_list])
        if date in sorted_dates:
            idx = sorted_dates.index(date)
            if idx > 0:
                prev_daily = next((d for d in daily_list if d.get("date") == sorted_dates[idx - 1]), None)

    report = {
        "period": period,
        "date": date,
        "prev_date": prev_daily.get("date") if prev_daily else None,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sections": {
            "A": section_A_top5_fail_reasons(daily, full, prev_daily),
            "B": section_B_path_distribution(daily, prev_daily),
            "C": section_C_stages(daily, prev_daily),
            "D": section_D_rescue_top10(full, daily),
            "E": section_E_compare(daily, full, prev_daily),
            "F": section_F_warnings(daily, full),
        },
        "dashboard_url": DASHBOARD_URL,
    }
    return report


# --------------------------------------------------------------------------- #
# 渲染：Markdown（钉钉兼容）
# --------------------------------------------------------------------------- #
def render_markdown(report: Dict) -> str:
    """渲染成钉钉 markdown 格式（用 ** 加粗、emoji 列表）"""
    s = report["sections"]
    date = report["date"]
    prev_date = report.get("prev_date", "")

    md = []
    md.append(f"## 📊 失败订单归因分析日报 · {date}")
    md.append("")
    md.append(f"> 报告期：{date}（环比 {prev_date or '-'}）")
    md.append(f"> 生成时间：{report['generated_at']}")
    md.append(f"> 数据源：dashboard_data.json")
    md.append("")

    # ---- B. 4 路径分布（核心 KPI，最先显示） ----
    B = s["B"]
    md.append(f"### {B['title']}")
    md.append(f"- 总订单：**{B['total']}** 单")
    md.append(f"- ✅ A 全自动成功：**{B['A']}** 单（{B['A_ratio']:.2f}%）")
    md.append(f"- 🛟 B 救场成功：**{B['B']}** 单（{B['B_ratio']:.2f}%）")
    md.append(f"- 🚧 C 政策强制人工：**{B['C']}** 单（{B['C_ratio']:.2f}%）")
    md.append(f"- ⚠️ D 票未出完：**{B['D']}** 单（{B['D_ratio']:.2f}%）")
    md.append(f"- 自动成功率：**{B['auto_succ_rate']:.2f}%**")
    if B.get("prev"):
        p = B["prev"]
        if p.get("auto_succ_rate"):
            delta = B["auto_succ_rate"] - p["auto_succ_rate"]
            arrow = "🔺" if delta > 0 else ("🔻" if delta < 0 else "➖")
            md.append(f"- 环比昨日：{arrow} {delta:+.2f} pct")
    md.append("")

    # ---- C. 8 大环节 ----
    C = s["C"]
    md.append(f"### {C['title']}")
    if C.get("items"):
        # 8 大环节：固定顺序显示（包括空环节也展示）
        for stage in STAGE_ORDER:
            item = next((it for it in C["items"] if it["stage"] == stage), None)
            if item and item["count"] > 0:
                bar = "█" * max(1, int(item["pct"] / 5))  # 20 字符满
                md.append(f"- {stage}：{item['count']} 单（{item['pct']:.1f}%）{bar}")
            else:
                md.append(f"- {stage}：0 单")
    md.append("")

    # ---- A. Top 5 失败根因 ----
    A = s["A"]
    md.append(f"### {A['title']}")
    if A.get("items"):
        for i, r in enumerate(A["items"], 1):
            delta = r["delta"]
            if r["prev_count"] > 0:
                arrow = "🔺" if delta > 0 else ("🔻" if delta < 0 else "➖")
                delta_str = f"{arrow} {delta:+d}（上月同期 {r['prev_count']}）"
            else:
                delta_str = f"（上月无）"
            md.append(f"{i}. **{r['reason']}**")
            md.append(f"   - 当月累计：{r['count']} 单 {delta_str}")
    md.append("")

    # ---- D. 需救场 Top 10 ----
    D = s["D"]
    md.append(f"### {D['title']}")
    if D.get("items"):
        for i, r in enumerate(D["items"][:5], 1):  # 简版只显示 5 条
            md.append(f"{i}. {r['reason']} — {r['total']} 单（救场率 {r['rescue_rate']:.0f}%）")
    md.append("")

    # ---- F. 预警（最重要，放最后） ----
    F = s["F"]
    if F.get("warnings"):
        md.append(f"### 🚨 {F['title']}")
        for w in F["warnings"]:
            icon = "🔴" if w["level"] == "danger" else "🟡"
            md.append(f"- {icon} {w['text']}")
        md.append("")

    # ---- E. 对比 ----
    E = s["E"]
    md.append(f"### {E['title']}")
    if E.get("yesterday"):
        y = E["yesterday"]
        md.append(f"- 当日 {E['today_total']} 单 / 月均 {E['month_avg_total']:.0f} 单")
        md.append(f"- 当日 A 成功率 {E['today_succ']:.2f}% / 月均 {E['month_avg_succ']:.2f}%")
        md.append(f"- 昨日（{y.get('date')}）：{y.get('total')} 单，A 成功率 {y.get('auto_succ_rate', 0):.2f}%")
    else:
        md.append(f"- 当日 {E['today_total']} 单 / 月均 {E['month_avg_total']:.0f} 单")
    md.append("")

    # ---- 页脚 ----
    md.append(f"---\n📈 [查看 Dashboard 详情]({DASHBOARD_URL})")

    return "\n".join(md)


# --------------------------------------------------------------------------- #
# 渲染：钉钉 ActionCard
# --------------------------------------------------------------------------- #
def render_dingtalk_actioncard(report: Dict) -> Dict:
    """钉钉 ActionCard（单链接 + 折叠面板）"""
    md = render_markdown(report)
    return {
        "title": f"📊 失败订单归因日报 · {report['date']}",
        "text": md,
        "singleTitle": "📈 查看 Dashboard",
        "singleURL": DASHBOARD_URL,
    }


# --------------------------------------------------------------------------- #
# 渲染：飞书 interactive 卡片
# --------------------------------------------------------------------------- #
def render_feishu_card(report: Dict) -> Dict:
    """飞书 interactive 卡片"""
    s = report["sections"]
    B = s["B"]
    F = s["F"]

    elements = []

    # 标题
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": f"**报告期**：{report['date']}（环比 {report.get('prev_date', '-')}）\n**生成时间**：{report['generated_at']}",
        },
    })
    elements.append({"tag": "hr"})

    # B. 4 路径
    c_ratio_str = f"{B['C_ratio']:.2f}%"
    elements.append({
        "tag": "div",
        "text": {
            "tag": "lark_md",
            "content": (
                f"**📊 4 路径分布**\n"
                f"- 总订单 **{B['total']}** 单\n"
                f"- ✅ A 全自动成功：**{B['A']}** 单（{B['A_ratio']:.2f}%）\n"
                f"- 🛟 B 救场成功：**{B['B']}** 单（{B['B_ratio']:.2f}%）\n"
                f"- 🚧 C 政策强制人工：**{B['C']}** 单（{c_ratio_str}）\n"
                f"- ⚠️ D 票未出完：**{B['D']}** 单（{B['D_ratio']:.2f}%）\n"
                f"- 自动成功率：**{B['auto_succ_rate']:.2f}%**"
            ),
        },
    })
    elements.append({"tag": "hr"})

    # F. 预警
    if F.get("warnings"):
        warn_lines = ["**🚨 预警**"]
        for w in F["warnings"]:
            icon = "🔴" if w["level"] == "danger" else "🟡"
            warn_lines.append(f"{icon} {w['text']}")
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(warn_lines)},
        })
        elements.append({"tag": "hr"})

    # A. Top 5（折叠）
    A = s["A"]
    if A.get("items"):
        top5_lines = ["**📋 Top 5 失败根因**"]
        for i, r in enumerate(A["items"], 1):
            top5_lines.append(f"{i}. {r['reason'][:40]} ({r['count']} 单)")
        elements.append({
            "tag": "collapsible",
            "header": {"title": {"tag": "plain_text", "content": "📋 展开 Top 5 失败根因"}},
            "elements": [{"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(top5_lines)}}],
        })

    # 跳转链接
    elements.append({
        "tag": "action",
        "actions": [{
            "tag": "button",
            "text": {"tag": "plain_text", "content": "📈 查看 Dashboard 详情"},
            "type": "primary",
            "url": DASHBOARD_URL,
        }],
    })

    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"📊 失败归因日报 · {report['date']}"},
        },
        "elements": elements,
    }


# --------------------------------------------------------------------------- #
# 包装：构造可直接 push 的 report
# --------------------------------------------------------------------------- #
def build_pushable_report(date: str, period: str = "daily", prev_date: Optional[str] = None) -> Dict:
    """构造可直接传给 notify.send() 的报告（带 markdown + dingtalk_card + feishu_card）"""
    r = build_report(date, period, prev_date)
    return {
        "title": f"📊 失败订单归因日报 · {r['date']}",
        "markdown": render_markdown(r),
        "action_url": DASHBOARD_URL,
        "dingtalk_card": render_dingtalk_actioncard(r),
        "feishu_card": render_feishu_card(r),
        "_raw": r,  # 完整结构（调试用）
    }
