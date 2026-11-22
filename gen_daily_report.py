# -*- coding: utf-8 -*-
"""
自动化数据汇报生成器
====================
从看板数据自动汇集，生成一份可直接下载 / 打印 / 导出 PDF 的单文件离线 HTML。
不推送、不提交、不改动任何看板数据文件。

数据来源（默认优先线上仓库，只读、不切换分支、不改工作区数据文件）：
  origin/main:dashboard_data.json  -> 当前月份 / 数据生成时间
  origin/main:monthly/<YYYY-MM>.json -> daily_detail[日期]（按日全量聚合，含平台/航司/渠道）
  origin/main:targets.json         -> 全自动成功率月度目标
  取不到线上时自动回退本地同名文件；--local 可强制只用本地。

用法：
  python gen_daily_report.py                          # 自动同步线上并取最新可用日期
  python gen_daily_report.py --date 2026-11-20       # 指定日期
  python gen_daily_report.py --local                 # 离线，用本地数据
  python gen_daily_report.py --no-fetch --out xxx.html
"""
import argparse
import html as _html
import json
import os
import subprocess
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))

# 4 路径配色（浅色汇报版）
C_A = "#059669"   # A 全自动成功
C_B = "#DC2626"   # B 全自动失败
C_C = "#EA580C"   # C 订单转人工
C_D = "#94A3B8"   # D 订单处理中
BLUE = "#2563EB"


def esc(s):
    return _html.escape(str(s), quote=True)


def num(v):
    return f"{int(round(float(v or 0))):,}"


def pct(v, d=2):
    return f"{float(v or 0):.{d}f}%"


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def weekday_cn(date_str):
    w = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    return w[datetime.strptime(date_str, "%Y-%m-%d").weekday()]


def git_fetch(timeout=90):
    """只读同步远程分支；不改变工作区，不 push、不提交。"""
    try:
        subprocess.run(["git", "-C", BASE, "fetch", "origin", "main"],
                       capture_output=True, timeout=timeout)
    except Exception:
        pass


def git_read(path, timeout=30):
    """从 origin/main 只读取一个 JSON 文件；失败返回 None 由调用方回退本地。"""
    try:
        r = subprocess.run(["git", "-C", BASE, "show", "origin/main:" + path],
                           capture_output=True, timeout=timeout)
        if r.returncode != 0:
            return None
        return json.loads(r.stdout.decode("utf-8"))
    except Exception:
        return None


def resolve(month, date, use_remote=True, do_fetch=True):
    if use_remote and do_fetch:
        git_fetch()
    main = (git_read("dashboard_data.json") if use_remote else None) or \
        load_json(os.path.join(BASE, "dashboard_data.json"))
    ym = month or main.get("current_month")

    md, source = None, "本地 monthly"
    if use_remote:
        md = git_read(f"monthly/{ym}.json")
        if md is not None:
            source = "线上看板按日明细"
    if md is None:
        md = load_json(os.path.join(BASE, "monthly", ym + ".json"))

    dd = md.get("daily_detail") or {}
    if not dd:
        raise SystemExit(f"monthly/{ym}.json 里没有 daily_detail")
    d = date or max(dd.keys())
    if d not in dd:
        raise SystemExit(f"{ym} 没有 {d} 的按日明细，可用日期：{', '.join(sorted(dd.keys()))}")
    return ym, d, dd[d], source, main.get("generated_at", ""), md


def _sum_field(rows, key):
    return sum(int(r.get(key) or 0) for r in rows if isinstance(r, dict))


def _safe_div(a, b, digits=2):
    return round(float(a) / float(b) * 100, digits) if b else 0.0


def merge_days(days, start, end):
    """把 [start, end] 区间内各天的 daily_detail 合并成一份“天”结构。

    口径：订单/航段/A/B/C/D/利润等计数相加；所有比率字段按合并后的计数重算，
    绝不取各天比率的平均。平台/航司/渠道按名称(代码)合并，逐小时与环节按桶相加，
    失败原因按 reason+family 合并计数。
    """
    days = sorted(days, key=lambda x: x.get("date", ""))
    if not days:
        return None
    n = len(days)

    # ---- summary ----
    tot = sum(int((x.get("summary") or {}).get("total_orders") or 0) for x in days)
    seg = sum(int((x.get("summary") or {}).get("total_segments") or 0) for x in days)
    A = sum(int((x.get("summary") or {}).get("A") or 0) for x in days)
    B = sum(int((x.get("summary") or {}).get("B") or 0) for x in days)
    C = sum(int((x.get("summary") or {}).get("C") or 0) for x in days)
    D = sum(int((x.get("summary") or {}).get("D") or 0) for x in days)
    auto = A + B
    profit = sum(float((x.get("summary") or {}).get("total_profit") or 0) for x in days)
    profit_pos = sum(int((x.get("summary") or {}).get("profit_pos") or 0) for x in days)
    summary = {
        "month": f"{start}~{end}", "total_days": n,
        "total_orders": tot, "total_segments": seg,
        "A": A, "B": B, "C": C, "D": D,
        "A_ratio": _safe_div(A, tot), "B_ratio": _safe_div(B, tot),
        "C_ratio": _safe_div(C, tot), "D_ratio": _safe_div(D, tot),
        "auto_coverage_rate": _safe_div(auto, tot),
        "auto_succ_rate": _safe_div(A, auto),
        "B_to_manual_rate": _safe_div(B, auto),
        "total_profit": round(profit, 2),
        "avg_profit": round(profit / tot, 2) if tot else 0.0,
        "profit_pos": profit_pos,
        "profit_pos_rate": _safe_div(profit_pos, tot),
    }

    # ---- 逐小时：按 hour 相加 A/B/C/D/total ----
    hour_map = {}
    for x in days:
        ht = (x.get("summary") or {}).get("hourly_today") or {}
        for r in (ht.get("data") or []):
            h = int(r.get("hour") or 0)
            agg = hour_map.setdefault(h, {"hour": h, "total": 0, "A": 0, "B": 0, "C": 0, "D": 0})
            for k in ("total", "A", "B", "C", "D"):
                agg[k] += int(r.get(k) or 0)
    hourly_data = []
    for h in sorted(hour_map):
        r = hour_map[h]
        a, b, t = r["A"], r["B"], r["total"]
        r["auto_coverage_rate"] = _safe_div(a + b, t)
        r["auto_succ_rate"] = _safe_div(a, a + b)
        hourly_data.append(r)
    summary["hourly_today"] = {"date": f"{start}~{end}", "data": hourly_data}

    # ---- 平台 / 航司 / 渠道：按名称合并 ----
    def merge_named(key_name, label):
        mp = {}
        for x in days:
            for row in (x.get(key_name) or []):
                if not isinstance(row, dict):
                    continue
                name = str(row.get(label) or "")
                if not name:
                    continue
                agg = mp.setdefault(name, {"total": 0, "A": 0, "B": 0, "C": 0, "D": 0,
                                           "profit_sum": 0.0})
                for k in ("total", "A", "B", "C", "D"):
                    agg[k] += int(row.get(k) or 0)
                agg["profit_sum"] += float(row.get("profit_sum") or 0)
                # 航司/渠道的名称映射保留首天
                if "name" in row and "name" not in agg:
                    agg["name"] = row["name"]
                if "tier" in row and "tier" not in agg:
                    agg["tier"] = row["tier"]
        out = []
        for name, agg in mp.items():
            agg[label] = name
            a, b, t = agg["A"], agg["B"], agg["total"]
            agg["auto_succ_rate"] = _safe_div(a, a + b)
            agg["auto_coverage_rate"] = _safe_div(a + b, t)
            agg["avg_profit"] = round(agg["profit_sum"] / t, 2) if t else 0.0
            agg["profit_sum"] = round(agg["profit_sum"], 2)
            out.append(agg)
        return out

    platform = merge_named("platform", "platform")
    airline = merge_named("airline", "airline")
    channel = merge_named("channel", "channel")
    airline.sort(key=lambda r: -r["total"])
    channel.sort(key=lambda r: -r["total"])

    # ---- hourly_stage / hourly_stage_B：按 hour 合并 9 环节（B+D 合计 / 纯 B） ----
    def merge_hourly_stage(key):
        hs_map = {}
        for x in days:
            for r in (x.get(key) or []):
                h = int(r.get("hour") or 0)
                agg = hs_map.setdefault(h, {"hour": h})
                for s in STAGES8:
                    agg[s] = int(agg.get(s) or 0) + int(r.get(s) or 0)
                agg["total"] = sum(int(agg.get(s) or 0) for s in STAGES8)
        return [hs_map[h] for h in sorted(hs_map)]

    hourly_stage = merge_hourly_stage("hourly_stage")
    hourly_stage_b = merge_hourly_stage("hourly_stage_B")

    # ---- fail_reasons_B / D：按 reason+family 合并 count ----
    # 保留 full / near_reason：07 章显示名优先用 near_reason（看板就近名），
    # 其次 full（完整文本），不能只留截断的 reason。
    def merge_reasons(key):
        mp = {}
        for x in days:
            for r in (x.get(key) or []):
                k = (str(r.get("reason") or ""), str(r.get("family") or ""))
                if k not in mp:
                    mp[k] = {
                        "reason": k[0], "family": k[1], "count": 0,
                        "full": str(r.get("full") or ""),
                        "near_reason": str(r.get("near_reason") or ""),
                    }
                mp[k]["count"] += int(r.get("count") or 0)
                # 若同一 reason 在不同天补出了就近名，取非空的那份
                if not mp[k].get("near_reason") and r.get("near_reason"):
                    mp[k]["near_reason"] = str(r.get("near_reason"))
        return list(mp.values())

    fail_b = merge_reasons("fail_reasons_B")
    fail_d = merge_reasons("fail_reasons_D")

    # ---- staff：区间内有锁定记录的人名并集（人均摊分用） ----
    staff_names = set()
    for x in days:
        for r in (x.get("staff") or []):
            if isinstance(r, dict) and r.get("name"):
                staff_names.add(r["name"])

    return {
        "month": days[0].get("month"), "date": f"{start}~{end}",
        "summary": summary,
        "daily": [{"date": f"{start}~{end}", "total": tot, "A": A, "B": B, "C": C, "D": D,
                   "total_segments": seg, "auto_succ_rate": summary["auto_succ_rate"]}],
        "platform": platform, "airline": airline, "channel": channel,
        "staff": [{"name": nm} for nm in staff_names],
        "hourly_stage": hourly_stage, "hourly_stage_B": hourly_stage_b,
        "fail_reasons_B": fail_b, "fail_reasons_D": fail_d,
    }


