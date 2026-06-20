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
    "MM": "乐桃", "NH": "全日空", "JL": "日航", "TR": "酷航",
    "KE": "大韩", "OZ": "韩亚", "TG": "泰航", "FD": "泰亚航",
    "BE": "英伦", "BA": "英航", "AF": "法航", "LH": "汉莎",
    "KL": "荷航", "EY": "阿提哈德", "EK": "阿联酋", "QR": "卡塔尔",
    "SQ": "新航", "CX": "国泰", "BR": "长荣", "CI": "华航",
    "CA": "国航", "CZ": "南航", "MU": "东航", "HU": "海航",
    "FM": "上航", "ZH": "深航", "3U": "川航", "GS": "华夏",
}


# ============================================================
# 第一次失败原因 - 数据清洗规则（v1，2026-06-17）
# ============================================================
# 1. A 路径订单（自动出票成功）不参与失败根因分析
# 2. B/D 路径订单：优先用 第一次失败原因，fallback 到 失败原因
# 3. 文本清洗：去邮箱/时间戳/订单号/null/技术字段/末尾 -xxx-xxx 模式
# 4. 归一化：第N次取票失败 → 取票失败；反采同程ITravel → 反采同程
# 5. 族聚合：按业务族归并（询价/亏损/取票/支付/平台状态/辅营/证件）
# ============================================================

# 文本清洗规则（按顺序：先去噪音，再归一化）
REASON_CLEANUP_RULES = [
    # 1) 去邮箱
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", ""),
    # 2) 去时间戳 (2026-05-30 12:34:56 等)
    (r"\d{4}[-/]\d{1,2}[-/]\d{1,2}([ T]\d{1,2}:\d{2}(:\d{2})?)?", ""),
    # 3) 去 10+ 位订单 ID
    (r"\b\d{10,}\b", ""),
    # 4) 去 trip_cid / user_id / order_id / null / undefined / NaN / nan
    (r"(?:trip_cid|user_id|order_id|userid|orderid|ip_addr|request_id)[:\s]*", ""),
    (r"\b(?:null|undefined|NaN|nan)\b", ""),
    # 5) 去尾部 -xxx-xxx-xxx 模式（如 -null-null, -aabbcc）
    (r"\s*-\s*[a-zA-Z0-9_-]+(?:\s*-\s*[a-zA-Z0-9_-]+)*\s*$", ""),
    # 6) 去 {} 空括号
    (r"\{\s*\}", ""),
    # 7) 归一化：第N次取票失败 → 取票失败
    (r"第\s*\d+\s*次取票失败", "取票失败"),
    (r"第\s*null\s*次取票失败", "取票失败"),
    # 8) 归一化：渠道差异（反采同程ITravel → 反采同程）
    (r"反采同程\s*ITravel", "反采同程"),
    (r"反采同程ITravel", "反采同程"),
    # 9) 多个连续空格/标点压成一个
    (r"[\s,，;；]+", " "),
    # 10) 去首尾标点
    (r"^[\s,，;：:]+|[\s,，;：:]+$", ""),
]


def clean_reason_text(reason: str) -> str:
    """对单条 reason 文本应用清洗规则。返回清洗后文本；清洗后为空则返回空串。"""
    if reason is None:
        return ""
    s = str(reason).strip()
    if not s or s.lower() in ("nan", "none", "null", ""):
        return ""
    for pattern, replacement in REASON_CLEANUP_RULES:
        s = re.sub(pattern, replacement, s)
    s = s.strip()
    return s


def get_root_reason(row) -> str:
    """获取清洗后的根因文本。

    优先级：
      1) 第一次失败原因 字段（清洗后）
      2) fallback 到 失败原因 字段（清洗后）
      3) 仍然为空 → 返回 ""
    """
    r1 = clean_reason_text(row.get("第一次失败原因", ""))
    if r1:
        return r1
    r2 = clean_reason_text(row.get("失败原因", ""))
    return r2


