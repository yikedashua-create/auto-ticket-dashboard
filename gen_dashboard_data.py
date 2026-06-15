# -*- coding: utf-8 -*-
"""
dashboard_v5 数据生成器：按月聚合 + 维度下钻。
输出 dashboard_data.json（前端直接吃），结构：
  {
    "months": {
      "2026-05": { ... 全部聚合数据 ... },
      "2026-06": { ... }
    },
    "available_months": ["2026-05", "2026-06"],
    "current_month": "2026-05"
  }

用法：
  python gen_dashboard_data.py                 # 跑所有月（自动扫）
  python gen_dashboard_data.py --month 2026-06  # 只跑 6 月
  python gen_dashboard_data.py --month all      # 显式跑全部
"""
import pandas as pd
import os, re, json, glob, argparse
from datetime import datetime
from collections import defaultdict, Counter

DATA_DIR = r"C:\Users\admin\Desktop\出票总订单数据"
OUT_DIR = r"C:\Users\admin\.mavis\sessions\mvs_b0c94c62a23e4172a7ba820eb07f096a\workspace"

# 出票成功状态（用于路径切分）
# 关键：VALID_TICKET_FAIL 名字带"FAIL"但实际是"出票完成"（2026-06-13 用户指正）
# 关键：ticket 是航班管家国际的特殊"出票完成"状态码（2026-06-13 排查确认，订单状态.1=已完结，票号齐全）
SUCCESS_STATUSES = {"已出票", "TICKET_OK", "已完成", "出票完成", "ISSUE_FINISH", "VALID_TICKET_FAIL", "ticket"}
MANUAL_KEY = "手工政策转人工并派单"

# 留单状态：v7 起不再单独成 E 路径，直接进 D（兜底）
# 仅留作参照（订单状态.1=留单订单）
HOLD_STATUS = "留单订单"

# 字段标准化
AIRLINE_NAME = {
    "9C": "春秋", "SL": "狮航", "HO": "吉祥", "AQ": "九元",
    "AK": "亚航", "MF": "厦航", "HX": "港航", "VJ": "越捷",
    "FR": "瑞安", "5J": "宿务", "TR": "酷航", "JT": "狮航印尼",
    "PR": "菲航", "D7": "亚航X", "BX": "釜山", "7C": "济州",
}


def load_all():
    files = sorted([f for f in glob.glob(os.path.join(DATA_DIR, "*.xlsx"))
                    if not os.path.basename(f).startswith("~$")])
    print(f"[加载] {len(files)} 个文件")
    dfs = []
    for f in files:
        bn = os.path.basename(f)
        m = re.match(r"(\d{4}-\d{2}-\d{2})\.xlsx", bn)
        if not m:
            continue
        try:
            df = pd.read_excel(f, sheet_name=0, engine="openpyxl")
            df["_file_date"] = m.group(1)
            dfs.append(df)
        except Exception as e:
            print(f"  [{bn}] 失败: {e}")
    df_all = pd.concat(dfs, ignore_index=True)
    print(f"[加载] 总计 {len(df_all)} 单")
    return df_all