def target_of(ym, override=None, use_remote=True):
    if override is not None:
        return float(override)
    t = (git_read("targets.json") if use_remote else None) or \
        load_json(os.path.join(BASE, "targets.json"))
    return float(t.get(ym) or t.get("_default") or 83)


CSS = r"""
*{box-sizing:border-box}
body{margin:0;background:radial-gradient(ellipse 85% 55% at 50% 0%,#FCFDFF 0%,#F3F6FB 52%,#EDF1F8 100%);color:#1B2430;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Hiragino Sans GB",Arial,sans-serif;font-size:14px;line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:32px 22px 60px}
.head{padding:32px 30px 24px;background:linear-gradient(170deg,#FDFFFF 0%,#F6FAFF 100%);border:1px solid #DDE6F2;border-radius:18px;border-top:4px solid #2563EB;text-align:center;box-shadow:0 6px 24px rgba(30,64,175,.07)}
.head h1{margin:0;font-size:31px;font-weight:800;letter-spacing:4px;color:#0F172A;line-height:1.45}
.head .rule{width:64px;height:4px;border-radius:4px;margin:12px auto 16px;background:linear-gradient(90deg,#2563EB,#38BDF8,#2563EB)}
.head .meta{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 8px;color:#5A6675;font-size:11.5px;line-height:1.5}
.head .meta .mi{white-space:nowrap;background:#fff;border:1px solid #DCE6F2;border-radius:999px;padding:5px 12px;box-shadow:0 1px 3px rgba(30,64,175,.04)}
.head .meta .mi b{color:#334155;font-weight:700}
.boxes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:18px 0 22px}
.box{position:relative;overflow:hidden;border:1px solid #E2E9F2;border-radius:16px;padding:16px 18px 13px;min-width:0;text-align:left;box-shadow:0 5px 20px rgba(30,64,175,.06)}
.box:nth-child(1){background:linear-gradient(160deg,#FFFFFF 55%,#F4F9FF)}
.box:nth-child(2){background:linear-gradient(160deg,#FFFFFF 55%,#F1FBF6)}
.box:nth-child(3){background:linear-gradient(160deg,#FFFFFF 55%,#FFF9F1)}
.box:before{content:"";position:absolute;left:0;right:0;top:0;height:3px}
.box:nth-child(1):before{background:linear-gradient(90deg,#2563EB,#60A5FA)}
.box:nth-child(2):before{background:linear-gradient(90deg,#059669,#34D399)}
.box:nth-child(3):before{background:linear-gradient(90deg,#F59E0B,#FBBF24)}
.box .bt{font-size:11.5px;font-weight:700;color:#475569;letter-spacing:1.5px;margin-bottom:6px}
.box .pair{display:grid;grid-template-columns:1fr;gap:0}
.box .cell{display:grid;grid-template-columns:1fr 1fr;align-items:center;padding:5px 0;min-height:47px;border-bottom:1px dashed #E6EDF6}
.box .cell:last-child{border-bottom:none}
.box .pk{font-size:11.5px;color:#5A6675;white-space:nowrap;text-align:left}
.box .pk .sub{display:block;font-size:10.5px;line-height:1.3;color:#94A3B8;margin-top:1px}
.box .pv{font-size:27px;font-weight:800;line-height:1.2;letter-spacing:-.6px;margin:0;font-variant-numeric:tabular-nums;text-align:center}
.box .pv.blue{color:#2563EB}.box .pv.green{color:#059669}.box .pv.orange{color:#EA580C}.box .pv.red{color:#DC2626}
.box .pf{margin-top:8px;padding-top:7px;border-top:1px dashed #EDF2F8;font-size:10.5px;color:#94A3B8;min-height:18px;line-height:1.6;text-align:left}
.sec{background:#fff;border:1px solid #E2E9F2;border-radius:16px;padding:26px 30px 28px;margin-bottom:20px;box-shadow:0 5px 22px rgba(20,38,70,.055)}
.sec-h{display:flex;align-items:baseline;gap:12px;margin-bottom:6px;flex-wrap:wrap;padding-bottom:11px;border-bottom:1px solid #EEF2F7}
.sec-n{font-size:12px;font-weight:800;color:#fff;background:linear-gradient(135deg,#2563EB,#3B82F6);padding:4px 10px;border-radius:7px;white-space:nowrap;box-shadow:0 2px 6px rgba(37,99,235,.2)}
.sec-h h2{margin:0;font-size:20px;font-weight:800;letter-spacing:.2px;color:#16202E}
.sec-h .sectip{font-size:11.5px;color:#8A95A5;margin-left:auto}
.lead{margin:12px 0 18px;padding:13px 17px;background:linear-gradient(90deg,#EFF6FF,#F8FBFF);border-left:3px solid #3B82F6;border-radius:0 8px 8px 0;font-size:14px;line-height:1.85;color:#334155}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:11.5px;color:#5A6675;margin:0 0 14px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}
.plat{border:1px solid #EAF0F7;border-radius:11px;padding:14px 18px 12px;margin-bottom:10px;break-inside:avoid;background:linear-gradient(180deg,#FFFFFF,#FCFDFE)}
.plat:hover{border-color:#CFDEF0}
.plat-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:9px}
.plat-nm{font-size:14px;font-weight:700;color:#1B2430}
.plat-tot{font-size:12px;color:#5A6675}
.plat-rate{margin-left:auto;font-size:12px;color:#5A6675;white-space:nowrap}
.plat-rate b{font-size:16px;font-variant-numeric:tabular-nums;margin-left:4px}
.stack{display:flex;width:100%;height:18px;border-radius:6px;overflow:hidden;background:#F1F4F8;box-shadow:inset 0 1px 2px rgba(15,23,42,.05)}
.stack i{display:block;height:100%}
.plat-lg{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:#8A95A5;margin-top:8px}
.plat-lg span i{display:inline-block;width:7px;height:7px;border-radius:2px;margin-right:5px}
.badge{display:inline-block;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:10px;border:1px solid;white-space:nowrap;margin-left:6px}
.badge.ok{color:#059669;border-color:#A7F3D0;background:#ECFDF5}
.badge.mid{color:#2563EB;border-color:#BFDBFE;background:#EFF6FF}
.badge.bad{color:#DC2626;border-color:#FECACA;background:#FEF2F2}
.badge.na{color:#64748B;border-color:#E2E8F0;background:#F8FAFC}
.rank{display:grid;grid-template-columns:170px 1fr 68px 116px 76px;align-items:center;gap:12px;padding:5px 0;border-bottom:1px solid #F1F4F8;break-inside:avoid}
.rank:last-child{border-bottom:none}
.rank-nm{font-size:12.5px;font-weight:700;color:#1B2430;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.rank-nm .code{display:inline-block;min-width:30px;color:#2563EB;font-weight:800}
.rank-bar{position:relative;height:16px;background:#EEF2F7;border-radius:5px;overflow:visible}
.rank-bar .fill{position:absolute;left:0;top:0;height:100%;border-radius:5px;box-shadow:inset 0 -2px 4px rgba(15,23,42,.06)}
.rank-bar .target{position:absolute;top:-3px;height:22px;width:0;border-left:2px dashed #64748B;z-index:2}
.rank-pct{font-size:12.5px;font-weight:800;text-align:right;font-variant-numeric:tabular-nums}
.rank-cnt{font-size:11.5px;color:#8A95A5;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.rank-bg{text-align:right}
table{width:100%;border-collapse:collapse;margin:16px 0 4px;font-size:12.5px;line-height:1.5}
th{background:linear-gradient(180deg,#F6F9FC,#EEF3F9);color:#1E293B;font-weight:700;text-align:left;padding:9px 14px;border-bottom:1px solid #D5DFEB;white-space:nowrap}
td{padding:8px 14px;border-bottom:1px solid #EFF2F6;color:#334155}
tr:last-child td{border-bottom:none}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:nth-child(even){background:#FAFBFD}
.foot{background:linear-gradient(180deg,#FFFFFF,#FBFCFE);border:1px solid #E2E9F2;border-radius:13px;padding:18px 24px;font-size:12px;color:#5A6675;line-height:1.9;box-shadow:0 4px 18px rgba(20,38,70,.05)}
.foot h3{margin:0 0 8px;font-size:13.5px;color:#1B2430}
.foot ul{margin:0;padding-left:20px}
/* 04 逐小时趋势 */
.shifts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0 16px}
.shift{border:1px solid #E5E9F0;border-left:3px solid #94A3B8;border-radius:10px;padding:11px 14px;min-width:0}
.shift.overnight{border-left-color:#7C3AED;background:linear-gradient(135deg,#FBFAFF,#FFFFFF)}
.shift.day{border-left-color:#2563EB;background:linear-gradient(135deg,#F7FAFF,#FFFFFF)}
.shift.night{border-left-color:#EA580C;background:linear-gradient(135deg,#FFFCF7,#FFFFFF)}
.shift .sh{display:flex;align-items:baseline;gap:7px;white-space:nowrap}
.shift .sh b{font-size:12.5px;color:#1B2430}.shift .sh span{font-size:10.5px;color:#94A3B8}
.shift .sm{display:flex;justify-content:space-between;gap:8px;margin-top:6px;font-size:11.5px;color:#5A6675}
.shift .sm em{font-style:normal;font-weight:800;color:#1B2430;font-variant-numeric:tabular-nums}
.chartbox{position:relative;border:1px solid #EAF0F7;border-radius:11px;padding:10px 10px 3px;background:linear-gradient(180deg,#FFFFFF,#FCFDFE)}
.chartbox svg{display:block;width:100%;height:auto}
.hovertip{position:absolute;display:none;pointer-events:none;z-index:30;min-width:216px;background:#fff;border:1px solid #CBD5E1;border-radius:10px;padding:9px 12px;box-shadow:0 10px 26px rgba(15,23,42,.16);font-size:11.5px;line-height:1.65;color:#334155}
.hovertip .th{font-weight:800;font-size:12.5px;color:#16202E}
.hovertip .tt{color:#5A6675;margin-bottom:5px}
.hovertip .tr{display:flex;justify-content:space-between;gap:16px}
.hovertip .tr i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}
.hovertip .tr b{font-variant-numeric:tabular-nums}
.hovertip .sep{height:1px;background:#E2E8F0;margin:6px 0}
.hovertip .sum b{color:#059669;font-size:12.5px}
/* 05-07 报错 */
.stage-lg{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:#5A6675;margin:0 0 12px}
.stage-lg span i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}
.barsvg{display:block;width:100%;height:auto}
.errgrp{border:1px solid #EEF1F6;border-radius:10px;padding:12px 16px 10px;margin-bottom:10px;break-inside:avoid}
.errgrp-h{display:flex;align-items:baseline;gap:9px;margin-bottom:7px;flex-wrap:wrap}
.errgrp-h b{font-size:13px;color:#1B2430}
.errgrp-h .dot{display:inline-block;width:9px;height:9px;border-radius:2px}
.errgrp-h span{font-size:11px;color:#94A3B8}
.errrow{display:grid;grid-template-columns:1fr 62px 70px 62px;align-items:center;gap:10px;padding:4px 0;border-bottom:1px solid #F4F6F9;font-size:11.5px}
.errrow:last-child{border-bottom:none}
.errrow .erm{color:#334155;overflow:visible;white-space:normal;word-break:break-word;line-height:1.55}
.errrow .erb{height:9px;background:#F1F4F8;border-radius:3px;overflow:hidden}
.errrow .erb i{display:block;height:100%;border-radius:3px}
.errrow .ern,.errrow .erp{text-align:right;color:#5A6675;font-variant-numeric:tabular-nums}
.errrow .erp{color:#94A3B8}
.hit5{cursor:pointer}
@media(max-width:900px){.boxes{grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.box{padding:11px 10px 9px}.box .bt{font-size:10px;letter-spacing:1px;margin-bottom:4px}.box .cell{min-height:42px}.box .pv{font-size:18px}.box .pk{font-size:10px}.box .pk .sub{font-size:10px}.box .pf{font-size:9.5px;min-height:16px}.head{padding:22px 14px 20px}.head h1{font-size:24px;letter-spacing:1.5px}.head .meta{font-size:10.5px}.head .meta .mi{padding:3px 8px}.rank{grid-template-columns:130px 1fr 62px 70px}.rank .rank-bg{display:none}.wrap{padding:14px}.shifts{gap:7px}.shift{padding:8px 9px}.shift .sh b{font-size:11px}.shift .sh span{font-size:9px}.shift .sm{font-size:10px}}
@media print{body{background:#fff}.wrap{max-width:none;padding:0}.head,.sec,.foot,.box{break-inside:avoid;box-shadow:none;border-color:#D9DEE6}@page{margin:12mm}}
/* ===== 视觉精修层（不改 DOM / 数据 / 口径） ===== */
:root{--ui-line:#E7EDF5;--ui-mute:#93A1B3;--ui-shadow:0 6px 22px rgba(24,48,90,.08);--ui-shadow-hover:0 13px 32px rgba(24,48,90,.14)}
.head .meta .mi{padding:6px 13px}
.head h1{color:#0B1220}
.boxes{gap:18px}
.box{padding:18px 20px 15px;border-radius:16px;box-shadow:var(--ui-shadow);transition:transform .18s ease,box-shadow .18s ease}
.box:hover{transform:translateY(-3px);box-shadow:var(--ui-shadow-hover)}
.box .bt{display:flex;align-items:center;gap:7px;font-size:11.5px;letter-spacing:1.4px;color:#475569}
.box .bt:before{content:"";width:7px;height:7px;border-radius:50%;flex:none}
.box:nth-child(1) .bt:before{background:#2563EB}
.box:nth-child(2) .bt:before{background:#059669}
.box:nth-child(3) .bt:before{background:#EA580C}
.box .pv{font-size:30px;letter-spacing:-1px}
.box .cell{min-height:50px}
.sec{padding:26px 30px 30px;border-radius:16px;box-shadow:var(--ui-shadow);margin-bottom:22px}
.sec-h{padding-bottom:13px}
.sec-n{padding:5px 11px;border-radius:8px;letter-spacing:.5px;box-shadow:0 3px 8px rgba(37,99,235,.28)}
.sec-h h2{font-size:21px;letter-spacing:.3px}
.lead{background:linear-gradient(90deg,#EEF5FF 0%,#F7FBFF 72%,#FFFFFF 100%);border-left-width:4px;padding:14px 18px;line-height:1.9}
.legend,.stage-lg{gap:8px 10px}
.legend span:not(:only-child),.stage-lg span:not(:last-child){display:inline-flex;align-items:center;gap:5px;background:#F8FAFD;border:1px solid var(--ui-line);border-radius:7px;padding:3px 10px;font-size:11px;line-height:1.5;color:#475569}
.legend i,.stage-lg span i{margin-right:0;flex:none}
.legend span:only-child,.stage-lg>span:last-child{border:none;background:none;padding-left:2px;color:var(--ui-mute)}
.plat{padding:15px 18px 13px;border-radius:12px}
.plat-nm{font-size:14.5px}
.stack{height:22px;border-radius:7px}
.plat-rate b{font-size:17px}
.shift{border-radius:11px;padding:13px 16px}
.shift .sm em{font-size:13px}
.rank{padding:6px 0}
.rank-bar{height:18px;border-radius:6px}
.rank-bar .fill{border-radius:6px}
.rank-nm{font-size:12.5px}
th{padding:11px 14px;letter-spacing:.3px}
td{padding:10px 14px}
tbody tr:hover{background:#F4F8FE}
.hovertip{border-radius:12px;box-shadow:0 14px 36px rgba(15,23,42,.2);padding:11px 14px}
@media(max-width:900px){.box .pv{font-size:19px}.box .bt{font-size:10px;gap:5px}.box .bt:before{width:6px;height:6px}.legend span:not(:only-child),.stage-lg span:not(:last-child){padding:2px 7px;font-size:10px}}
"""


