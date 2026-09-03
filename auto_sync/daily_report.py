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


def _check_health(full: Dict, latest_date: str) -> Dict:
    """v9（2026-09-01）：健康检查——数据滞后 + auto_sync 心跳。

    - 数据滞后：最新数据日期距今 >=2 天 → 警示（断档时日报照发、业务无感知的教训）
    - auto_sync 心跳：status.db 上次触发距今 >90 分钟 → 疑似停摆
      （30 分钟兜底任务正常时 age 应 <=40 分钟左右）
    """
    warnings = []
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        from datetime import date as _date
        d0 = _date.fromisoformat(latest_date)
        d1 = _date.fromisoformat(today)
        lag_days = (d1 - d0).days
    except Exception:
        lag_days = 0
    if lag_days >= 2:
        warnings.append(f"⚠️ 数据滞后：最新数据为 {latest_date}（距今 {lag_days} 天），拉取链路疑似异常")

    trigger_age_min = None
    try:
        import sqlite3
        from .status import StatusStore
        store = StatusStore(str(DATA_PATH.parent / "auto_sync" / "data" / "status.db"))
        st = store.get_status()
        if st and st.last_trigger_at:
            t = datetime.fromisoformat(st.last_trigger_at)
            now = datetime.now(t.tzinfo) if t.tzinfo else datetime.now()  # 对齐时区感知
            trigger_age_min = int((now - t).total_seconds() / 60)
            if trigger_age_min > 90:
                warnings.append(f"🔴 auto_sync 疑似停摆：上次触发距今 {trigger_age_min} 分钟")
    except Exception as e:
        logger.warning(f"心跳检查失败（不影响报告）: {e}")

    return {"lag_days": lag_days, "trigger_age_min": trigger_age_min, "warnings": warnings}


def build_report(date: str) -> Dict:
    """v8 报告：含 9 环节百分比 + 环比 + reason 比例 + 3 个案例订单"""
    full = _load_data()
    daily_list = full.get("daily", [])
    daily = next((d for d in daily_list if d.get("date") == date), None)
    if not daily:
        daily = max(daily_list, key=lambda x: x.get("date", ""))
        date = daily.get("date", "")
        logger.warning(f"找不到 {date}，用最近一天")

    # v10.16（2026-09-01）：daily_detail 已从顶层 json 剥离到 monthly/{ym}.json，
    # 这里按需合入（9 环节环比 / 失败明细都依赖它）。
    # 同时合入上一个月，月初第一天的"环比昨天"才能跨月取到。
    if not full.get("daily_detail"):
        merged = {}
        ym = date[:7]
        months_avail = full.get("available_months") or []
        if ym in months_avail:
            idx = months_avail.index(ym)
            prev_ym = months_avail[idx - 1] if idx > 0 else None
        else:
            prev_ym = None
        for m in filter(None, [prev_ym, ym]):
            mp = DATA_PATH.parent / "monthly" / f"{m}.json"
            if mp.exists():
                try:
                    merged.update(json.loads(mp.read_text(encoding="utf-8")).get("daily_detail", {}))
                except Exception as e:
                    logger.warning(f"读 {mp} 失败: {e}")
        full["daily_detail"] = merged

    health = _check_health(full, date)

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
        "health": health,
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
    # v9：健康警示置顶（数据滞后 / auto_sync 停摆时第一时间可见）
    for w in report.get("health", {}).get("warnings", []):
        lines.append(w)
        lines.append("")
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

    # v9：健康警示置顶
    warns = report.get("health", {}).get("warnings", [])
    if warns:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": "\n".join(warns)},
        })
        elements.append({"tag": "hr"})

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
# --------------------------------------------------------------------------- #
# v9（2026-09-01）：一屏日报（业务员版）+ 周报/月报（经理版）
#
# 设计原则（用户拍板）：
#   - 结论先行、只报异常、行动项带可复制订单号、细节引导到看板
#   - 日报服务业务员（一屏），周报/月报服务经理（趋势与结构）
# --------------------------------------------------------------------------- #
DASHBOARD_URL = "https://auto-ticket-dashboard.streamlit.app"