# v10 族聚合规则（按出票环节划分 + 子分类）
# 设计原则：失败根因按出票环节定位问题（预定/支付/取票/回填/验真/平台/人工/系统）
# 命名规则：「环节 - 子分类」，子分类是开放扩展的
# 注：清洗后的 reason 已经去掉了「第N次」前缀和" 渠道名"后缀，所以匹配主要看 reason 主体
REASON_FAMILY_RULES = [
    # === 人工环节（最优先，按 reason 主体关键字匹配） ===
    (r"辅营", "人工环节-辅营订单"),
    # 重复订单（两个变体："重复订单" / "订单存在重复"，归同一族）
    (r"重复订单", "人工环节-重复订单"),
    (r"订单存在重复", "人工环节-重复订单"),
    # 订单取消（D 路径大头）
    (r"订单取消", "人工环节-订单取消"),
    # 补抓单/锁单失败/处理器异常转人工
    (r"补抓单|锁单失败|处理器执行异常转人工", "人工环节-补抓单转人工"),

    # === 系统环节（横切关注点，任何环节超时/系统故障都归这里）===
    # 订单处理超时
    (r"订单处理超时", "系统环节-订单处理超时"),
    # Token 失败（接口鉴权失败）
    (r"获取token失败", "系统环节-Token失败"),
    # 定时维护窗口
    (r"daily maintenance window", "系统环节-定时维护"),
    # 卡余额不足
    (r"issue card error|CNH bal not enough", "系统环节-卡余额不足"),
    # 接口异常（航旅纵横 LY0502）
    (r"LY0502101022|调用接口异常", "系统环节-接口异常"),

    # === 预定失败（细分：预定异常 / 未匹配自动规则 / 验价 / 询价 / 亏损 / 证件 / 渠道账号 / 价格不符 / 利润过大 / 订单已完结）===
    # 证件异常（细分下：解析乘客信息/证件有效期异常）
    (r"解析乘客信息异常|解析.*证件", "预定失败-证件异常"),
    # 渠道账号为空
    (r"获取.*账号为空", "预定失败-渠道账号为空"),
    # 价格不符（自家价格）
    (r"自家价格", "预定失败-价格不符"),
    # 利润过大（春秋/Atlas等渠道，利润大于阈值，语义同亏损大于）
    (r"利润大于", "预定失败-利润过大"),
    # 订单已完结（无法继续操作）
    (r"订单已完结", "预定失败-订单已完结"),
    # 询价（询价失败 / 询价异常）— 已包含渠道前缀
    (r"反采同程.*询价失败", "预定失败-询价失败-反采同程"),
    (r"反采同程.*询价", "预定失败-询价异常-反采同程"),
    (r"反采携程海外.*询价失败", "预定失败-询价失败-反采携程海外"),
    (r"反采携程海外.*询价", "预定失败-询价异常-反采携程海外"),
    (r"航班管家.*询价失败", "预定失败-询价失败-航班管家"),
    (r"航班管家.*询价", "预定失败-询价异常-航班管家"),
    (r".*询价失败", "预定失败-询价失败-其他渠道"),
    # 政策亏损（保留渠道）
    (r"反采同程.*亏损大于", "预定失败-亏损过大-反采同程"),
    (r"反采携程海外.*亏损大于", "预定失败-亏损过大-反采携程海外"),
    (r"反采同程.*亏损", "预定失败-政策亏损-反采同程"),
    (r"反采携程海外.*亏损", "预定失败-政策亏损-反采携程海外"),
    (r".*亏损大于", "预定失败-亏损过大-其他渠道"),
    # 验价失败
    (r"验价失败", "预定失败-验价失败"),
    # 未匹配自动规则（多个变体）
    (r"没有匹配到自动出票规则|未找到出票规则|初筛没有匹配出票规则|未匹配自动规则", "预定失败-未匹配规则"),
    # 预定失败-其他（兜底型预定失败，预约异常/系统忙等）
    (r"预定失败", "预定失败-预定异常"),

    # === 支付失败（细分：通用支付失败 / 订单校验失败）===
    (r"订单校验失败", "支付失败-订单校验失败"),
    (r"支付失败", "支付失败-支付异常"),

    # === 取票失败（细分：通用取票失败，留扩展位）===
    (r"取票失败", "取票失败-取票异常"),

    # === 验真失败（细分：异常/失败，留扩展位）===
    (r"验真异常", "验真失败-验真异常"),
    (r"验真失败", "验真失败-验真失败"),

    # === 回填失败（主动回填动作失败）===
    (r"回填原平台失败", "回填失败-主动回填"),
    (r"回填失败", "回填失败-主动回填"),

    # === 平台失败（回填成功后，下一步操作/监测）===
    # 出票费审核失败（回填成功后的下一步操作）
    (r"出票费审核失败", "平台失败-出票费审核"),
    # 原平台状态监测（监测动作发现问题）
    (r"原平台状态监测", "平台失败-状态监测"),
    (r"原平台状态", "平台失败-状态监测"),
]


