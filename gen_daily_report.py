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


def target_of(ym, override=None, use_remote=True):
    if override is not None:
        return float(override)
    t = (git_read("targets.json") if use_remote else None) or \
        load_json(os.path.join(BASE, "targets.json"))
    return float(t.get(ym) or t.get("_default") or 83)


CSS = r"""
*{box-sizing:border-box}
body{margin:0;background:#F4F6F9;color:#1B2430;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei","Hiragino Sans GB",Arial,sans-serif;font-size:14px;line-height:1.7;-webkit-font-smoothing:antialiased}
.wrap{max-width:1120px;margin:0 auto;padding:28px 22px 60px}
.head{padding:30px 30px 26px;background:#fff;border:1px solid #E5E9F0;border-radius:16px;border-top:4px solid #2563EB;text-align:center;box-shadow:0 3px 16px rgba(20,38,70,.05)}
.head h1{margin:0;font-size:32px;font-weight:800;letter-spacing:3px;color:#16202E;line-height:1.45}
.head .rule{width:54px;height:3px;border-radius:3px;margin:12px auto 15px;background:linear-gradient(90deg,#2563EB,#38BDF8)}
.head .meta{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 8px;color:#5A6675;font-size:11.5px;line-height:1.5}
.head .meta .mi{white-space:nowrap;background:#F5F8FC;border:1px solid #E8EEF6;border-radius:999px;padding:4px 11px}
.head .meta .mi b{color:#334155;font-weight:700}
.boxes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:18px 0 22px}
.box{position:relative;overflow:hidden;background:#fff;border:1px solid #E5E9F0;border-radius:16px;padding:14px 16px 12px;min-width:0;text-align:left;box-shadow:0 3px 16px rgba(20,38,70,.05)}
.box:before{content:"";position:absolute;left:0;right:0;top:0;height:3px}
.box:nth-child(1):before{background:#2563EB}
.box:nth-child(2):before{background:#059669}
.box:nth-child(3):before{background:#F59E0B}
.box .bt{font-size:11.5px;font-weight:700;color:#64748B;letter-spacing:1.5px;margin-bottom:6px}
.box .pair{display:grid;grid-template-columns:1fr;gap:0}
.box .cell{display:grid;grid-template-columns:1fr 1fr;align-items:center;padding:5px 0;min-height:45px;border-bottom:1px dashed #EDF1F6}
.box .cell:last-child{border-bottom:none}
.box .pk{font-size:11.5px;color:#5A6675;white-space:nowrap;text-align:left}
.box .pk .sub{display:block;font-size:10.5px;line-height:1.3;color:#94A3B8;margin-top:1px}
.box .pv{font-size:23px;font-weight:800;line-height:1.2;letter-spacing:-.5px;margin:0;font-variant-numeric:tabular-nums;text-align:center}
.box .pv.blue{color:#2563EB}.box .pv.green{color:#059669}.box .pv.orange{color:#EA580C}.box .pv.red{color:#DC2626}
.box .pf{margin-top:8px;padding-top:7px;border-top:1px dashed #F0F3F8;font-size:10.5px;color:#94A3B8;min-height:18px;line-height:1.6;text-align:left}
.sec{background:#fff;border:1px solid #E5E9F0;border-radius:14px;padding:24px 28px 26px;margin-bottom:20px;box-shadow:0 3px 16px rgba(20,38,70,.045)}
.sec-h{display:flex;align-items:baseline;gap:12px;margin-bottom:6px;flex-wrap:wrap}
.sec-n{font-size:12px;font-weight:800;color:#2563EB;background:#EFF6FF;padding:3px 9px;border-radius:6px;white-space:nowrap}
.sec-h h2{margin:0;font-size:19px;font-weight:800;letter-spacing:.2px}
.sec-h .sectip{font-size:11.5px;color:#8A95A5;margin-left:auto}
.lead{margin:10px 0 18px;padding:12px 16px;background:#F8FAFC;border-left:3px solid #94A3B8;border-radius:0 8px 8px 0;font-size:14px;line-height:1.85;color:#334155}
.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:11.5px;color:#5A6675;margin:0 0 14px}
.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}
.plat{border:1px solid #EEF1F6;border-radius:10px;padding:13px 16px 12px;margin-bottom:10px;break-inside:avoid}
.plat-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:9px}
.plat-nm{font-size:14px;font-weight:700;color:#1B2430}
.plat-tot{font-size:12px;color:#5A6675}
.plat-rate{margin-left:auto;font-size:12px;color:#5A6675;white-space:nowrap}
.plat-rate b{font-size:16px;font-variant-numeric:tabular-nums;margin-left:4px}
.stack{display:flex;width:100%;height:16px;border-radius:5px;overflow:hidden;background:#F1F4F8}
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
.rank-bar{position:relative;height:15px;background:#F1F4F8;border-radius:4px;overflow:visible}
.rank-bar .fill{position:absolute;left:0;top:0;height:100%;border-radius:4px}
.rank-bar .target{position:absolute;top:-3px;height:21px;width:0;border-left:2px dashed #64748B;z-index:2}
.rank-pct{font-size:12.5px;font-weight:800;text-align:right;font-variant-numeric:tabular-nums}
.rank-cnt{font-size:11.5px;color:#8A95A5;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.rank-bg{text-align:right}
table{width:100%;border-collapse:collapse;margin:16px 0 4px;font-size:12.5px;line-height:1.5}
th{background:#F1F5F9;color:#334155;font-weight:700;text-align:left;padding:8px 14px;border-bottom:1px solid #DDE4ED;white-space:nowrap}
td{padding:7px 14px;border-bottom:1px solid #EFF2F6;color:#334155}
tr:last-child td{border-bottom:none}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:nth-child(even){background:#FAFBFD}
.foot{background:#fff;border:1px solid #E5E9F0;border-radius:12px;padding:18px 24px;font-size:12px;color:#5A6675;line-height:1.9;box-shadow:0 3px 16px rgba(20,38,70,.045)}
.foot h3{margin:0 0 8px;font-size:13.5px;color:#1B2430}
.foot ul{margin:0;padding-left:20px}
/* 04 逐小时趋势 */
.shifts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0 16px}
.shift{background:#fff;border:1px solid #E5E9F0;border-left:3px solid #94A3B8;border-radius:10px;padding:10px 13px;min-width:0}
.shift.overnight{border-left-color:#7C3AED}.shift.day{border-left-color:#2563EB}.shift.night{border-left-color:#EA580C}
.shift .sh{display:flex;align-items:baseline;gap:7px;white-space:nowrap}
.shift .sh b{font-size:12.5px;color:#1B2430}.shift .sh span{font-size:10.5px;color:#94A3B8}
.shift .sm{display:flex;justify-content:space-between;gap:8px;margin-top:6px;font-size:11.5px;color:#5A6675}
.shift .sm em{font-style:normal;font-weight:800;color:#1B2430;font-variant-numeric:tabular-nums}
.chartbox{position:relative;border:1px solid #EEF1F6;border-radius:10px;padding:8px 8px 2px;background:#fff}
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
.errrow .erm{color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.errrow .erb{height:9px;background:#F1F4F8;border-radius:3px;overflow:hidden}
.errrow .erb i{display:block;height:100%;border-radius:3px}
.errrow .ern,.errrow .erp{text-align:right;color:#5A6675;font-variant-numeric:tabular-nums}
.errrow .erp{color:#94A3B8}
@media(max-width:900px){.boxes{grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.box{padding:11px 10px 9px}.box .bt{font-size:10px;letter-spacing:1px;margin-bottom:4px}.box .cell{min-height:42px}.box .pv{font-size:18px}.box .pk{font-size:10px}.box .pk .sub{font-size:10px}.box .pf{font-size:9.5px;min-height:16px}.head{padding:22px 14px 20px}.head h1{font-size:24px;letter-spacing:1.5px}.head .meta{font-size:10.5px}.head .meta .mi{padding:3px 8px}.rank{grid-template-columns:130px 1fr 62px 70px}.rank .rank-bg{display:none}.wrap{padding:14px}.shifts{gap:7px}.shift{padding:8px 9px}.shift .sh b{font-size:11px}.shift .sh span{font-size:9px}.shift .sm{font-size:10px}}
@media print{body{background:#fff}.wrap{max-width:none;padding:0}.head,.sec,.foot,.box{break-inside:avoid;box-shadow:none;border-color:#D9DEE6}@page{margin:12mm}}
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
    """报错原因是自由文本，转义并压空白，长文本截断显示。"""
    s = " ".join(str(s or "").split())
    if not s or s == "(无)":
        return "（无失败原因）"
    return esc(s if len(s) <= 46 else s[:45] + "…")


def build_daily_stage_section(ctx):
    """05 每日各环节报错：当天按失败原因归 8 大环节，每环节一根柱子表示报错单数。"""
    reasons = (ctx.get("fail_b") or []) + (ctx.get("fail_d") or [])
    counts = stage8_counts(reasons)
    pairs = [(s, int(counts.get(s) or 0)) for s in STAGES8]
    total = sum(n for _, n in pairs)
    if not total:
        return ""
    d = ctx["date"]

    W, H, L, R, T, B = 1080, 360, 52, 24, 46, 64
    pw, ph = W - L - R, H - T - B
    max_n = max(n for _, n in pairs) or 1
    top = max(100, ((max_n + 99) // 100) * 100)
    gy_step = 100 if top <= 1000 else 200
    Y = lambda v: T + ph - (v / top * ph)
    slot = pw / len(pairs)
    bw = min(96, slot * 0.56)

    out = [f'<svg class="barsvg" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    v = 0
    while v <= top:
        y = Y(v)
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W - R}" y2="{y:.1f}" stroke="#EDF1F6" stroke-width="1"/>')
        out.append(f'<text x="{L - 8}" y="{y + 4:.1f}" text-anchor="end" font-size="10.5" fill="#94A3B8">{num(v)}</text>')
        v += gy_step
    for i, (stage, n) in enumerate(pairs):
        cx = L + slot * (i + 0.5)
        x = cx - bw / 2
        share = n / total * 100
        out.append(f'<g><title>{esc(stage)}：{num(n)} 单，占 {pct(share)}</title>')
        if n:
            h = n / top * ph
            y = Y(n)
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{h:.1f}" '
                       f'fill="{STAGE8_COLOR[stage]}"/>')
            out.append(f'<text x="{cx:.1f}" y="{y - 8:.1f}" text-anchor="middle" font-size="14" '
                       f'font-weight="800" fill="#1B2430">{num(n)}</text>')
            out.append(f'<text x="{cx:.1f}" y="{y - 23:.1f}" text-anchor="middle" font-size="10" '
                       f'fill="#94A3B8">{share:.1f}%</text>')
        else:
            out.append(f'<line x1="{x:.1f}" y1="{Y(0):.1f}" x2="{x + bw:.1f}" y2="{Y(0):.1f}" '
                       'stroke="#CBD5E1" stroke-width="3"/>')
            out.append(f'<text x="{cx:.1f}" y="{Y(0) - 8:.1f}" text-anchor="middle" font-size="12" '
                       'font-weight="700" fill="#94A3B8">0</text>')
        out.append(f'<text x="{cx:.1f}" y="{T + ph + 22:.1f}" text-anchor="middle" font-size="12.5" '
                   f'font-weight="700" fill="#334155">{esc(stage)}</text>')
        out.append('</g>')
    out.append(f'<text x="{W - R}" y="{H - 6}" text-anchor="end" font-size="9.5" fill="#94A3B8">'
               '柱高＝该环节报错单数，百分比＝占当天报错总量</text></svg>')

    nonzero = [(s, n) for s, n in pairs if n]
    top3 = sorted(nonzero, key=lambda x: -x[1])[:3]
    zeros = [s for s, n in pairs if not n]
    lead = (f'{esc(d)} 当天记录报错 {num(total)} 单（B 全自动失败＋D 订单处理中），'
            f'按失败原因归到 {len(pairs)} 类环节。报错最多的是 '
            + '、'.join(f'{s} {num(n)} 单（{pct(n / total * 100)}）' for s, n in top3) + '。')
    if zeros:
        lead += f'当天 {len(zeros)} 个环节没有报错：' + '、'.join(zeros) + '。'
    lg = "".join(f'<span><i style="background:{STAGE8_COLOR[s]}"></i>{s}</span>' for s in STAGES8)
    return (
        '<div class="sec"><div class="sec-h"><span class="sec-n">05</span><h2>每日各环节报错</h2>'
        f'<span class="sectip">{esc(d)} · 共 {num(total)} 单 · 每环节一根柱</span></div>'
        f'<div class="lead">{lead}</div>'
        f'<div class="stage-lg">{lg}<span>「其他环节」＝未匹配到具体环节的兜底</span></div>'
        + "".join(out) + '</div>'
    )


ERR_JS = r"""
(function(){
  var box=document.getElementById('errBox'), tip=document.getElementById('errTip'),
      metaEl=document.getElementById('errMeta');
  if(!box||!tip||!metaEl) return;
  var meta; try{meta=JSON.parse(metaEl.textContent);}catch(e){return;}
  var hours=meta.hours||[], stages=meta.stages||[], colors=meta.colors||{};
  var f=function(n){return Number(n||0).toLocaleString('zh-CN');};
  function show(i,e){
    var r=hours[i]; if(!r) return;
    var html='<div class="th">'+String(r.hour||0).padStart(2,'0')+':00 – '+String((r.hour||0)+1).padStart(2,'0')+':00</div>'+
      '<div class="tt">报错合计 <b>'+f(r.total)+'</b> 单</div>';
    stages.forEach(function(s){
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
    """06 24小时各环节报错条数：优先真实 hourly_stage（8 环节），缺失时用每小时 B+D 兜底。"""
    stage_rows = ctx.get("hourly_stage") or []
    hours = ctx.get("hourly") or []
    if not hours:
        return ""
    # 只有含 8 环节字段的表才算真数据，避免把旧 6 环节表误读成 8 环节
    real = (len(stage_rows) == 24 and all(any(s in r for s in STAGES8) for r in stage_rows))
    stages = list(STAGES8) if real else [FALLBACK_STAGE]
    colors = dict(STAGE8_COLOR) if real else {FALLBACK_STAGE: FALLBACK_COLOR}
    src_note = ("按创建时间 · 失败原因归 8 大环节" if real
                else "环节细分待生产机字段上线")
    data = []
    if real:
        by_hour = {int(r.get("hour") or 0): r for r in stage_rows}
        for r in hours:
            h = int(r.get("hour") or 0)
            src = by_hour.get(h, {})
            row = {"hour": h}
            for s in stages:
                row[s] = int(src.get(s) or 0)
            row["total"] = sum(row[s] for s in stages)
            data.append(row)
    else:
        for r in hours:
            row = {"hour": int(r.get("hour") or 0), FALLBACK_STAGE: int(r.get("B") or 0) + int(r.get("D") or 0)}
            row["total"] = row[FALLBACK_STAGE]
            data.append(row)
    data.sort(key=lambda x: x["hour"])

    W, H, L, R, T, B = 1040, 300, 46, 12, 24, 46
    pw, ph = W - L - R, H - T - B
    maxv = max(r["total"] for r in data) or 1
    step = pw / 24
    bw = min(step * 0.62, 30)
    out = [f'<svg class="barsvg" viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">']
    for hb in ((0, 8, "#F3F0FB"), (8, 18, "#EFF6FF"), (18, 24, "#FFF5EE")):
        x0 = L + step * hb[0]
        out.append(f'<rect x="{x0:.1f}" y="{T}" width="{step*(hb[1]-hb[0]):.1f}" height="{ph}" fill="{hb[2]}"/>')
    for gy in range(5):
        y = T + ph - ph * gy / 4
        out.append(f'<line x1="{L}" y1="{y:.1f}" x2="{W-R}" y2="{y:.1f}" stroke="#EDF1F6" stroke-width="1"/>')
        out.append(f'<text x="{L-7}" y="{y+4:.1f}" text-anchor="end" font-size="10" fill="#94A3B8">{int(maxv*gy/4)}</text>')
    for hh in (8, 18):
        x = L + step * hh
        out.append(f'<line x1="{x:.1f}" y1="{T}" x2="{x:.1f}" y2="{T+ph}" stroke="#CBD5E1" stroke-width="1" stroke-dasharray="5 4"/>')
    for i, r in enumerate(data):
        x = L + step * i + (step - bw) / 2
        ycursor = T + ph
        for s in reversed(stages):
            n = r[s]
            if not n:
                continue
            h = ph * n / maxv
            ycursor -= h
            out.append(f'<rect x="{x:.1f}" y="{ycursor:.1f}" width="{bw:.1f}" height="{h:.1f}" fill="{colors[s]}"/>')
        if r["total"]:
            out.append(f'<text x="{x+bw/2:.1f}" y="{ycursor-4:.1f}" text-anchor="middle" font-size="9.5" font-weight="700" fill="#475569">{r["total"]}</text>')
        if i % 2 == 0:
            out.append(f'<text x="{x+bw/2:.1f}" y="{T+ph+16:.1f}" text-anchor="middle" font-size="9.5" fill="#94A3B8">{r["hour"]:02d}</text>')
        out.append(f'<rect class="hit" data-i="{i}" x="{L+step*i:.1f}" y="{T}" width="{step:.1f}" height="{ph}" fill="transparent" style="cursor:default"/>')
    out.append(f'<line x1="{L}" y1="{T+ph}" x2="{W-R}" y2="{T+ph}" stroke="#CBD5E1" stroke-width="1"/>')
    out.append('</svg>')

    lg = "".join(f'<span><i style="background:{colors[s]}"></i>{s}</span>' for s in stages)
    meta = {"hours": data, "stages": stages, "colors": colors}
    meta_json = json.dumps(meta, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tot = sum(r["total"] for r in data)
    peak = max(data, key=lambda r: r["total"])
    lead = (f'全天 {num(tot)} 单报错，报错最多的是 '
            f'{peak["hour"]:02d}:00 时段（{num(peak["total"])} 单）。'
            + ("鼠标悬浮看每小时各环节条数。" if real else ""))
    return (
        '<div class="sec"><div class="sec-h"><span class="sec-n">06</span><h2>24 小时各环节报错</h2>'
        f'<span class="sectip">{src_note} · 悬浮看明细</span></div>'
        f'<div class="lead">{lead}</div>'
        f'<div class="stage-lg">{lg}<span>灰虚线＝班次分界（08 / 18 点）</span></div>'
        f'<div class="chartbox" id="errBox">{"".join(out)}<div class="hovertip" id="errTip"></div></div>'
        f'<script type="application/json" id="errMeta">{meta_json}</script><script>{ERR_JS}</script>'
        '</div>'
    )


def build_fail_top5_section(ctx):
    """07 每个环节 top5 报错：合并 fail_reasons_B/D，按 family 归 8 大环节取前 5。"""
    reasons = (ctx.get("fail_b") or []) + (ctx.get("fail_d") or [])
    grouped = {}
    for x in reasons:
        st = stage8_of_family(x.get("family"))
        grouped.setdefault(st, []).append((int(x.get("count") or 0), str(x.get("reason") or "")))
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
    lead = (f'当日报错单按失败原因归到 8 大环节，实际有报错的有 {len(parts)} 个环节、共 {num(total_fail)} 条原因记录；'
            '每个环节列出报错最多的 5 种原因（占全量报错的比例）。')
    return (
        '<div class="sec"><div class="sec-h"><span class="sec-n">07</span><h2>各环节 TOP5 报错</h2>'
        '<span class="sectip">按失败原因归 8 大环节 · 每环节前 5 种</span></div>'
        f'<div class="lead">{lead}</div>'
        '<div class="legend"><span>左：报错原因（自由文本，过长截断）　中：环节内相对条数　右：单量／占全量报错比例</span></div>'
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

    cards_html, plat_sorted = build_platform_cards(ctx["platform"], target, total)
    air_html, air_ok = build_rank_rows(ctx["airline"], target, "airline")
    ch_html, ch_ok = build_rank_rows(ctx["channel"], target, "channel")

    parts = []
    parts.append('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">'
                 '<meta name="viewport" content="width=device-width,initial-scale=1">'
                 '<title>自动化数据汇报</title><style>' + CSS + '</style></head><body><div class="wrap">')

    # 标题区
    metas = (
        f'数据日期 <b>{esc(d)}（{weekday_cn(d)}）</b>',
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
        '<div class="legend"><span>进度条＝全自动成功率，灰色虚线＝目标线；右侧为达标情况与当日订单量</span></div>'
        + air_html + '</div>'
    )

    # 03 渠道
    parts.append(
        '<div class="sec"><div class="sec-h"><span class="sec-n">03</span><h2>渠道自动化成功率</h2>'
        f'<span class="sectip">全量 {len(ctx["channel"])} 个 · 目标 {pct(target, 0)} · 按成功率降序</span></div>'
        f'<div class="lead">{lead_rank(ctx["channel"], target, "渠道", "个", ch_ok)}</div>'
        '<div class="legend"><span>进度条＝全自动成功率，灰色虚线＝目标线；右侧为达标情况与当日订单量</span></div>'
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
    ap.add_argument("--target", type=float, help="覆盖全自动成功率目标（%%）")
    ap.add_argument("--out", help="输出 HTML 路径，默认 output/自动化数据汇报_<日期>.html")
    ap.add_argument("--local", action="store_true", help="只用本地数据，不联网")
    ap.add_argument("--no-fetch", action="store_true", help="跳过 git fetch，用已缓存的 origin/main")
    args = ap.parse_args()

    use_remote = not args.local
    ym, d, day, source, generated_at, md = resolve(
        args.month, args.date, use_remote=use_remote, do_fetch=not args.no_fetch)
    s = day.get("summary") or {}
    row = (day.get("daily") or [{}])[0]
    for k in ("total_orders", "total_segments", "A", "B", "C", "D", "auto_succ_rate"):
        if k not in s or s[k] is None:
            s[k] = row.get("total" if k == "total_orders" else k, 0)

    hourly = sorted((s.get("hourly_today") or {}).get("data") or [],
                    key=lambda r: int(r.get("hour") or 0))
    ctx = {
        "month": ym, "date": d, "summary": s,
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
        "fail_b": day.get("fail_reasons_B") or [],
        "fail_d": day.get("fail_reasons_D") or [],
    }
    out = args.out or os.path.join(BASE, "output", f"自动化数据汇报_{d}.html")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    content = build_html(ctx)
    with open(out, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"数据日期 : {d}（{weekday_cn(d)}）")
    print(f"数据源   : {source}（更新于 {generated_at[:16]}）")
    print(f"订单/航段: {num(s['total_orders'])} / {num(s['total_segments'])}")
    print(f"全自动成功率 / 成功数: {pct(s['auto_succ_rate'])} / {num(s['A'])}")
    print(f"订单转人工 / 全自动失败: {num(s['C'])} / {num(s['B'])}")
    print(f"平台 / 航司 / 渠道: {len(ctx['platform'])} / {len(ctx['airline'])} / {len(ctx['channel'])} 项")
    print(f"逐小时数据 : {len(ctx['hourly'])} 个小时桶 / 当日锁定人数 {ctx['staff_n']}")
    print(f"报错数据  : 每日环节 {len(ctx['daily_stage'])} 天 / 小时环节 {len(ctx['hourly_stage'])} 桶 / 原因 {len(ctx['fail_b'])+len(ctx['fail_d'])} 条")
    print(f"目标值   : {pct(ctx['target'], 0)}")
    print(f"输出文件 : {out}  ({len(content.encode('utf-8')) / 1024:.1f} KB)")
    return out


if __name__ == "__main__":
    main()