def _load_dd_for_months(ym_list):
    """按月份列表加载并合并 monthly/*.json 的 daily_detail"""
    merged = {}
    for m in ym_list:
        mp = DATA_PATH.parent / "monthly" / f"{m}.json"
        if mp.exists():
            try:
                merged.update(json.loads(mp.read_text(encoding="utf-8")).get("daily_detail", {}))
            except Exception as e:
                logger.warning(f"读 {mp} 失败: {e}")
    return merged


def _prev_dates(dd, date, n):
    dates = sorted(dd.keys())
    if date not in dates:
        return []
    i = dates.index(date)
    return dates[max(0, i - n):i]


def _fmt_pp(v):
    return f"+{v:.1f}" if v >= 0 else f"{v:.1f}"


def _collect_attention(full, date, limit=3):
    """v9『值得注意』：新根因 / 连续上升根因。正常波动不上榜。"""
    dd = full.get("daily_detail", {})
    today = dd.get(date, {})
    prevs = _prev_dates(dd, date, 2)
    y1 = {r["reason"]: r.get("count", 0) for r in dd.get(prevs[-1], {}).get("fail_reasons_B", [])} if prevs else {}
    y2 = {r["reason"]: r.get("count", 0) for r in dd.get(prevs[0], {}).get("fail_reasons_B", [])} if len(prevs) > 1 else {}
    items = []
    # ① 新根因：昨天没有、今天 >=2 单
    for r in sorted(today.get("fail_reasons_B", []), key=lambda x: -x.get("count", 0)):
        c = r.get("count", 0)
        if c >= 2 and r["reason"] not in y1:
            items.append({
                "kind": "new", "reason": r["reason"], "count": c,
                "orders": [str(o) for o in (r.get("orders") or [])[:2]],
            })
        if sum(1 for i in items if i["kind"] == "new") >= 2:
            break
    # ② 连续 2 天上升：D-2 < D-1 < 今天，今天 >=5 单且比昨天多 50%
    for r in today.get("fail_reasons_B", []):
        c2 = y2.get(r["reason"], -1)
        c1 = y1.get(r["reason"], 0)
        c0 = r.get("count", 0)
        if c0 >= 5 and c0 > c1 > c2 and c0 >= c1 * 1.5:
            items.append({
                "kind": "rise", "reason": r["reason"], "count": c0,
                "orders": [str(o) for o in (r.get("orders") or [])[:2]],
            })
    return items[:limit]


def build_brief(date: str) -> Dict:
    """v9 日报数据（业务员版）"""
    full = _load_data()
    if not full.get("daily_detail"):
        full["daily_detail"] = _load_dd_for_months(_recent_month_keys(full, date, 2))
    dd = full["daily_detail"]
    today = dd.get(date) or {}
    s = today.get("summary", {})
    prevs = _prev_dates(dd, date, 1)
    y_s = dd.get(prevs[0], {}).get("summary", {}) if prevs else {}

    # 月度累计 vs 上月
    ym = date[:7]
    months = full.get("months", {})
    month_sum = months.get(ym, {}).get("summary", {}) or (today.get("summary", {}) if date.endswith("01") else {})
    months_avail = full.get("available_months") or []
    prev_ym = months_avail[months_avail.index(ym) - 1] if ym in months_avail and months_avail.index(ym) > 0 else None
    prev_month_sum = months.get(prev_ym, {}).get("summary", {}) if prev_ym else {}

    staff_top = sorted(today.get("staff", []), key=lambda x: -x.get("B", 0))[:2]
    attention = _collect_attention(full, date)
    health = _check_health(full, date)

    succ = s.get("auto_succ_rate") or 0
    succ_prev = y_s.get("auto_succ_rate") or 0
    return {
        "date": date,
        "yesterday_date": prevs[0] if prevs else None,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "succ": succ, "succ_prev": succ_prev,
        "succ_delta": succ - succ_prev if succ_prev else None,
        "total": s.get("total_orders", 0), "A": s.get("A", 0), "B": s.get("B", 0),
        "C": s.get("C", 0), "D": s.get("D", 0),
        "month_rate": month_sum.get("auto_succ_rate"),
        "prev_month_rate": prev_month_sum.get("auto_succ_rate"),
        "prev_month_name": prev_ym,
        "staff_top": [{"name": x.get("name"), "B": x.get("B", 0)} for x in staff_top],
        "attention": attention,
        "health": health,
    }