def classify(df):
    """v9 业务定义切分（用户 2026-06-14 修正）

    4 路径定义（v9）：
      C 最高优先级（且**绝对优先**，不计入自动化分析）：
          第一次失败原因含"手工政策转人工并派单" → 一律归 C
          （不管最终有没有被救回来、平台有没有出票，都不算自动化救场）
      A = OR
          (1) 平台状态 ∈ SUCCESS_STATUSES  AND  最后锁定人 = 空
          (2) 平台状态 ∈ {支付成功等待出票, 待出票, 未出票}
              AND  订单状态.1 ≠ 留单订单  AND  最后锁定人 = 空
      B = OR
          (1) 平台状态 ∈ SUCCESS_STATUSES  AND  最后锁定人 ≠ 空
          (2) 平台状态 ∈ {支付成功等待出票, 待出票, 未出票}
              AND  最后锁定人 ≠ 空
      D = 兜底（以上 A/B/C 都不满足的全部进 D，含留单订单）

    v9 vs v8 关键差异：C 路径不再被 A/B 抢走。
    v8 里"手工政策但被救回来"的订单会被算成 B，v9 全部强制归 C。
    """
    plat = df["平台状态"].fillna("").astype(str).str.strip()
    is_succ = plat.isin(SUCCESS_STATUSES)
    plat_pending = plat.isin({"支付成功等待出票", "待出票", "未出票"})
    lock = df["最后锁定人"].fillna("").astype(str).str.strip()
    lock_empty = lock == ""
    first_reason = df["第一次失败原因"].fillna("").astype(str).str.strip()
    is_pure_manual = first_reason.str.contains(MANUAL_KEY, regex=False)

    # 订单状态.1（区分留单订单）
    hold_status = df["订单状态.1"].fillna("").astype(str).str.strip() if "订单状态.1" in df.columns else pd.Series("", index=df.index)
    is_hold = hold_status == HOLD_STATUS

    path = pd.Series("D", index=df.index)  # 默认 D（兜底）

    # C：政策强制人工（最高优先级，**不计入自动化分析**，不参与 A/B 抢单）
    path[is_pure_manual] = "C"

    # A：OR 条件（**排除掉 C**，避免 C 被覆盖）
    not_c = ~is_pure_manual
    path[is_succ & lock_empty & not_c] = "A"                                       # (1) 成功 + 没人锁
    path[plat_pending & (~is_hold) & lock_empty & not_c] = "A"                     # (2) 等待出票 + 不是留单 + 没人锁

    # B：OR 条件（**排除掉 C**）
    path[is_succ & (~lock_empty) & not_c] = "B"                                    # (1) 成功 + 有人锁
    path[plat_pending & (~lock_empty) & not_c] = "B"                              # (2) 等待出票 + 有人锁

    # D：剩下的（兜底，含留单订单、真烂尾）
    # 留单订单会进 D 因为 plat_pending 命中但 is_hold=True 被 A 排除，B 也没有匹配
    # C 已经守住，不会被 A/B 抢

    df["path"] = path
    return df


def safe_num(series):
    return pd.to_numeric(series, errors="coerce").dropna()


# ============================================================
# 流程归类规则（v4 定版）
# 5 阶段：预定/支付/取票/回填/验真 + 1 兜底（流程未走完）
# 关键原则：取票包含中间态（出票中/待出票）
# 失信人/证件问题归到预定
# 验真只留"真验真异常"
# ============================================================
STAGE_RULES = [
    # ============ 预定（包含失信/证件/实名） ============
    (lambda s: "预定失败" in s or "预订失败" in s
              or "限制高消费" in s or "失信" in s
              or "5020" in s or "证件类型" in s
              or "证件有效期" in s or "实名认证" in s
              or "联系法院" in s, "预定-预订失败"),
    (lambda s: "询价" in s or "反采" in s, "预定-询价失败"),
    (lambda s: "停留超过20分钟" in s or "ERR803" in s or "ERR_RISK" in s, "预定-航司官网异常"),
    (lambda s: "锁单" in s or "锁定失败" in s, "预定-锁单失败"),
    (lambda s: "重复的行程" in s or "占座" in s, "预定-重复占座"),

    # ============ 支付 ============
    (lambda s: "支付失败" in s or "支付超时" in s or "支付时超时" in s
              or "支付时" in s, "支付-支付失败"),
    (lambda s: "Read timed out" in s or "SocketTimeout" in s
              or "Timeout connecting" in s or "502 Bad Gateway" in s
              or "Unexpected end of file" in s, "支付-网络超时"),
    (lambda s: "获取支付结果失败" in s, "支付-结果获取失败"),
    (lambda s: "issue card" in s.lower() or "bal not enough" in s.lower(), "支付-余额不足"),
    (lambda s: "支付验证" in s, "支付-验证失败"),

    # ============ 取票（全量：含中间态） ============
    (lambda s: "已支付,出票中" in s or "订单状态异常:出票中" in s
              or "出票中" in s, "取票-出票中"),
    (lambda s: "待出票" in s or "VALIDATING" in s
              or "验证中" in s, "取票-待出票"),
    (lambda s: "取票失败" in s and "订单已支付" in s, "取票-状态异常"),
    (lambda s: "取票失败" in s and "订单关闭" in s, "取票-订单已关闭"),
    (lambda s: "取票失败" in s and "订单状态为空" in s, "取票-状态为空"),
    (lambda s: "取票失败" in s and "ip异常" in s, "取票-IP异常"),
    (lambda s: "取票失败" in s and ("令牌" in s or "登录已过期" in s), "取票-凭证异常"),
    (lambda s: "取票失败" in s and ("JsonParseException" in s or "Unexpected char" in s), "取票-请求异常"),
    (lambda s: "取票失败" in s and "取消订单失败" in s, "取票-取消失败"),
    (lambda s: "取票失败" in s and "退票中" in s, "取票-退票中"),
    (lambda s: "取票失败" in s and "未查询到订单信息" in s, "取票-未查到订单"),
    (lambda s: "取票失败" in s, "取票-其他失败"),  # 兜底
    (lambda s: "暂时没有票号" in s or "无合法票号" in s, "取票-无票号"),
    (lambda s: "出票失败已退款" in s, "取票-已退款"),

    # ============ 回填 ============
    (lambda s: "原平台状态" in s or ("原平台" in s and "状态" in s), "回填-状态检测失败"),
    (lambda s: "状态校验失败" in s, "回填-状态校验失败"),
    (lambda s: "回填" in s, "回填-回填失败"),
    (lambda s: "出票费审核" in s, "回填-审核失败"),

    # ============ 验真（只留真验真） ============
    (lambda s: "验真" in s, "验真-验真异常"),

    # ============ 流程未走完（兜底大筐） ============
    (lambda s: "订单取消" in s, "未走完-订单取消"),
    (lambda s: "处理超时" in s and "订单" in s, "未走完-订单超时"),
    (lambda s: "辅营" in s, "未走完-辅营订单"),
    (lambda s: "订单已完结" in s, "未走完-订单已完结"),
    (lambda s: "未找到" in s and "出票规则" in s, "未走完-无出票规则"),
    (lambda s: s.strip() == "" or s.strip().lower() == "nan", "未走完-无文本"),
]