def rate_class(rate, target):
    if rate >= target:
        return "ok", "达标", f"+{rate - target:.2f}%", C_A
    if rate >= 50:
        return "mid", "中等", f"差 {target - rate:.2f}%", BLUE
    return "bad", "待改", f"差 {target - rate:.2f}%", C_B


def build_rank_rows(items, target, name_key):
    """参考看板「航司/渠道自动化成功率」：按成功率降序、目标线、达标徽章、订单量。
    全量展示；A+B=0 的项没有自动流程分母，单独标「未走自动」，不当成 0% 失败。
    """
    ordered = sorted(items, key=lambda x: -(float(x.get("auto_succ_rate") or 0)))
    rows = []
    ok_n = 0
    for x in ordered:
        rate = float(x.get("auto_succ_rate") or 0)
        auto_base = float(x.get("A") or 0) + float(x.get("B") or 0)
        if auto_base == 0:
            cls, txt, diff, color = "na", "未走自动", "", C_D
        elif rate == 0:
            cls, txt, diff, color = "na", "无自动成功", "", C_D
        else:
            cls, txt, diff, color = rate_class(rate, target)
            if cls == "ok":
                ok_n += 1
        name = esc(x[name_key])
        nm = f'<span class="code">{name}</span>' if name_key == "airline" else f'<span>{name}</span>'
        rows.append(
            '<div class="rank">'
            f'<div class="rank-nm" title="{name}">{nm}</div>'
            f'<div class="rank-bar"><i class="target" style="left:{target:.2f}%"></i>'
            f'<i class="fill" style="width:{rate:.2f}%;background:{color}"></i></div>'
            f'<div class="rank-pct" style="color:{color}">{pct(rate)}</div>'
            f'<div class="rank-bg"><span class="badge {cls}">{(txt + " " + diff).strip()}</span></div>'
            f'<div class="rank-cnt">{num(x["total"])} 单</div>'
            '</div>'
        )
    return "".join(rows), ok_n