def _recent_month_keys(full, date, n=2):
    """取 date 所在月及之前 n-1 个月（跨月环比/懒加载用）"""
    months = full.get("available_months") or []
    ym = date[:7]
    if ym in months:
        i = months.index(ym)
        return months[max(0, i - n + 1):i + 1]
    return [ym]


def render_brief_markdown(b: Dict) -> str:
    """v9 钉钉 markdown（一屏）。钉钉单换行被忽略 → 全部 \n\n 分段"""
    has_issue = bool(b["attention"]) or bool(b["health"].get("warnings"))
    d = b["succ_delta"]
    delta_str = f"（昨日 {b['succ_prev']:.1f}% {_fmt_pp(d)}pp）" if d is not None else ""
    L = []
    L.append(f"### {'⚠️' if has_issue else '✅'} 自动成功率 **{b['succ']:.1f}%**{delta_str}")
    L.append(f"**📦 {b['total']:,} 单** ｜ A {b['A']:,} ｜ B {b['B']}·人工介入 ｜ C {b['C']} ｜ D {b['D']}")
    for w in b["health"].get("warnings", []):
        L.append(w)
    if b["attention"]:
        L.append("**🔴 值得注意**")
        for it in b["attention"]:
            tag = "新根因" if it["kind"] == "new" else "连续上升"
            L.append(f"- 【{tag}】{it['reason']}（{it['count']} 单）")
            if it["orders"]:
                L.append(f"  订单号：{' · '.join(it['orders'])}")
    if b["month_rate"] is not None:
        pm = f"（上月 {b['prev_month_rate']:.1f}%）" if b["prev_month_rate"] is not None else ""
        L.append(f"📈 本月累计 {b['month_rate']:.1f}%{pm}")
    if b["staff_top"]:
        L.append("👨‍💼 今日救场：" + " · ".join(f"{x['name']} {x['B']} 单" for x in b["staff_top"]))
    L.append(f"🔗 [打开完整看板]({DASHBOARD_URL})")
    return "\n\n".join(L)


def render_brief_feishu(b: Dict) -> Dict:
    """v9 飞书卡片（一屏，header 变色）"""
    has_issue = bool(b["attention"]) or bool(b["health"].get("warnings"))
    d = b["succ_delta"]
    delta_str = f"（昨日 {b['succ_prev']:.1f}%，{_fmt_pp(d)}pp）" if d is not None else ""
    els = []
    els.append({"tag": "div", "text": {"tag": "lark_md", "content":
        f"**{'⚠️' if has_issue else '✅'} 自动成功率 {b['succ']:.1f}%**{delta_str}\n"
        f"**📦 {b['total']:,} 单** ｜ A {b['A']:,} ｜ B {b['B']}·人工介入 ｜ C {b['C']} ｜ D {b['D']}"}})
    for w in b["health"].get("warnings", []):
        els.append({"tag": "div", "text": {"tag": "lark_md", "content": w}})
    if b["attention"]:
        lines = ["**🔴 值得注意**"]
        for it in b["attention"]:
            tag = "新根因" if it["kind"] == "new" else "连续上升"
            ln = f"- 【{tag}】{it['reason']}（{it['count']} 单）"
            if it["orders"]:
                ln += f"\n  订单号：{' · '.join(it['orders'])}"
            lines.append(ln)
        els.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(lines)}})
    tail = []
    if b["month_rate"] is not None:
        pm = f"（上月 {b['prev_month_rate']:.1f}%）" if b["prev_month_rate"] is not None else ""
        tail.append(f"📈 本月累计 {b['month_rate']:.1f}%{pm}")
    if b["staff_top"]:
        tail.append("👨‍💼 今日救场：" + " · ".join(f"{x['name']} {x['B']} 单" for x in b["staff_top"]))
    tail.append(f"🔗 [打开完整看板]({DASHBOARD_URL})")
    els.append({"tag": "div", "text": {"tag": "lark_md", "content": "\n".join(tail)}})
    return {
        "header": {
            "title": {"tag": "plain_text", "content": f"📊 出票日报 · {b['date']} {'⚠️' if has_issue else '✅'}"},
            "template": "red" if has_issue else "green",
        },
        "elements": els,
    }