def family_reason(reason: str) -> str:
    """v11：把单条清洗后的 reason 归到「环节 - 子分类」。
    如果没有任何规则匹配，返回 '其他失败-兜底'。
    空 reason 在 D 路径很常见（票已出但无失败原因记录），归'其他失败-空原因'。"""
    if not reason or reason == "(无)":
        return "其他失败-空原因"
    for pattern, family in REASON_FAMILY_RULES:
        if re.search(pattern, reason):
            return family
    return "其他失败-兜底"


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
    # v6 更新（2026-06-17）：
    #   1) A 路径订单不参与失败根因分析（它们没失败）
    #   2) B/D 路径：先 第一次失败原因，fallback 到 失败原因
    #   3) 应用文本清洗规则（去邮箱/时间戳/订单号/null/技术字段）
    #   4) 族聚合：把相似根因归到业务族（"取票失败"/"询价失败"/"亏损"等）
    fail_reasons_b = Counter()
    fail_reasons_d = Counter()
    # 族级聚合（B/D 分别）
    fail_families_b = Counter()
    fail_families_d = Counter()
    for _, r in df.iterrows():
        p = r["path"]
        # A 路径不参与失败根因分析
        if p == "A":
            continue
        # 清洗 + fallback
        cleaned = get_root_reason(r)
        if not cleaned:
            cleaned = "(无)"  # 真没原因（B/D 路径才会到这里）
        if p == "B":
            fail_reasons_b[cleaned] += 1
            fam = family_reason(cleaned) or "(无)"
            fail_families_b[fam] += 1
        elif p == "D":
            fail_reasons_d[cleaned] += 1
            fam = family_reason(cleaned) or "(无)"
            fail_families_d[fam] += 1

    # 简化：取前 60 字
    def short(s, n=60):
        s = s.replace("\n", " ").replace("\r", " ")
        return s[:n] + ("..." if len(s) > n else "")

    # v12 修复：fail_reasons 预计算 family 字段（前端不再每次调用 getFamily）
    # 之前 B 路径 1526 项 × 37 条正则 = 5.6 万次正则匹配 → 点族行卡顿
    # 修法：后端一次性归族，存到 reason 的 family 字段；前端 O(1) Map 查询
    out["fail_reasons_B"] = [
        {"reason": short(k, 80), "full": k, "count": v, "family": family_reason(k) or "(无)"}
        for k, v in fail_reasons_b.most_common()  # 全量
    ]
    out["fail_reasons_D"] = [
        {"reason": short(k, 80), "full": k, "count": v, "family": family_reason(k) or "(无)"}
        for k, v in fail_reasons_d.most_common()  # 全量
    ]
    # 族级 Top（看板默认展示，Top 15 足够，前端限制显示 Top 10）
    out["fail_families_B"] = [
        {"family": k, "count": v}
        for k, v in fail_families_b.most_common()
    ]
    out["fail_families_D"] = [
        {"family": k, "count": v}
        for k, v in fail_families_d.most_common()
    ]

    # ========== Top 10 失败根因下钻数据（5 维度）==========
    # 为 Top 10 根因预计算：平台分布 / 航司分布 / 航司×平台交叉 / 日期趋势 / 员工救场
    # 用 groupby 按 reason 一次性 group 出所有数据，避免再二次匹配
    def build_drilldown(target_path, top_n=10):
        """为 Top N 失败根因生成 5 维度下钻数据。

        不用 reason_counter 二次匹配（可能因 strip/类型问题导致 0 匹配），
        直接从 df 拿该 path 的所有订单，groupby("第一次失败原因") 后
        按 counter 排序取 Top N。
        """
        # 该路径的所有订单
        path_df = df[df["path"] == target_path].copy()
        if path_df.empty:
            return []
        # 计算每个 reason 的 count
        reason_full = path_df["第一次失败原因"].fillna("").astype(str).str.strip()
        reason_full_nonempty = reason_full[reason_full != ""]
        cnt = reason_full_nonempty.value_counts().head(top_n)
        drills = []
        for reason_text, top_count in cnt.items():
            # 用 numpy 数组按位置匹配（避免索引对齐问题）
            sub = path_df[reason_full == reason_text]
            n_sub = len(sub)
            if n_sub == 0:
                # fallback：substring 匹配
                sub = path_df[reason_full.str.contains(reason_text, regex=False, na=False)]
                n_sub = len(sub)
            if n_sub == 0:
                continue

            # 1. 平台分布
            plat_dist = sub["平台"].value_counts().head(10)
            platform_dist = [{"name": k, "count": int(v)} for k, v in plat_dist.items()]

            # 2. 航司分布（注意：真正的航司代码在"航空公司列表"列，"航司编码信息"是乘客名）
            # "航空公司列表"是逗号分隔的字符串（如 "9C, HO"），需要 explode 拆分
            air_col = "航空公司列表" if "航空公司列表" in sub.columns else ("航司编码信息" if "航司编码信息" in sub.columns else "航司")
            # 拆分多航司 + 统计
            air_exploded = sub[air_col].fillna("").astype(str).str.strip()
            air_exploded = air_exploded[air_exploded != ""].str.split(r"[,,;；\s]+", regex=True).explode()
            air_exploded = air_exploded[air_exploded.str.strip() != ""]
            air_dist = air_exploded.value_counts().head(10)
            airline_dist = []
            for k, v in air_dist.items():
                k_str = str(k).strip()
                cn = AIRLINE_NAME.get(k_str, k_str)
                airline_dist.append({"code": k_str, "name": cn, "count": int(v)})

            # 3. 航司 × 平台 交叉（同样需要拆分多航司）
            cross_dict = {}
            for _, r in sub.iterrows():
                air_raw = str(r.get(air_col, "")).strip()
                if not air_raw:
                    air_list = ["未识别"]
                else:
                    air_list = [a.strip() for a in re.split(r"[,,;；\s]+", air_raw) if a.strip()]
                    if not air_list:
                        air_list = ["未识别"]
                plat = str(r.get("平台", "")).strip() or "未识别"
                for air in air_list:
                    air_cn = AIRLINE_NAME.get(air, air)
                    key = (air_cn, plat)
                    cross_dict[key] = cross_dict.get(key, 0) + 1
            airlines_set = sorted({k[0] for k in cross_dict.keys()})
            platforms_set = sorted({k[1] for k in cross_dict.keys()})
            cross = {
                "airlines": airlines_set,
                "platforms": platforms_set,
                "data": [[cross_dict.get((a, p), 0) for p in platforms_set] for a in airlines_set],
            }

            # 4. 日期趋势
            daily_count = sub["_file_date"].value_counts().sort_index()
            date_trend = [{"date": str(d), "count": int(c)} for d, c in daily_count.items()]

            # 5. 员工救场
            staff_series = sub["最后锁定人"].fillna("").astype(str).str.strip()
            staff_series = staff_series[staff_series != ""]
            staff_counts = staff_series.value_counts().head(10)
            staff_dist = [{"name": k, "count": int(v)} for k, v in staff_counts.items()]
            rescued_count = int(staff_series.shape[0])
            rescue_rate = round(rescued_count / n_sub * 100, 2) if n_sub else 0

            drills.append({
                "reason": short(reason_text, 80),
                "total": int(n_sub),
                "top_count": int(top_count),
                "platform_dist": platform_dist,
                "airline_dist": airline_dist,
                "cross": cross,
                "date_trend": date_trend,
                "staff_dist": staff_dist,
                "rescued_count": rescued_count,
                "rescue_rate": rescue_rate,
            })
        return drills

    out["fail_drill_B"] = build_drilldown("B", top_n=10)
    out["fail_drill_D"] = build_drilldown("D", top_n=10)

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
    from datetime import datetime, timezone, timedelta
    bj_tz = timezone(timedelta(hours=8))
    final = {
        "generated_at": datetime.now(bj_tz).strftime("%Y-%m-%d %H:%M:%S"),
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