def build_platform_cards(items, target, total):
    items = sorted(items, key=lambda x: -float(x.get("total") or 0))
    cards = []
    for i, x in enumerate(items, 1):
        tot = float(x.get("total") or 0)
        rate = float(x.get("auto_succ_rate") or 0)
        _, _, _, color = rate_class(rate, target)
        segs = [("A 全自动成功", x.get("A"), C_A), ("B 全自动失败", x.get("B"), C_B),
                ("C 订单转人工", x.get("C"), C_C), ("D 订单处理中", x.get("D"), C_D)]
        stack = "".join(
            f'<i style="width:{(float(v or 0) / tot * 100) if tot else 0:.3f}%;background:{c}" title="{k} {num(v)} 单"></i>'
            for k, v, c in segs
        )
        lg = "".join(
            f'<span><i style="background:{c}"></i>{k} {num(v)}</span>' for k, v, c in segs
        )
        cards.append(
            '<div class="plat">'
            f'<div class="plat-h"><span class="plat-nm">{i}. {esc(x["platform"])}</span>'
            f'<span class="plat-tot">{num(tot)} 单 · 占全量 {pct(tot / total * 100 if total else 0)}</span>'
            f'<span class="plat-rate">全自动成功率<b style="color:{color}">{pct(rate)}</b></span></div>'
            f'<div class="stack">{stack}</div>'
            f'<div class="plat-lg">{lg}</div>'
            '</div>'
        )
    return "".join(cards), items


def build_table(items):
    rows = []
    for x in items:
        rows.append(
            f'<tr><td>{esc(x["platform"])}</td><td class="n">{num(x["total"])}</td>'
            f'<td class="n">{pct(x.get("auto_succ_rate"))}</td><td class="n">{num(x.get("A"))}</td>'
            f'<td class="n">{num(x.get("B"))}</td></tr>'
        )
    return (
        '<table><thead><tr><th>平台</th><th class="n">订单数</th><th class="n">全自动成功率</th>'
        '<th class="n">全自动成功数</th><th class="n">全自动失败数</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table>'
    )


def lead_platform(items, target, total):
    top = items[0]
    ok = sum(1 for x in items if float(x.get("auto_succ_rate") or 0) >= target)
    large = [x for x in items if int(x.get("total") or 0) >= 100] or items
    best = max(large, key=lambda x: float(x.get("auto_succ_rate") or 0))
    return (f'共 {len(items)} 个平台、{num(total)} 单。单量最大的是{esc(top["platform"])}，'
            f'{num(top["total"])} 单、全自动成功率 {pct(top.get("auto_succ_rate"))}；'
            f'在订单量 100 单以上的平台里，{esc(best["platform"])}成功率最高 '
            f'{pct(best.get("auto_succ_rate"))}（{num(best["total"])} 单）。'
            f'按 {pct(target, 0)} 的目标看，{len(items)} 个平台里 {ok} 个达标。')


def lead_rank(items, target, label, unit, ok_n):
    big = max(items, key=lambda x: float(x.get("total") or 0))
    name = esc(big.get("channel") or big.get("airline"))
    return (f'{label}共 {len(items)} {unit}，按全自动成功率从高到低排列，'
            f'{ok_n} {unit}达到 {pct(target, 0)} 目标；'
            f'单量最大的是{name}，{num(big["total"])} 单、成功率 {pct(big.get("auto_succ_rate"))}。')


# 8 大环节，与看板 getStageColor / groupByStage 的 STAGE_ORDER 对齐
# 前 8 项＝业务环节，末项「其他环节」＝兜底（family 未匹配到任何环节的单）
STAGES8 = ("人工环节", "系统环节", "预定环节", "支付环节", "取票环节",
           "验真环节", "回填环节", "平台环节", "其他环节")
STAGE8_MAIN = STAGES8[:8]
STAGE8_COLOR = {
    "人工环节": "#FF6B9D", "系统环节": "#FFD93D", "预定环节": "#FF4757",
    "支付环节": "#FF6348", "取票环节": "#FFA502", "验真环节": "#9C88FF",
    "回填环节": "#70A1FF", "平台环节": "#5F27CD", "其他环节": "#A0B4CC",
}
FALLBACK_STAGE = "未细分报错"
FALLBACK_COLOR = "#94A3B8"
# 线上缺 hour×环节 字段时，用逐小时真实的 B/D 两段拆分代替全灰单柱（都是数据里真实存在的口径）
FB_B = "全自动失败"
FB_D = "订单处理中"

# 05 环形图配色（按占比降序分配，预览定稿）
DONUT_COLORS = ("#FF4757", "#FF6348", "#FFD93D", "#FFA502", "#FF6B9D", "#A0B4CC",
                "#60A5FA", "#A78BFA", "#34D399")

DONUT_JS = r"""
(function(){
  var box=document.getElementById('donutBox'), tip=document.getElementById('donutTip'), metaEl=document.getElementById('donutMeta');
  if(!box||!tip||!metaEl) return;
  var meta; try{meta=JSON.parse(metaEl.textContent);}catch(e){return;}
  var rows=meta.rows||[], colors=meta.colors||{}, total=meta.total||0;
  var f=function(n){return Number(n||0).toLocaleString('zh-CN');};
  function show(i,e){
    var r=rows[i]; if(!r) return;
    var share=total?(r.n/total*100).toFixed(2):'0.00';
    tip.innerHTML='<div class="th"><i style="display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;background:'+(colors[r.s]||'#94A3B8')+'"></i>'+r.s+'</div>'+
      '<div class="tt">报错 <b>'+f(r.n)+'</b> 单 · 占'+meta.pw+' <b>'+share+'%</b></div>'+
      '<div class="sep"></div><div class="sum">'+meta.pw+'报错合计 <b>'+f(total)+'</b> 单</div>';
    tip.style.display='block';
    var br=box.getBoundingClientRect();
    var x=e.clientX-br.left+14, y=e.clientY-br.top+10;
    if(x+tip.offsetWidth>br.width-6) x=e.clientX-br.left-tip.offsetWidth-14;
    if(x<6) x=6;
    if(y+tip.offsetHeight>br.height-6) y=br.height-tip.offsetHeight-6;
    if(y<6) y=6;
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function hide(){tip.style.display='none';}
  Array.prototype.forEach.call(box.querySelectorAll('.hit5'),function(el){
    el.addEventListener('mousemove',function(e){show(parseInt(el.getAttribute('data-i'),10),e);});
    el.addEventListener('mouseleave',hide);
  });
})();
"""


def stage8_of_family(fam):
    """把 family（如「预定环节-亏损过大-其他渠道」）归到 8 大环节之一。"""
    fam = str(fam or "")
    for s in STAGES8:
        if fam.startswith(s):
            return s
    return "其他环节"


def stage8_counts(reasons):
    """统计一组 fail_reason 记录里各环节的报错单数。"""
    c = {s: 0 for s in STAGES8}
    for x in reasons or []:
        c[stage8_of_family(x.get("family"))] += int(x.get("count") or 0)
    return c


def _esc_text(s):
    """报错原因是自由文本：转义、压空白，完整显示不截断（CSS 允许换行）。"""
    s = " ".join(str(s or "").split())
    if not s or s == "(无)":
        return "（无失败原因）"
    return esc(s)