# ---------------- 周报 / 月报（经理版） ---------------- #

def _agg_days(dd, dates):
    """把若干天的 daily_detail 聚合（summary 四路径 / 平台 / 航司 / 员工 / B 环节族 / 根因计数）"""
    agg = {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0, "days": 0,
           "platform": {}, "airline": {}, "staff": {}, "famB": {}, "reasonB": {}}
    for d in dates:
        day = dd.get(d)
        if not day:
            continue
        agg["days"] += 1
        s = day.get("summary", {})
        for k in ("total", "A", "B", "C", "D"):
            agg[k] += s.get(k if k != "total" else "total_orders", 0)
        for p in day.get("platform", []):
            t = agg["platform"].setdefault(p["platform"], {"total": 0, "A": 0, "B": 0})
            t["total"] += p.get("total", 0); t["A"] += p.get("A", 0); t["B"] += p.get("B", 0)
        for a in day.get("airline", []):
            t = agg["airline"].setdefault(f"{a.get('airline', '?')} {a.get('name', '')}".strip(), {"total": 0, "A": 0, "B": 0})
            t["total"] += a.get("total", 0); t["A"] += a.get("A", 0); t["B"] += a.get("B", 0)
        for st in day.get("staff", []):
            agg["staff"][st.get("name", "?")] = agg["staff"].get(st.get("name", "?"), 0) + st.get("B", 0)
        for f in day.get("fail_families_B", []):
            agg["famB"][f.get("family", "?")] = agg["famB"].get(f.get("family", "?"), 0) + f.get("count", 0)
        for r in day.get("fail_reasons_B", []):
            agg["reasonB"][r["reason"]] = agg["reasonB"].get(r["reason"], 0) + r.get("count", 0)
    return agg


def _rate(x):
    ab = x["A"] + x["B"]
    return x["A"] / ab * 100 if ab else 0.0


def _risk_split(reason_counts):
    """风控拦截 vs 技术失败拆分（按根因文本含『亏损大于』归类，不动 gen 口径）"""
    risk = tech = 0
    top_tech = []
    for reason, c in sorted(reason_counts.items(), key=lambda kv: -kv[1]):
        if "亏损大于" in reason or "利润大于" in reason:
            risk += c
        else:
            tech += c
            top_tech.append((reason, c))
    return risk, tech, top_tech


def build_weekly(date: str) -> Dict:
    """周报数据：最近 7 天 vs 之前 7 天"""
    full = _load_data()
    dd = _load_dd_for_months(_recent_month_keys(full, date, 2))
    dates = sorted(dd.keys())
    i = dates.index(date) if date in dates else len(dates) - 1
    cur_d = [d for d in dates[max(0, i - 6):i + 1]]
    prev_d = [d for d in dates[max(0, i - 13):max(0, i - 6)]]
    cur, prev = _agg_days(dd, cur_d), _agg_days(dd, prev_d)
    risk, tech, top_tech = _risk_split(cur["reasonB"])
    plat = sorted(cur["platform"].items(), key=lambda kv: _rate(kv[1]))
    air = sorted(cur["airline"].items(), key=lambda kv: _rate(kv[1]))
    worsen = []
    for fam, c in cur["famB"].items():
        p = prev["famB"].get(fam, 0)
        if c >= 20 and p and c > p * 1.3:
            worsen.append((fam, c, p))
    worsen.sort(key=lambda x: -(x[1] - x[2]))
    return {
        "period": f"{cur_d[0]} ~ {cur_d[-1]}", "prev_period": f"{prev_d[0]} ~ {prev_d[-1]}" if prev_d else "?",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cur": cur, "prev": prev,
        "cur_rate": _rate(cur), "prev_rate": _rate(prev) if prev["A"] + prev["B"] else None,
        "risk": risk, "tech": tech, "top_tech": top_tech[:5],
        "plat_low": [(k, v, _rate(v)) for k, v in plat if v["total"] >= 50][:5],
        "air_low": [(k, v, _rate(v)) for k, v in air if v["total"] >= 100][:5],
        "worsen": worsen[:3],
        "staff_top": sorted(cur["staff"].items(), key=lambda kv: -kv[1])[:5],
    }