STAGE_META = {
    "预定": ("#5b8def", "🟦"),
    "支付": ("#f5a623", "🟧"),
    "取票": ("#ff5e5e", "🟥"),
    "回填": ("#00b894", "🟩"),
    "验真": ("#a259ff", "🟪"),
    "未走完": ("#7a8ba0", "⬜"),
}


def classify_stage(s):
    """按 5 阶段 + 兜底 归类失败原因，返回 (阶段, 子类)"""
    s = str(s or "").strip()
    for fn, cat in STAGE_RULES:
        if fn(s):
            stage = cat.split("-")[0]
            return stage, cat
    return "未走完", "未走完-未归类"


def build_month_data(df, month_label):
    """对单月数据跑所有聚合，返回该月的 dict。"""
    out = {"month": month_label}

    # ========== 1. summary ==========
    n = len(df)
    A = (df["path"] == "A").sum()
    B = (df["path"] == "B").sum()
    C = (df["path"] == "C").sum()
    D = (df["path"] == "D").sum()
    profit_all = safe_num(df["利润"])
    profit_pos = (profit_all > 0).sum()
    out["summary"] = {
        "month": month_label,
        "total_days": df["_file_date"].nunique(),
        "total_orders": int(n),
        "A": int(A), "B": int(B), "C": int(C), "D": int(D),
        "A_ratio": round(A/n*100, 2),
        "B_ratio": round(B/n*100, 2),
        "C_ratio": round(C/n*100, 2),
        "D_ratio": round(D/n*100, 2),
        "auto_coverage_rate": round((A+B)/n*100, 2),
        "auto_succ_rate": round(A/(A+B)*100, 2) if (A+B) else 0,
        "B_to_manual_rate": round(B/n*100, 2),
        "total_profit": round(float(profit_all.sum()), 2),
        "avg_profit": round(float(profit_all.mean()), 2) if len(profit_all) else 0,
        "profit_pos": int(profit_pos),
        "profit_pos_rate": round(profit_pos/len(profit_all)*100, 2) if len(profit_all) else 0,
    }

    print(f"  [{month_label} summary] {out['summary']}")

    # ========== 2. daily ==========
    daily = []
    for date, g in df.groupby("_file_date"):
        n = len(g)
        a = int((g["path"] == "A").sum())
        b = int((g["path"] == "B").sum())
        c = int((g["path"] == "C").sum())
        d = int((g["path"] == "D").sum())
        p = safe_num(g["利润"])
        psum = float(p.sum()) if len(p) else 0
        pavg = float(p.mean()) if len(p) else 0
        ppos = int((p > 0).sum()) if len(p) else 0
        daily.append({
            "date": date,
            "total": int(n), "A": a, "B": b, "C": c, "D": d,
            "auto_coverage_rate": round((a+b)/n*100, 2) if n else 0,
            "auto_succ_rate": round(a/(a+b)*100, 2) if (a+b) else 0,
            "B_ratio": round(b/n*100, 2) if n else 0,
            "C_ratio": round(c/n*100, 2) if n else 0,
            "D_ratio": round(d/n*100, 2) if n else 0,
            "profit_sum": round(psum, 2),
            "avg_profit": round(pavg, 2),
            "profit_pos": ppos,
            "profit_pos_rate": round(ppos/len(p)*100, 2) if len(p) else 0,
        })
    daily.sort(key=lambda x: x["date"])
    out["daily"] = daily

    # ========== 3. weekly ==========
    weekly_def = defaultdict(lambda: {"A": 0, "B": 0, "C": 0, "D": 0, "total": 0,
                                      "profit_sum": 0.0, "profit_cnt": 0, "days": []})
    for r in daily:
        dt = datetime.strptime(r["date"], "%Y-%m-%d")
        monday = dt - __import__("datetime").timedelta(days=dt.weekday())
        wk = monday.strftime("%Y-W%W")
        w = weekly_def[wk]
        w["A"] += r["A"]; w["B"] += r["B"]; w["C"] += r["C"]; w["D"] += r["D"]
        w["total"] += r["total"]; w["profit_sum"] += r["profit_sum"]
        w["days"].append(r["date"])
    weekly = []
    for wk in sorted(weekly_def.keys()):
        w = weekly_def[wk]
        weekly.append({
            "week": wk,
            "date_range": f"{min(w['days'])}~{max(w['days'])}",
            "total": w["total"], "A": w["A"], "B": w["B"], "C": w["C"], "D": w["D"],
            "auto_coverage_rate": round((w["A"]+w["B"])/w["total"]*100, 2),
            "auto_succ_rate": round(w["A"]/(w["A"]+w["B"])*100, 2) if (w["A"]+w["B"]) else 0,
            "A_ratio": round(w["A"]/w["total"]*100, 2),
            "B_ratio": round(w["B"]/w["total"]*100, 2),
            "profit_sum": round(w["profit_sum"], 2),
            "avg_profit": round(w["profit_sum"]/w["total"], 2) if w["total"] else 0,
        })
    out["weekly"] = weekly

    # ========== 4. 航司 维度 ==========
    airline = []
    if "航空公司列表" in df.columns:
        df["_airline"] = df["航空公司列表"].fillna("").astype(str).str.strip()
        for air, g in df.groupby("_airline"):
            if not air:
                continue
            n = len(g)
            a = int((g["path"] == "A").sum())
            b = int((g["path"] == "B").sum())
            c = int((g["path"] == "C").sum())
            d = int((g["path"] == "D").sum())
            p = safe_num(g["利润"])
            psum = float(p.sum()) if len(p) else 0
            pavg = float(p.mean()) if len(p) else 0
            airline.append({
                "airline": air,
                "name": AIRLINE_NAME.get(air, air),
                "total": n, "A": a, "B": b, "C": c, "D": d,
                "auto_coverage_rate": round((a+b)/n*100, 2) if n else 0,
                "auto_succ_rate": round(a/(a+b)*100, 2) if (a+b) else 0,
                "B_ratio": round(b/n*100, 2) if n else 0,
                "D_ratio": round(d/n*100, 2) if n else 0,
                "profit_sum": round(psum, 2),
                "avg_profit": round(pavg, 2),
            })
        airline.sort(key=lambda x: -x["total"])
    out["airline"] = airline

    # ========== 5. 平台 维度 ==========
    platform = []
    if "平台" in df.columns:
        df["_platform"] = df["平台"].fillna("").astype(str).str.strip()
        for pf, g in df.groupby("_platform"):
            if not pf:
                continue
            n = len(g)
            a = int((g["path"] == "A").sum())
            b = int((g["path"] == "B").sum())
            c = int((g["path"] == "C").sum())
            d = int((g["path"] == "D").sum())
            p = safe_num(g["利润"])
            psum = float(p.sum()) if len(p) else 0
            pavg = float(p.mean()) if len(p) else 0
            platform.append({
                "platform": pf, "total": n,
                "A": a, "B": b, "C": c, "D": d,
                "auto_coverage_rate": round((a+b)/n*100, 2) if n else 0,
                "auto_succ_rate": round(a/(a+b)*100, 2) if (a+b) else 0,
                "profit_sum": round(psum, 2),
                "avg_profit": round(pavg, 2),
            })
        platform.sort(key=lambda x: -x["total"])
    out["platform"] = platform

    # ========== 6. 采购渠道 维度 ==========
    channel = []
    if "采购渠道" in df.columns:
        df["_channel"] = df["采购渠道"].fillna("").astype(str).str.strip()
        for ch, g in df.groupby("_channel"):
            if not ch:
                continue
            n = len(g)
            a = int((g["path"] == "A").sum())
            b = int((g["path"] == "B").sum())
            c = int((g["path"] == "C").sum())
            d = int((g["path"] == "D").sum())
            p = safe_num(g["利润"])
            psum = float(p.sum()) if len(p) else 0
            pavg = float(p.mean()) if len(p) else 0
            channel.append({
                "channel": ch, "total": n,
                "A": a, "B": b, "C": c, "D": d,
                "auto_coverage_rate": round((a+b)/n*100, 2) if n else 0,
                "auto_succ_rate": round(a/(a+b)*100, 2) if (a+b) else 0,
                "profit_sum": round(psum, 2),
                "avg_profit": round(pavg, 2),
            })
        channel.sort(key=lambda x: -x["total"])
    out["channel"] = channel

    # ========== 7. 锁定人（员工）绩效 ==========
    staff = []
    lock_col = df["最后锁定人"].fillna("").astype(str).str.strip()
    locked_df = df[lock_col != ""].copy()
    locked_df["_staff"] = lock_col[lock_col != ""]
    for staff_name, g in locked_df.groupby("_staff"):
        n = len(g)
        b = int((g["path"] == "B").sum())
        c = int((g["path"] == "C").sum())
        d = int((g["path"] == "D").sum())
        succ = b  # B 路径 = 救场成功的
        p = safe_num(g["利润"])
        psum = float(p.sum()) if len(p) else 0
        pavg = float(p.mean()) if len(p) else 0
        ppos = int((p > 0).sum()) if len(p) else 0
        staff.append({
            "name": staff_name, "total": n,
            "B": b, "C": c, "D": d,
            "succ": succ,  # 救场单数
            "succ_rate": round(b/n*100, 2) if n else 0,
            "profit_sum": round(psum, 2),
            "avg_profit": round(pavg, 2),
            "profit_pos_rate": round(ppos/len(p)*100, 2) if len(p) else 0,
        })
    staff.sort(key=lambda x: -x["total"])
    out["staff"] = staff

    # ========== 8. 失败原因（路径B + 路径D 合并） ==========
    # v5 更新：用「第一次失败原因」字段（根因分析视角），fallback 到 失败原因
    fail_reasons_b = Counter()
    fail_reasons_d = Counter()
    for _, r in df.iterrows():
        p = r["path"]
        reason = str(r.get("第一次失败原因", "") or r.get("失败原因", "") or "").strip()
        if not reason:
            reason = "(无)"
        if p == "B":
            fail_reasons_b[reason] += 1
        elif p == "D":
            fail_reasons_d[reason] += 1

    # 简化：取前 60 字
    def short(s, n=60):
        s = s.replace("\n", " ").replace("\r", " ")
        return s[:n] + ("..." if len(s) > n else "")

    out["fail_reasons_B"] = [
        {"reason": short(k, 80), "full": short(k, 200), "count": v}
        for k, v in fail_reasons_b.most_common(30)
    ]
    out["fail_reasons_D"] = [
        {"reason": short(k, 80), "full": short(k, 200), "count": v}
        for k, v in fail_reasons_d.most_common(30)
    ]

    # ========== 8.5 流程归因（v4 定版）==========
    # 阶段分布、子类分布、每日阶段堆叠
    stage_counter = Counter()      # 阶段 -> 单数
    sub_counter = Counter()        # 阶段-子类 -> 单数
    stage_path_counter = Counter() # (阶段, path) -> 单数
    daily_stage = defaultdict(Counter)  # date -> {阶段 -> 单数}
    daily_sub = defaultdict(Counter)    # date -> {子类 -> 单数}

    for _, r in df.iterrows():
        if r["path"] not in ("B", "D"):
            continue
        stage, sub = classify_stage(r.get("第一次失败原因", "") or r.get("失败原因", ""))
        stage_counter[stage] += 1
        sub_counter[sub] += 1
        stage_path_counter[(stage, r["path"])] += 1
        d = r.get("_file_date", "")
        if d:
            daily_stage[d][stage] += 1
            daily_sub[d][sub] += 1

    # 阶段汇总（按定义顺序）
    stage_list = ["预定", "支付", "取票", "回填", "验真", "未走完"]
    stage_distribution = []
    total_fail = sum(stage_counter.values())
    for st in stage_list:
        n = stage_counter.get(st, 0)
        pct = round(n / total_fail * 100, 2) if total_fail else 0
        color, _ = STAGE_META.get(st, ("#7a8ba0", ""))
        # 按路径拆
        b_n = stage_path_counter.get((st, "B"), 0)
        d_n = stage_path_counter.get((st, "D"), 0)
        stage_distribution.append({
            "stage": st,
            "total": n,
            "B": b_n,
            "D": d_n,
            "pct": pct,
            "color": color,
        })

    # 子类明细（按阶段排序）
    sub_list = []
    # 阶段内排序：B+D 总量倒序
    for st in stage_list:
        for sub, n in sub_counter.most_common():
            if sub.startswith(st + "-"):
                color, _ = STAGE_META.get(st, ("#7a8ba0", ""))
                pct = round(n / total_fail * 100, 2) if total_fail else 0
                sub_list.append({
                    "category": sub,
                    "stage": st,
                    "count": n,
                    "pct": pct,
                    "color": color,
                })

    # 每日阶段堆叠
    daily_stage_list = []
    for d in sorted(daily_stage.keys()):
        row = {"date": d, "total": sum(daily_stage[d].values())}
        for st in stage_list:
            row[st] = daily_stage[d].get(st, 0)
        daily_stage_list.append(row)

    # 每日子类堆叠（用于"取票失败每天分布"）
    daily_sub_list = []
    for d in sorted(daily_sub.keys()):
        row = {"date": d}
        for sub, n in daily_sub[d].most_common():
            row[sub] = n
        daily_sub_list.append(row)

    out["stage_distribution"] = stage_distribution
    out["stage_subcategory"] = sub_list
    out["daily_stage"] = daily_stage_list
    out["daily_subcategory"] = daily_sub_list
    out["total_fail_orders"] = total_fail

    # ========== 9. 平台状态分布（D 路径细节） ==========
    plat_status_dist = Counter()
    for _, r in df.iterrows():
        if r["path"] == "D":
            ps = str(r.get("平台状态", "") or "").strip()
            plat_status_dist[ps] += 1
    out["plat_status_D"] = [{"status": k, "count": v} for k, v in plat_status_dist.most_common()]

    # ========== 9.5. 4 路径全月利润（精确） ==========
    profit_path = {"A": [], "B": [], "C": [], "D": []}
    for _, r in df.iterrows():
        p = r.get("利润")
        if pd.isna(p):
            continue
        try:
            v = float(p)
            if v != v:  # NaN check
                continue
            profit_path[r["path"]].append(v)
        except (ValueError, TypeError):
            pass
    out["path_profit"] = []
    for p in ["A", "B", "C", "D"]:
        arr = profit_path[p]
        s_sum = float(sum(arr)) if arr else 0
        s_avg = float(sum(arr) / len(arr)) if arr else 0
        out["path_profit"].append({
            "name": p, "sum": round(s_sum, 2),
            "avg": round(s_avg, 2),
            "count": len(arr),
        })

    # ========== 10. 关键洞察 ==========
    insights = []
    # 第一周 vs 最后一周
    first7 = daily[:7]
    last7 = daily[-7:]
    if first7 and last7:
        cov_first = sum(d["auto_coverage_rate"] for d in first7) / len(first7)
        cov_last = sum(d["auto_coverage_rate"] for d in last7) / len(last7)
        b_first = sum(d["B_ratio"] for d in first7) / len(first7)
        b_last = sum(d["B_ratio"] for d in last7) / len(last7)
        insights.append({
            "title": "📉 自动覆盖率持续下滑",
            "level": "danger",
            "text": f"第一周 {cov_first:.1f}% → 最后一周 {cov_last:.1f}%（{cov_last-cov_first:+.1f}%），自动流程覆盖在恶化。",
        })
        insights.append({
            "title": "📈 B 路径占比飙升",
            "level": "warning",
            "text": f"第一周 {b_first:.1f}% → 最后一周 {b_last:.1f}%（{b_last-b_first:+.1f}%），更多订单需要人工救场。",
        })
        insights.append({
            "title": "💸 月度累计亏损",
            "level": "danger",
            "text": f"{month_label} 累计利润 {out['summary']['total_profit']:+,.0f} 元（单均 {out['summary']['avg_profit']:+.2f}），整体亏损。",
        })
    # 9C 异常
    nine_c = next((a for a in airline if a["airline"] == "9C"), None)
    if nine_c:
        insights.append({
            "title": "🚨 9C 航司异常集中",
            "level": "danger",
            "text": f"9C 单量 {nine_c['total']:,}（占 {nine_c['total']/out['summary']['total_orders']*100:.1f}%），D 路径 {nine_c['D']} 单，D 占比 {nine_c['D_ratio']:.1f}%。",
        })
    out["insights"] = insights

    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--month", default="all",
                        help="指定月份 2026-05 / 2026-06，或 'all' 跑全部")
    args = parser.parse_args()

    df_all = load_all()
    df_all = classify(df_all)
    print(f"[切分] A={(df_all['path']=='A').sum()}, B={(df_all['path']=='B').sum()}, "
          f"C={(df_all['path']=='C').sum()}, D={(df_all['path']=='D').sum()}\n")

    # 按月分桶
    df_all["_month"] = df_all["_file_date"].str[:7]  # "2026-05-01" -> "2026-05"
    available_months = sorted(df_all["_month"].unique().tolist())
    print(f"[月份] 发现 {len(available_months)} 个月份：{available_months}")

    # 决定跑哪些月
    if args.month == "all":
        target_months = available_months
    else:
        if args.month not in available_months:
            print(f"[错误] 月份 {args.month} 在数据中不存在（已有：{available_months}）")
            return
        target_months = [args.month]

    # 逐月聚合
    months_data = {}
    for m in target_months:
        df_m = df_all[df_all["_month"] == m].copy()
        print(f"\n[跑] {m} · {len(df_m):,} 单 · {df_m['_file_date'].nunique()} 天")
        months_data[m] = build_month_data(df_m, m)

        # 按日再聚合一次（v6 增强：日份切换时所有详细数据可用）
        # 单日数据精简版：只保留前 5 维度 + 失败原因 + 平台状态 + 阶段分布
        daily_detail = {}
        for date in sorted(df_m["_file_date"].unique()):
            df_day = df_m[df_m["_file_date"] == date].copy()
            if len(df_day) == 0:
                continue
            day_data = build_month_data(df_day, date)
            # 精简：去掉单日用不到的字段
            day_data.pop("weekly", None)
            day_data.pop("insights", None)
            # 精简：航司/平台/渠道/员工 只保留前 5（单日 Top5 足够看）
            for k in ["airline", "platform", "channel", "staff"]:
                if k in day_data and isinstance(day_data[k], list):
                    day_data[k] = day_data[k][:5]
            # 精简：失败原因 Top 10
            for k in ["fail_reasons_B", "fail_reasons_D"]:
                if k in day_data and isinstance(day_data[k], list):
                    day_data[k] = day_data[k][:10]
            # 精简：subcategory Top 10
            if "stage_subcategory" in day_data and isinstance(day_data["stage_subcategory"], list):
                day_data["stage_subcategory"] = day_data["stage_subcategory"][:10]
            # plat_status_D 全留（量小）
            daily_detail[date] = day_data
        months_data[m]["daily_detail"] = daily_detail
        print(f"  [daily_detail] {len(daily_detail)} 天")

    # ========== 写入 ==========
    out_path = os.path.join(OUT_DIR, "dashboard_data.json")
    final = {
        "available_months": available_months,
        "current_month": target_months[-1],  # 默认显示最后（最新）月
        "months": months_data,
        # 兼容旧版（顶层还有默认月数据，前端可平滑切换）
        **months_data[target_months[-1]],
    }
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
    print(f"\n[输出] {out_path} ({os.path.getsize(out_path)/1024:.1f} KB)")
    print(f"[统计] 月份={target_months}，"
          f"总单数={sum(months_data[m]['summary']['total_orders'] for m in target_months):,}")


if __name__ == "__main__":
    main()