def build_daily_stage_section(ctx):
    """05 每日各环节报错：环形图看当天/区间报错的环节构成，悬浮看明细。口径=B（全自动失败），与看板失败原因排行一致。"""
    reasons = ctx.get("fail_b") or []
    counts = stage8_counts(reasons)
    pairs = [(s, int(counts.get(s) or 0)) for s in STAGES8]
    total = sum(n for _, n in pairs)
    if not total:
        return ""
    d = ctx["date"]
    pw = ctx.get("period_word", "当天")
    # 按报错量降序，只为非零环节画块/图例；0 值环节只在结论里说明
    ranked = sorted([(s, n) for s, n in pairs if n], key=lambda x: -x[1])
    colors = {s: DONUT_COLORS[i % len(DONUT_COLORS)] for i, (s, _) in enumerate(ranked)}

    cx, cy, r, sw = 250, 160, 108, 46
    circ = 2 * 3.141592653589793 * r
    out = [f'<svg class="barsvg" viewBox="0 0 1080 330" xmlns="http://www.w3.org/2000/svg" '
           f'role="img" aria-label="各环节报错占比环形图">']
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="#EEF2F7" stroke-width="{sw}"/>')
    offset = 0.0
    for i, (s, n) in enumerate(ranked):
        seg = n / total * circ
        out.append(f'<g class="hit5" data-i="{i}">'
                   f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{colors[s]}" stroke-width="{sw}" '
                   f'stroke-dasharray="{seg:.2f} {circ - seg:.2f}" stroke-dashoffset="{-offset:.2f}" '
                   f'transform="rotate(-90 {cx} {cy})"/></g>')
        offset += seg
    out.append(f'<text x="{cx}" y="154" text-anchor="middle" font-size="40" font-weight="800" fill="#16202E">{num(total)}</text>')
    out.append(f'<text x="{cx}" y="180" text-anchor="middle" font-size="13" fill="#8A95A5">单报错</text>')
    out.append('<text x="500" y="24" font-size="11.5" font-weight="700" fill="#8A95A5">按报错量排序</text>')
    maxn = ranked[0][1] or 1
    for i, (s, n) in enumerate(ranked):
        y = 32 + i * 40
        share = n / total * 100
        bw = 250 * n / maxn
        out.append(f'<g class="hit5" data-i="{i}">'
                   f'<rect x="500" y="{y}" width="12" height="12" rx="3" fill="{colors[s]}"/>'
                   f'<text x="520" y="{y + 13}" font-size="13" font-weight="700" fill="#1B2430">{esc(s)}</text>'
                   f'<text x="520" y="{y + 31}" font-size="10.5" fill="#94A3B8">占比 {share:.1f}%</text>'
                   f'<rect x="650" y="{y + 10}" width="250" height="8" rx="4" fill="#F1F4F8"/>'
                   f'<rect x="650" y="{y + 10}" width="{bw:.1f}" height="8" rx="4" fill="{colors[s]}"/>'
                   f'<text x="914" y="{y + 18}" font-size="14" font-weight="800" fill="#1B2430">{num(n)}</text>'
                   '</g>')
    out.append('</svg>')

    top3 = ranked[:3]
    zeros = [s for s, n in pairs if not n]
    lead = (f'{esc(d)} {pw}全自动失败 {num(total)} 单，'
            f'按失败原因归到 {len(pairs)} 类环节（口径同看板「失败原因排行」B 路径）。报错最多的是 '
            + '、'.join(f'{s} {num(n)} 单（{pct(n / total * 100)}）' for s, n in top3) + '。')
    if zeros:
        lead += f'{pw}有 {len(zeros)} 个环节没有报错：' + '、'.join(zeros) + '。'
    meta = {"rows": [{"s": s, "n": n} for s, n in ranked], "colors": colors,
            "total": total, "pw": pw}
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        '<div class="sec"><div class="sec-h"><span class="sec-n">05</span><h2>每日各环节报错</h2>'
        f'<span class="sectip">{esc(d)} · 共 {num(total)} 单 · 环形占比图，悬浮看明细</span></div>'
        f'<div class="lead">{lead}</div>'
        f'<div class="chartbox" id="donutBox">{"".join(out)}<div class="hovertip" id="donutTip"></div></div>'
        f'<script type="application/json" id="donutMeta">{meta_json}</script><script>{DONUT_JS}</script>'
        '</div>'
    )


def build_stage_stacked_svg(rows, series, colors):
    """06 堆叠柱状图：横轴 24 小时，每小时一根柱按环节堆叠，纵轴报错单数。

    折线方案在环节多（9 条）且多数小时只有 0～3 单时，线全贴底相互遮挡；
    堆叠柱把每个环节变成柱内一段色块，互不遮挡，且能同时看出小时总量与环节构成。
    """
    W, H = 1080, 380
    L, R, T, B = 52, 18, 46, 42
    pw, ph = W - L - R, H - T - B
    step = pw / 24
    bw = step * 0.66
    X = lambda i: L + (i + 0.5) * step
    maxv = max((r["total"] for r in rows), default=1) or 1
    top = max(20, ((maxv + 19) // 20) * 20)
    Y = lambda v: T + ph - (max(0, min(top, v)) / top * ph)

    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="24 小时各环节报错堆叠柱状图" xmlns="http://www.w3.org/2000/svg">']
    for a, b, col, lab in ((0, 8, "#F5F3FF", "通宵班 00:00–08:00"),
                           (8, 18, "#EFF6FF", "白班 08:00–18:00"),
                           (18, 24, "#FFF7ED", "晚班 18:00–24:00")):
        x0, x1 = L + a * step, L + b * step
        p.append(f'<rect x="{x0:.1f}" y="{T}" width="{x1 - x0:.1f}" height="{ph}" fill="{col}" opacity="0.7"/>')
        p.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{T - 12}" text-anchor="middle" font-size="11" '
                 f'font-weight="700" fill="#64748B">{lab}</text>')
    for k in range(6):
        v = top * k // 5
        y = Y(v)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" stroke="#E2E8F0" stroke-width="1"/>')
        p.append(f'<text x="{L-8}" y="{y+4:.1f}" text-anchor="end" font-size="10.5" fill="#94A3B8">{v}</text>')
    for a in (8, 18):
        x = L + a * step
        p.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{T+ph}" stroke="#94A3B8" '
                 'stroke-width="1.4" stroke-dasharray="6 4"/>')
    # 每小时一根堆叠柱：从下往上依次画各环境，0 值不画（避免零高度色块）
    for i, r in enumerate(rows):
        x = X(i) - bw / 2
        acc = 0
        for s in series:
            v = int(r.get(s) or 0)
            if v <= 0:
                continue
            y0, y1 = Y(acc + v), Y(acc)
            p.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{y1-y0:.1f}" '
                     f'fill="{colors[s]}" stroke="#FFFFFF" stroke-width="0.6"/>')
            acc += v
        # 总数标柱顶，不塞进矮柱
        if r["total"] > 0:
            p.append(f'<text x="{X(i):.1f}" y="{Y(r["total"])-4:.1f}" text-anchor="middle" '
                     f'font-size="9.5" font-weight="700" fill="#334155">{r["total"]}</text>')
    for i in range(24):
        x = X(i)
        if i % 2 == 0:
            p.append(f'<text x="{x:.1f}" y="{T+ph+18}" text-anchor="middle" font-size="10" '
                     f'fill="#94A3B8">{i+1:02d}:00</text>')
        p.append(f'<rect class="hit" data-i="{i}" x="{L+i*step:.1f}" y="{T}" width="{step:.1f}" '
                 f'height="{ph}" fill="transparent" pointer-events="all" style="cursor:crosshair"/>')
    p.append(f'<text x="{W-R}" y="{H-6}" text-anchor="end" font-size="9.5" fill="#94A3B8">'
             '横轴为小时区间右端点，01:00 = 00:00–01:00；柱高＝该小时报错单数，色块＝环节构成</text></svg>')
    return "".join(p)


STAGE_TREND_JS = r"""
(function(){
  var box=document.getElementById('errBox'), tip=document.getElementById('errTip'),
      metaEl=document.getElementById('errMeta');
  if(!box||!tip||!metaEl) return;
  var meta; try{meta=JSON.parse(metaEl.textContent);}catch(e){return;}
  var rows=meta.rows||[], series=meta.series||[], colors=meta.colors||{};
  var f=function(n){return Number(n||0).toLocaleString('zh-CN');};
  function show(i,e){
    var r=rows[i]; if(!r) return;
    var html='<div class="th">'+String(i).padStart(2,'0')+':00 – '+String(i+1).padStart(2,'0')+':00</div>'+
      '<div class="tt">报错合计 <b>'+f(r.total)+'</b> 单</div>';
    series.forEach(function(s){
      html+='<div class="tr"><span><i style="background:'+(colors[s]||'#94A3B8')+'"></i>'+s+'</span><b>'+f(r[s]||0)+' 单</b></div>';
    });
    tip.innerHTML=html;
    tip.style.display='block';
    var br=box.getBoundingClientRect();
    var x=e.clientX-br.left+14, y=e.clientY-br.top+10;
    if(x+tip.offsetWidth>br.width-6) x=e.clientX-br.left-tip.offsetWidth-14;
    if(x<6) x=6;
    if(y+tip.offsetHeight>br.height-6) y=br.height-tip.offsetHeight-6;
    if(y<6) y=6;
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function hide(){tip.style.display='none';}
  Array.prototype.forEach.call(box.querySelectorAll('.hit'),function(el){
    el.addEventListener('mousemove',function(e){show(parseInt(el.getAttribute('data-i'),10),e);});
    el.addEventListener('mouseleave',hide);
  });
})();
"""