def build_monthly(ym: str) -> Dict:
    """月报数据：月 vs 上月"""
    full = _load_data()
    months_avail = full.get("available_months") or []
    prev_ym = months_avail[months_avail.index(ym) - 1] if ym in months_avail and months_avail.index(ym) > 0 else None

    def load(m):
        mp = DATA_PATH.parent / "monthly" / f"{m}.json"
        return json.loads(mp.read_text(encoding="utf-8")) if mp.exists() else {}

    cur_m, prev_m = load(ym), load(prev_ym or "")
    cs, ps = cur_m.get("summary", {}), prev_m.get("summary", {})
    reason_counts = {r["reason"]: r.get("count", 0) for r in cur_m.get("fail_reasons_B", [])}
    risk, tech, top_tech = _risk_split(reason_counts)
    plat = sorted(cur_m.get("platform", []), key=_rate)
    air = sorted(cur_m.get("airline", []), key=_rate)
    return {
        "ym": ym, "prev_ym": prev_ym,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "cs": cs, "ps": ps,
        "cur_rate": cs.get("auto_succ_rate", 0), "prev_rate": ps.get("auto_succ_rate"),
        "risk": risk, "tech": tech, "top_tech": top_tech[:5],
        "plat_low": [(p["platform"], {"total": p["total"], "A": p["A"], "B": p["B"]}, _rate(p))
                     for p in plat if p.get("total", 0) >= 500][:5],
        "air_low": [(f"{p.get('airline', '?')} {p.get('name', '')}".strip(),
                     {"total": p["total"], "A": p["A"], "B": p["B"]}, _rate(p))
                    for p in air if p.get("total", 0) >= 1000][:5],
        "staff_top": sorted([(s.get("name", "?"), s.get("B", 0)) for s in cur_m.get("staff", [])],
                            key=lambda kv: -kv[1])[:5],
        "famB": sorted([(f.get("family", "?"), f.get("count", 0)) for f in cur_m.get("fail_families_B", [])],
                       key=lambda kv: -kv[1]),
    }


def _digest_kv_rows(rows):
    """(名, (total,A,B), rate) → markdown 列表行"""
    return [f"- {k}：{v['total']:,} 单，成功率 {r:.1f}%" for k, v, r in rows]