def build_hourly_stage_section(ctx):
    """06 24小时各环节报错堆叠柱：优先 hourly_stage_B（纯 B，口径同看板），其次 hourly_stage（B+D 混合），
    两者都没有时用每小时真实 B/D 两段。绝不用 B+D 混合数据冒充纯 B。"""
    stage_rows_b = ctx.get("hourly_stage_B") or []
    stage_rows_ab = ctx.get("hourly_stage") or []
    hours = ctx.get("hourly") or []
    if not hours:
        return ""
    # 有效环节表：24 行且含 8 环节字段；优先纯 B，退回 B+D 混合（文案标注口径）
    def valid(rows):
        return len(rows) == 24 and all(any(s in r for s in STAGES8) for r in rows)
    has_b = valid(stage_rows_b)
    has_ab = valid(stage_rows_ab)
    real = has_b or has_ab
    stage_rows = stage_rows_b if has_b else (stage_rows_ab if has_ab else [])
    colors = dict(STAGE8_COLOR) if real else {FB_B: C_B, FB_D: C_D}
    series = list(STAGES8) if real else [FB_B, FB_D]
    caliber = "纯 B 全自动失败 · 口径同看板" if has_b else ("B+D 全自动失败＋订单处理中" if has_ab else "真实 B/D 两段")
    src_note = (f"按创建时间 · 失败原因归 8 大环节 · {caliber} · 堆叠柱" if real
                else "按创建时间 · 真实 B/D 两段 · 环节细分待字段上线")
    data = []
    if real:
        by_hour = {int(r.get("hour") or 0): r for r in stage_rows}
        for r in hours:
            h = int(r.get("hour") or 0)
            src = by_hour.get(h, {})
            row = {"hour": h}
            for s in series:
                row[s] = int(src.get(s) or 0)
            row["total"] = sum(row[s] for s in series)
            data.append(row)
    else:
        for r in hours:
            row = {"hour": int(r.get("hour") or 0),
                   FB_B: int(r.get("B") or 0), FB_D: int(r.get("D") or 0)}
            row["total"] = row[FB_B] + row[FB_D]
            data.append(row)
    data.sort(key=lambda x: x["hour"])

    meta = {"rows": data, "series": series, "colors": colors}
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    lg = "".join(f'<span><i style="background:{colors[s]}"></i>{s}</span>' for s in series)
    tot = sum(r["total"] for r in data)
    peak = max(data, key=lambda r: r["total"])
    lead = (f'全天 {num(tot)} 单' + ('全自动失败' if has_b else ('报错' if has_ab else '报错')) +
            f'，最多的是 {peak["hour"]:02d}:00 时段（{num(peak["total"])} 单）。'
            + (("每根柱按环节分色堆叠，口径为纯 B 全自动失败（同看板），悬浮看每小时各环节条数。" if has_b
                else "每根柱按环节分色堆叠；本地数据尚无纯 B 小时环节字段，此处为 B＋D 合计（含订单处理中），生产机补 pure-B 字段后自动切换。")
               if real else
               '当前数据没有按小时拆分的环节字段，先按真实结果画出全自动失败 / 订单处理中两段；'
               '生产机补上字段后，这里会自动变成 8 个环节分色堆叠。'))
    return (
        '<div class="sec"><div class="sec-h"><span class="sec-n">06</span><h2>24 小时各环节报错</h2>'
        f'<span class="sectip">{src_note} · 悬浮看明细</span></div>'
        f'<div class="lead">{lead}</div>'
        f'<div class="stage-lg">{lg}<span>灰虚线＝班次分界（08 / 18 点）</span></div>'
        f'<div class="chartbox" id="errBox">{build_stage_stacked_svg(data, series, colors)}'
        '<div class="hovertip" id="errTip"></div></div>'
        f'<script type="application/json" id="errMeta">{meta_json}</script><script>{STAGE_TREND_JS}</script>'
        '</div>'
    )


def build_fail_top5_section(ctx):
    """07 每个环节 top5 报错：只取 fail_reasons_B（全自动失败，口径同看板失败原因排行），按 family 归 8 大环节取前 5。"""
    reasons = ctx.get("fail_b") or []
    grouped = {}
    merged = {}  # (stage, 显示名) -> 合并单数，避免同一就近名拆成多行
    for x in reasons:
        st = stage8_of_family(x.get("family"))
        # 显示名优先级：near_reason（看板「失败原因(需就近)」）> full > reason
        label = str(x.get("near_reason") or "").strip() \
            or str(x.get("full") or "").strip() \
            or str(x.get("reason") or "").strip()
        key = (st, label)
        merged[key] = merged.get(key, 0) + int(x.get("count") or 0)
    for (st, label), n in merged.items():
        grouped.setdefault(st, []).append((n, label))
    if not grouped:
        return ""
    parts = []
    total_fail = sum(n for v in grouped.values() for n, _ in v)
    grand = []
    for st in STAGES8:
        items = sorted(grouped.get(st, []), key=lambda t: -t[0])[:5]
        if not items:
            continue
        st_sum = sum(n for n, _ in grouped[st])
        grand.extend((st, n, r) for n, r in items)
        mx = items[0][0] or 1
        rows = []
        for n, reason in items:
            rows.append(
                '<div class="errrow">'
                f'<div class="erm" title="{esc(" ".join(reason.split()))}">{_esc_text(reason)}</div>'
                f'<div class="erb"><i style="width:{n/mx*100:.1f}%;background:{STAGE8_COLOR[st]}"></i></div>'
                f'<div class="ern">{num(n)} 单</div>'
                f'<div class="erp">{pct(n/total_fail*100) if total_fail else "0.00%"}</div>'
                '</div>'
            )
        parts.append(
            '<div class="errgrp"><div class="errgrp-h">'
            f'<i class="dot" style="background:{STAGE8_COLOR[st]}"></i>'
            f'<b>{st}</b><span>合计 {num(st_sum)} 单 · 下列为该环节报错最多的 5 种</span></div>'
            + "".join(rows) + '</div>'
        )
    pw = ctx.get("period_word", "当天")
    lead = (f'{pw}全自动失败单按失败原因归到 8 大环节，实际有报错的有 {len(parts)} 个环节、共 {num(total_fail)} 单；'
            '每个环节列出报错最多的 5 种原因（占全量失败的比例，口径同看板 B 路径）。')
    return (
        '<div class="sec"><div class="sec-h"><span class="sec-n">07</span><h2>各环节 TOP5 报错</h2>'
        '<span class="sectip">全自动失败 B 口径 · 归 8 大环节 · 每环节前 5 种</span></div>'
        f'<div class="lead">{lead}</div>'
        '<div class="legend"><span>左：失败原因（与看板口径一致，完整显示）　中：环节内相对条数　右：单量／占全量报错比例</span></div>'
        + "".join(parts) + '</div>'
    )


SHIFTS = (
    ("通宵班", "00:00–08:00", "overnight", tuple(range(0, 8))),
    ("白班", "08:00–18:00", "day", tuple(range(8, 18))),
    ("晚班", "18:00–24:00", "night", tuple(range(18, 24))),
)
SHIFT_STAFF = {"通宵班": 2, "白班": 8, "晚班": 8}


def hourly_value(row, key):
    """折线口径：A/B 分母＝A+B；C/D 分母＝该小时全量。"""
    if key in ("A", "B"):
        base = int(row.get("A") or 0) + int(row.get("B") or 0)
        return float(row.get(key) or 0) / base * 100 if base else 0.0
    tot = int(row.get("total") or 0)
    return float(row.get(key) or 0) / tot * 100 if tot else 0.0


def build_shift_cards(hours, staff_n):
    cards, stats = [], {}
    for name, span, cls, rng in SHIFTS:
        g = [r for r in hours if int(r.get("hour") or 0) in rng]
        t = sum(int(r.get("total") or 0) for r in g)
        a = sum(int(r.get("A") or 0) for r in g)
        b = sum(int(r.get("B") or 0) for r in g)
        c = sum(int(r.get("C") or 0) for r in g)
        d = sum(int(r.get("D") or 0) for r in g)
        need = b + c + d
        rate = a / (a + b) * 100 if a + b else 0.0
        per = need / SHIFT_STAFF[name]
        stats[name] = {"total": t, "need": need, "per": per, "rate": rate}
        cards.append(
            f'<div class="shift {cls}"><div class="sh"><b>{name}</b><span>{span}</span></div>'
            f'<div class="sm"><span>需处理单 <em>{num(need)}</em></span>'
            f'<span>人均处理 <em>{per:.1f}</em> 单/人</span></div>'
            f'<div class="sm"><span>全自动成功率 <em>{pct(rate)}</em></span></div></div>'
        )
    return "".join(cards), stats


def lead_hourly(total, stats, need_all):
    over, day, night = stats["通宵班"], stats["白班"], stats["晚班"]
    total_staff = sum(SHIFT_STAFF.values())
    per_all = need_all / total_staff if total_staff else 0.0
    return (f'全天 {num(total)} 单按创建时间分布：白班 {num(day["total"])} 单、'
            f'晚班 {num(night["total"])} 单、通宵班 {num(over["total"])} 单。'
            f'除全自动成功外，实际需处理 {num(need_all)} 单，人均处理 {per_all:.1f} 单'
            f'（白班 {day["per"]:.1f}、晚班 {night["per"]:.1f}、通宵班 {over["per"]:.1f}）。'
            f'三个班次的全自动成功率分别是通宵班 {pct(over["rate"])}、白班 {pct(day["rate"])}、'
            f'晚班 {pct(night["rate"])}，相差 '
            f'{max(x["rate"] for x in stats.values()) - min(x["rate"] for x in stats.values()):.2f} 个百分点。')