def render_weekly(w) -> Dict:
    pr = f"（上周 {w['prev_rate']:.1f}%，{_fmt_pp(w['cur_rate'] - w['prev_rate'])}pp）" if w["prev_rate"] is not None else ""
    md = "\n\n".join(filter(None, [
        f"### 📈 周报 · {w['period']}",
        f"**自动成功率 {w['cur_rate']:.1f}%**{pr}",
        f"📦 {w['cur']['total']:,} 单 ｜ B {w['cur']['B']:,}（上周 {w['prev']['B']:,}）",
        f"🛡️ 风控拦截 {w['risk']:,} 单 · 🔧 技术失败 {w['tech']:,} 单",
        "**📉 平台成功率后 5**\n\n" + "\n\n".join(_digest_kv_rows(w["plat_low"])) if w["plat_low"] else "",
        "**✈️ 航司成功率后 5**\n\n" + "\n\n".join(_digest_kv_rows(w["air_low"])) if w["air_low"] else "",
        "**⚠️ 连续恶化的环节**\n\n" + "\n\n".join(
            f"- {f}：{c} 单（上周 {p} 单，+{c - p}）" for f, c, p in w["worsen"]) if w["worsen"] else "",
        "**🔧 技术失败 Top 5**\n\n" + "\n\n".join(
            f"- {r}（{c} 单）" for r, c in w["top_tech"]) if w["top_tech"] else "",
        "**👨‍💼 救场 Top 5**：" + " · ".join(f"{n} {c}" for n, c in w["staff_top"]) if w["staff_top"] else "",
        f"🔗 [打开完整看板]({DASHBOARD_URL})",
    ]))
    fs_els = [{"tag": "div", "text": {"tag": "lark_md", "content": s.replace("\n\n", "\n")}}
              for s in [f"**📈 周报 · {w['period']}**",
                        f"**自动成功率 {w['cur_rate']:.1f}%**{pr}\n📦 {w['cur']['total']:,} 单 ｜ B {w['cur']['B']:,}（上周 {w['prev']['B']:,}）",
                        f"🛡️ 风控拦截 {w['risk']:,} 单 · 🔧 技术失败 {w['tech']:,} 单"] +
              ([ "**📉 平台成功率后 5**\n" + "\n".join(_digest_kv_rows(w["plat_low"])) ] if w["plat_low"] else []) +
              ([ "**✈️ 航司成功率后 5**\n" + "\n".join(_digest_kv_rows(w["air_low"])) ] if w["air_low"] else []) +
              ([ "**⚠️ 连续恶化的环节**\n" + "\n".join(f"- {f}：{c} 单（上周 {p} 单，+{c - p}）" for f, c, p in w["worsen"]) ] if w["worsen"] else []) +
              ([ "**🔧 技术失败 Top 5**\n" + "\n".join(f"- {r}（{c} 单）" for r, c in w["top_tech"]) ] if w["top_tech"] else []) +
              ([ "**👨‍💼 救场 Top 5**：" + " · ".join(f"{n} {c}" for n, c in w["staff_top"]) ] if w["staff_top"] else []) +
              [ f"🔗 [打开完整看板]({DASHBOARD_URL})" ]]
    return {
        "title": f"📈 出票周报 · {w['period']}",
        "markdown": md,
        "feishu_card": {
            "header": {"title": {"tag": "plain_text", "content": f"📈 出票周报 · {w['period']}"},
                       "template": "orange"},
            "elements": fs_els,
        },
    }