def build_hourly_svg(hours):
    W, H = 1080, 372
    L, R, T, B = 52, 18, 46, 42
    pw, ph = W - L - R, H - T - B
    step = pw / 24
    X = lambda i: L + (i + 0.5) * step
    Y = lambda v: T + ph - (max(0, min(100, v)) / 100 * ph)

    p = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="逐小时四路径比率折线图">']
    for a, b, col, lab in ((0, 8, "#F5F3FF", "通宵班 00:00–08:00"),
                           (8, 18, "#EFF6FF", "白班 08:00–18:00"),
                           (18, 24, "#FFF7ED", "晚班 18:00–24:00")):
        x0, x1 = L + a * step, L + b * step
        p.append(f'<rect x="{x0:.1f}" y="{T}" width="{x1 - x0:.1f}" height="{ph}" fill="{col}" opacity="0.7"/>')
        p.append(f'<text x="{(x0 + x1) / 2:.1f}" y="{T - 12}" text-anchor="middle" font-size="11" '
                 f'font-weight="700" fill="#64748B">{lab}</text>')
    for v in range(0, 101, 20):
        y = Y(v)
        p.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="#E2E8F0" stroke-width="1"/>')
        p.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10.5" fill="#94A3B8">{v}%</text>')
    for a in (8, 18):
        x = L + a * step
        p.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{T + ph}" stroke="#94A3B8" '
                 'stroke-width="1.4" stroke-dasharray="6 4"/>')

    series = (("A 全自动成功率", "A", C_A, 2.6, False),
              ("B 全自动失败率", "B", C_B, 2.2, False),
              ("C 订单转人工率", "C", C_C, 2.0, False),
              ("D 订单处理中率", "D", C_D, 1.8, True))
    for _, key, col, width, dashed in series:
        pts = [f"{X(i):.1f},{Y(hourly_value(r, key)):.1f}" for i, r in enumerate(hours)]
        da = ' stroke-dasharray="5 3"' if dashed else ''
        p.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{col}" stroke-width="{width}" '
                 f'stroke-linejoin="round" stroke-linecap="round"{da}/>')
        for i, r in enumerate(hours):
            p.append(f'<circle cx="{X(i):.1f}" cy="{Y(hourly_value(r, key)):.1f}" r="2.6" fill="{col}"/>')

    for key in ("A", "B"):
        vals = [hourly_value(r, key) for r in hours]
        if not vals:
            continue
        for idx, col in ((max(range(len(vals)), key=lambda i: vals[i]), "#059669"),
                         (min(range(len(vals)), key=lambda i: vals[i]), "#DC2626")):
            cx, cy = X(idx), Y(vals[idx])
            p.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="8" fill="{col}" stroke="#fff" stroke-width="2"/>')
            p.append(f'<text x="{cx:.1f}" y="{cy + 3:.1f}" text-anchor="middle" font-size="8.5" '
                     f'font-weight="800" fill="#fff">{vals[idx]:.0f}</text>')

    for i in range(24):
        x = X(i)
        p.append(f'<text x="{x:.1f}" y="{T + ph + 18}" text-anchor="middle" font-size="10" '
                 f'fill="#94A3B8">{i + 1:02d}:00</text>')
        p.append(f'<rect class="hit" data-i="{i}" x="{L + i * step:.1f}" y="{T}" width="{step:.1f}" '
                 f'height="{ph}" fill="transparent" pointer-events="all" style="cursor:crosshair"/>')
    p.append(f'<text x="{W - R}" y="{H - 6}" text-anchor="end" font-size="9.5" fill="#94A3B8">'
             '横轴为小时区间右端点，01:00 = 00:00–01:00</text></svg>')
    return "".join(p)


HOUR_JS = r"""
(function(){
  var box=document.getElementById('hourBox'), tip=document.getElementById('hourTip'),
      metaEl=document.getElementById('hourMeta');
  if(!box||!tip||!metaEl) return;
  var meta; try{meta=JSON.parse(metaEl.textContent);}catch(e){return;}
  var hours=meta.hours||[], staff=meta.staff_n||0, sts=meta.staff_by_hour||[];
  var f=function(n){return Number(n||0).toLocaleString('zh-CN');};
  var p=function(v){return Number(v||0).toFixed(1)+'%';};
  var dot=function(c){return '<i style="background:'+c+'"></i>';};
  function show(i,e){
    var r=hours[i]; if(!r) return;
    var A=r.A||0,B=r.B||0,C=r.C||0,D=r.D||0,t=r.total||0,auto=A+B,need=B+C+D;
    var st=sts[i]||staff||1;
    tip.innerHTML='<div class="th">'+String(i+1).padStart(2,'0')+':00</div>'+
      '<div class="tt">总计 <b>'+f(t)+'</b> 单 · 需处理 <b>'+f(need)+'</b> 单（人均 '+(need/st).toFixed(1)+' 单/人）</div>'+
      '<div class="tr"><span>'+dot('#059669')+'A 全自动成功</span><b>'+f(A)+' 单 ('+p(auto?A/auto*100:0)+')</b></div>'+
      '<div class="tr"><span>'+dot('#DC2626')+'B 全自动失败</span><b>'+f(B)+' 单 ('+p(auto?B/auto*100:0)+')</b></div>'+
      '<div class="tr"><span>'+dot('#EA580C')+'C 订单转人工</span><b>'+f(C)+' 单 ('+p(t?C/t*100:0)+')</b></div>'+
      '<div class="tr"><span>'+dot('#94A3B8')+'D 订单处理中</span><b>'+f(D)+' 单 ('+p(t?D/t*100:0)+')</b></div>'+
      '<div class="sep"></div><div class="sum">成功率 <b>'+p(auto?A/auto*100:0)+'</b> · 覆盖率 '+p(t?auto/t*100:0)+'</div>';
    tip.style.display='block';
    var br=box.getBoundingClientRect();
    var x=e.clientX-br.left+14, y=e.clientY-br.top+10;
    if(x+tip.offsetWidth>br.width-6) x=e.clientX-br.left-tip.offsetWidth-14;
    if(x<6) x=6;
    if(y+tip.offsetHeight>br.height-6) y=br.height-tip.offsetHeight-6;
    if(y<6) y=6;
    tip.style.left=x+'px'; tip.style.top=y+'px';
  }
  function hide(){tip.style.display='none';}
  Array.prototype.forEach.call(box.querySelectorAll('.hit'),function(el){
    el.addEventListener('mousemove',function(e){show(parseInt(el.getAttribute('data-i'),10),e);});
    el.addEventListener('mouseleave',hide);
  });
})();
"""


def build_hour_section(ctx):
    hours = ctx.get("hourly") or []
    if not hours:
        return ""
    staff_n = int(ctx.get("staff_n") or 0)
    total = int(ctx["summary"]["total_orders"])
    cards, stats = build_shift_cards(hours, staff_n)
    need_all = sum(int(r.get("B") or 0) + int(r.get("C") or 0) + int(r.get("D") or 0)
                   for r in hours)
    staff_by_hour = [next((SHIFT_STAFF[name] for name, _, _, rng in SHIFTS
                           if int(r.get("hour") or 0) in rng), staff_n) for r in hours]
    meta = {"staff_n": staff_n, "staff_by_hour": staff_by_hour,
            "hours": [{k: int(r.get(k) or 0) for k in ("hour", "total", "A", "B", "C", "D")}
                      for r in hours]}
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return (
        '<div class="sec"><div class="sec-h"><span class="sec-n">04</span><h2>逐小时自动化趋势</h2>'
        '<span class="sectip">按创建时间 · 0–24 点 · 鼠标悬浮看明细</span></div>'
        f'<div class="lead">{lead_hourly(total, stats, need_all)}</div>'
        '<div class="shifts">' + cards + '</div>'
        + '<div class="legend"><span><i style="background:' + C_A + '"></i>A 全自动成功率</span>'
        f'<span><i style="background:{C_B}"></i>B 全自动失败率</span>'
        f'<span><i style="background:{C_C}"></i>C 订单转人工率</span>'
        f'<span><i style="background:{C_D}"></i>D 订单处理中率</span>'
        '<span>灰色虚线＝班次分界；彩色圆点为各路径的高／低点</span></div>'
        f'<div class="chartbox" id="hourBox">{build_hourly_svg(hours)}<div class="hovertip" id="hourTip"></div></div>'
        f'<script type="application/json" id="hourMeta">{meta_json}</script><script>{HOUR_JS}</script>'
        '</div>'
    )