def render_monthly(mm) -> Dict:
    cs, ps = mm["cs"], mm["ps"]
    pr = f"（上月 {mm['prev_rate']:.1f}%，{_fmt_pp(mm['cur_rate'] - mm['prev_rate'])}pp）" if mm["prev_rate"] is not None else ""
    b_total = cs.get("B", 0) or 1
    md = "\n\n".join(filter(None, [
        f"### 📊 月报 · {mm['ym']}",
        f"**自动成功率 {mm['cur_rate']:.1f}%**{pr}",
        f"📦 {cs.get('total_orders', 0):,} 单 ｜ A {cs.get('A', 0):,} ｜ B {cs.get('B', 0):,} ｜ C {cs.get('C', 0):,} ｜ D {cs.get('D', 0):,}",
        f"🛡️ 风控拦截 {mm['risk']:,} 单（占 B {mm['risk'] / b_total * 100:.0f}%）· 🔧 技术失败 {mm['tech']:,} 单",
        "**🔧 技术失败 Top 5**\n\n" + "\n\n".join(f"- {r}（{c} 单）" for r, c in mm["top_tech"]) if mm["top_tech"] else "",
        "**📉 平台成功率后 5**\n\n" + "\n\n".join(_digest_kv_rows(mm["plat_low"])) if mm["plat_low"] else "",
        "**✈️ 航司成功率后 5**\n\n" + "\n\n".join(_digest_kv_rows(mm["air_low"])) if mm["air_low"] else "",
        "**👨‍💼 救场 Top 5**：" + " · ".join(f"{n} {c}" for n, c in mm["staff_top"]) if mm["staff_top"] else "",
        "⚠️ 口径说明：C 路径自 7/29 起包含辅营订单；D 路径含跨天历史快照。",
        f"🔗 [打开完整看板]({DASHBOARD_URL})",
    ]))
    fs_els = [{"tag": "div", "text": {"tag": "lark_md", "content": s.replace("\n\n", "\n")}}
              for s in [f"**📊 月报 · {mm['ym']}**",
                        f"**自动成功率 {mm['cur_rate']:.1f}%**{pr}\n📦 {cs.get('total_orders', 0):,} 单 ｜ A {cs.get('A', 0):,} ｜ B {cs.get('B', 0):,} ｜ C {cs.get('C', 0):,} ｜ D {cs.get('D', 0):,}",
                        f"🛡️ 风控拦截 {mm['risk']:,} 单（占 B {mm['risk'] / b_total * 100:.0f}%）· 🔧 技术失败 {mm['tech']:,} 单"] +
              ([ "**🔧 技术失败 Top 5**\n" + "\n".join(f"- {r}（{c} 单）" for r, c in mm["top_tech"]) ] if mm["top_tech"] else []) +
              ([ "**📉 平台成功率后 5**\n" + "\n".join(_digest_kv_rows(mm["plat_low"])) ] if mm["plat_low"] else []) +
              ([ "**✈️ 航司成功率后 5**\n" + "\n".join(_digest_kv_rows(mm["air_low"])) ] if mm["air_low"] else []) +
              ([ "**👨‍💼 救场 Top 5**：" + " · ".join(f"{n} {c}" for n, c in mm["staff_top"]) ] if mm["staff_top"] else []) +
              [ "⚠️ 口径说明：C 路径自 7/29 起包含辅营订单；D 路径含跨天历史快照。",
                f"🔗 [打开完整看板]({DASHBOARD_URL})" ]]
    return {
        "title": f"📊 出票月报 · {mm['ym']}",
        "markdown": md,
        "feishu_card": {
            "header": {"title": {"tag": "plain_text", "content": f"📊 出票月报 · {mm['ym']}"},
                       "template": "blue"},
            "elements": fs_els,
        },
    }


def build_pushable_report(date: str, period: str = "daily", prev_date: Optional[str] = None,
                          style: str = "brief") -> Dict:
    """构造可直接 push 的 report。period: daily / weekly / monthly。

    daily 默认 v9 一屏版（style=full 切回 v8 长模板备用）。
    """
    if period == "weekly":
        w = build_weekly(date)
        out = render_weekly(w)
        out["_raw"] = {"date": date, "period": "weekly", "generated_at": w["generated_at"]}
        out["action_url"] = DASHBOARD_URL
        return out
    if period == "monthly":
        mm = build_monthly(date[:7])
        out = render_monthly(mm)
        out["_raw"] = {"date": date, "period": "monthly", "generated_at": mm["generated_at"]}
        out["action_url"] = DASHBOARD_URL
        return out

    if style == "full":
        r = build_report(date)
        prefix = "⚠️ " if r.get("health", {}).get("warnings") else ""
        return {
            "title": f"{prefix}📊 自动化数据日报 · {r['date']}",
            "markdown": render_markdown(r),
            "dingtalk_card": render_dingtalk_actioncard(r),
            "feishu_card": render_feishu_card(r),
            "_raw": r,
        }
    b = build_brief(date)
    has_issue = bool(b["attention"]) or bool(b["health"].get("warnings"))
    return {
        "title": f"📊 出票日报 · {b['date']} {'⚠️' if has_issue else '✅'}",
        "markdown": render_brief_markdown(b),
        "feishu_card": render_brief_feishu(b),
        "action_url": DASHBOARD_URL,
        "_raw": b,
    }