def build_html(ctx):
    d = ctx["date"]
    s = ctx["summary"]
    total = int(s["total_orders"])
    seg = int(s["total_segments"])
    A, B, C, D = int(s["A"]), int(s["B"]), int(s["C"]), int(s["D"])
    succ = float(s["auto_succ_rate"])
    target = ctx["target"]
    pw = ctx.get("period_word", "当天")

    cards_html, plat_sorted = build_platform_cards(ctx["platform"], target, total)
    air_html, air_ok = build_rank_rows(ctx["airline"], target, "airline")
    ch_html, ch_ok = build_rank_rows(ctx["channel"], target, "channel")

    parts = []
    parts.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<title>自动化数据汇报</title><style>' + CSS + '</style></head><body><div class="wrap">')

    # 标题区
    if "~" in d:
        date_cn = f"{esc(d)} · 共 {int(ctx['summary'].get('total_days') or 1)} 天"
    else:
        date_cn = f"{esc(d)}（{weekday_cn(d)}）"
    metas = (
        f'数据日期 <b>{date_cn}</b>',
        f'数据更新 <b>{esc(ctx["generated_at"][:16])}</b>',
        f'全自动成功率目标 <b>{pct(target, 0)}</b>',
    )
    parts.append(
        '<div class="head"><h1>自动化数据汇报</h1><div class="rule"></div>'
        '<div class="meta">' + "".join(f'<span class="mi">{m}</span>' for m in metas) + '</div></div>'
    )

    # 三个框
    parts.append('<div class="boxes">')
    parts.append(
        '<div class="box"><div class="bt">整体规模</div><div class="pair">'
        f'<div class="cell"><div class="pk">订单总数</div><div class="pv blue">{num(total)}</div></div>'
        f'<div class="cell"><div class="pk">航段总数</div><div class="pv blue">{num(seg)}</div></div>'
        '</div>'
        f'<div class="pf">平均每单 {seg / total:.2f} 个航段</div></div>'
    )
    parts.append(
        '<div class="box"><div class="bt">自动出票结果</div><div class="pair">'
        f'<div class="cell"><div class="pk">全自动成功率</div><div class="pv green">{pct(succ)}</div></div>'
        f'<div class="cell"><div class="pk">全自动成功数</div><div class="pv green">{num(A)}</div></div>'
        '</div>'
        f'<div class="pf">占全量 {pct(A / total * 100)}</div></div>'
    )
    parts.append(
        '<div class="box"><div class="bt">转人工与失败</div><div class="pair">'
        f'<div class="cell"><div class="pk">订单转人工<span class="sub">（手工政策转人工）</span></div><div class="pv orange">{num(C)}</div></div>'
        f'<div class="cell"><div class="pk">全自动失败</div><div class="pv red">{num(B)}</div></div>'
        '</div>'
        f'<div class="pf">占全量：转人工 {pct(C / total * 100)}　失败 {pct(B / total * 100)}</div></div>'
    )
    parts.append('</div>')

    # 01 平台
    parts.append(
        '<div class="sec"><div class="sec-h"><span class="sec-n">01</span><h2>各平台对比</h2>'
        '<span class="sectip">按订单量降序 · 堆叠条为 4 路径构成</span></div>'
        f'<div class="lead">{lead_platform(plat_sorted, target, total)}</div>'
        f'<div class="legend"><span><i style="background:{C_A}"></i>A 全自动成功</span>'
        f'<span><i style="background:{C_B}"></i>B 全自动失败</span>'
        f'<span><i style="background:{C_C}"></i>C 订单转人工</span>'
        f'<span><i style="background:{C_D}"></i>D 订单处理中</span></div>'
        + cards_html + build_table(plat_sorted) + '</div>'
    )

    # 02 航司
    parts.append(
        '<div class="sec"><div class="sec-h"><span class="sec-n">02</span><h2>航司自动化成功率</h2>'
        f'<span class="sectip">全量 {len(ctx["airline"])} 家 · 目标 {pct(target, 0)} · 按成功率降序</span></div>'
        f'<div class="lead">{lead_rank(ctx["airline"], target, "航司", "家", air_ok)}</div>'
        f'<div class="legend"><span>进度条＝全自动成功率，灰色虚线＝目标线；右侧为达标情况与{pw}订单量</span></div>'
        + air_html + '</div>'
    )

    # 03 渠道
    parts.append(
        '<div class="sec"><div class="sec-h"><span class="sec-n">03</span><h2>渠道自动化成功率</h2>'
        f'<span class="sectip">全量 {len(ctx["channel"])} 个 · 目标 {pct(target, 0)} · 按成功率降序</span></div>'
        f'<div class="lead">{lead_rank(ctx["channel"], target, "渠道", "个", ch_ok)}</div>'
        f'<div class="legend"><span>进度条＝全自动成功率，灰色虚线＝目标线；右侧为达标情况与{pw}订单量</span></div>'
        + ch_html + '</div>'
    )

    # 04 逐小时趋势
    parts.append(build_hour_section(ctx))

    # 05 每日各环节报错
    parts.append(build_daily_stage_section(ctx))
    # 06 24小时各环节报错
    parts.append(build_hourly_stage_section(ctx))
    # 07 各环节 TOP5 报错
    parts.append(build_fail_top5_section(ctx))

    parts.append('</div></body></html>')
    return "".join(parts)


def main():
    ap = argparse.ArgumentParser(description="生成自动化数据汇报 HTML")
    ap.add_argument("--month", help="月份 YYYY-MM，默认取 dashboard_data.json 的 current_month")
    ap.add_argument("--date", help="数据日 YYYY-MM-DD，默认取该月最新一天")
    ap.add_argument("--start", help="区间起始日 YYYY-MM-DD（与 --end 搭配，合并区间多天为一份汇总）")
    ap.add_argument("--end", help="区间结束日 YYYY-MM-DD（含当天）")
    ap.add_argument("--target", type=float, help="覆盖全自动成功率目标（%%）")
    ap.add_argument("--out", help="输出 HTML 路径，默认 output/自动化数据汇报_<日期>.html")
    ap.add_argument("--local", action="store_true", help="只用本地数据，不联网")
    ap.add_argument("--no-fetch", action="store_true", help="跳过 git fetch，用已缓存的 origin/main")
    args = ap.parse_args()

    use_remote = not args.local
    ym, d, day, source, generated_at, md = resolve(
        args.month, args.date, use_remote=use_remote, do_fetch=not args.no_fetch)

    # 日期区间模式：把 [start, end] 内每天合并成一份汇总
    is_range = bool(args.start or args.end)
    if is_range:
        dd = md.get("daily_detail") or {}
        if not args.start or not args.end:
            raise SystemExit("区间模式需同时提供 --start 和 --end")
        keys = sorted(k for k in dd if args.start <= k <= args.end)
        if not keys:
            raise SystemExit(f"{ym} 区间 {args.start}~{args.end} 内没有数据，可用：{', '.join(sorted(dd))}")
        day = merge_days([dd[k] for k in keys], keys[0], keys[-1])
        d = f"{keys[0]}~{keys[-1]}"
        print(f"区间模式 : {keys[0]} ~ {keys[-1]}（{len(keys)} 天合并）")
    s = day.get("summary") or {}
    row = (day.get("daily") or [{}])[0]
    for k in ("total_orders", "total_segments", "A", "B", "C", "D", "auto_succ_rate"):
        if k not in s or s[k] is None:
            s[k] = row.get("total" if k == "total_orders" else k, 0)

    hourly = sorted((s.get("hourly_today") or {}).get("data") or [],
                    key=lambda r: int(r.get("hour") or 0))
    ctx = {
        "month": ym, "date": d, "summary": s,
        "period_word": "区间内" if is_range else "当天",
        "platform": day.get("platform") or [],
        "airline": day.get("airline") or [],
        "channel": day.get("channel") or [],
        "hourly": hourly,
        "staff_n": len(day.get("staff") or []),
        "target": target_of(ym, args.target, use_remote),
        "source": source, "generated_at": generated_at,
        "daily_stage": md.get("daily_stage") or [],
        "month_detail": md.get("daily_detail") or {},
        "hourly_stage": day.get("hourly_stage") or [],
        "hourly_stage_B": day.get("hourly_stage_B") or [],
        "fail_b": day.get("fail_reasons_B") or [],
        "fail_d": day.get("fail_reasons_D") or [],
    }
    date_tag = d.replace("~", "_") if is_range else d
    out = args.out or os.path.join(BASE, "output", f"自动化数据汇报_{date_tag}.html")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    content = build_html(ctx)
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)

    # 看板「📊 数据汇报」入口指向固定文件名，始终代表最新一次生成的汇报
    latest = os.path.join(BASE, "output", "自动化数据汇报.html")
    if os.path.abspath(latest) != os.path.abspath(out):
        with open(latest, "w", encoding="utf-8") as f:
            f.write(content)

    date_label = d if is_range else f"{d}（{weekday_cn(d)}）"
    print(f"数据日期 : {date_label}")
    print(f"数据源   : {source}（更新于 {generated_at[:16]}）")
    print(f"订单/航段: {num(s['total_orders'])} / {num(s['total_segments'])}")
    print(f"全自动成功率 / 成功数: {pct(s['auto_succ_rate'])} / {num(s['A'])}")
    print(f"订单转人工 / 全自动失败: {num(s['C'])} / {num(s['B'])}")
    print(f"平台 / 航司 / 渠道: {len(ctx['platform'])} / {len(ctx['airline'])} / {len(ctx['channel'])} 项")
    print(f"逐小时数据 : {len(ctx['hourly'])} 个小时桶 / 当日锁定人数 {ctx['staff_n']}")
    print(f"报错数据  : 每日环节 {len(ctx['daily_stage'])} 天 / 小时环节B {'有' if ctx['hourly_stage_B'] else '无'}(混合 {len(ctx['hourly_stage'])} 桶) / B原因 {len(ctx['fail_b'])} 条")
    print(f"目标值   : {pct(ctx['target'], 0)}")
    print(f"输出文件 : {out}  ({len(content.encode('utf-8')) / 1024:.1f} KB)")
    print(f"看板入口 : {latest}")
    return out


if __name__ == "__main__":
    main()
