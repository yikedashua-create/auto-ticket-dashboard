var CSS = "\n*{box-sizing:border-box}\nbody{margin:0;background:radial-gradient(ellipse 85% 55% at 50% 0%,#FCFDFF 0%,#F3F6FB 52%,#EDF1F8 100%);color:#1B2430;font-family:-apple-system,BlinkMacSystemFont,\"PingFang SC\",\"Microsoft YaHei\",\"Hiragino Sans GB\",Arial,sans-serif;font-size:14px;line-height:1.7;-webkit-font-smoothing:antialiased}\n.wrap{max-width:1120px;margin:0 auto;padding:32px 22px 60px}\n.head{padding:32px 30px 24px;background:linear-gradient(170deg,#FDFFFF 0%,#F6FAFF 100%);border:1px solid #DDE6F2;border-radius:18px;border-top:4px solid #2563EB;text-align:center;box-shadow:0 6px 24px rgba(30,64,175,.07)}\n.head h1{margin:0;font-size:31px;font-weight:800;letter-spacing:4px;color:#0F172A;line-height:1.45}\n.head .rule{width:64px;height:4px;border-radius:4px;margin:12px auto 16px;background:linear-gradient(90deg,#2563EB,#38BDF8,#2563EB)}\n.head .meta{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 8px;color:#5A6675;font-size:11.5px;line-height:1.5}\n.head .meta .mi{white-space:nowrap;background:#fff;border:1px solid #DCE6F2;border-radius:999px;padding:5px 12px;box-shadow:0 1px 3px rgba(30,64,175,.04)}\n.head .meta .mi b{color:#334155;font-weight:700}\n.boxes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:16px;margin:18px 0 22px}\n.box{position:relative;overflow:hidden;border:1px solid #E2E9F2;border-radius:16px;padding:16px 18px 13px;min-width:0;text-align:left;box-shadow:0 5px 20px rgba(30,64,175,.06)}\n.box:nth-child(1){background:linear-gradient(160deg,#FFFFFF 55%,#F4F9FF)}\n.box:nth-child(2){background:linear-gradient(160deg,#FFFFFF 55%,#F1FBF6)}\n.box:nth-child(3){background:linear-gradient(160deg,#FFFFFF 55%,#FFF9F1)}\n.box:before{content:\"\";position:absolute;left:0;right:0;top:0;height:3px}\n.box:nth-child(1):before{background:linear-gradient(90deg,#2563EB,#60A5FA)}\n.box:nth-child(2):before{background:linear-gradient(90deg,#059669,#34D399)}\n.box:nth-child(3):before{background:linear-gradient(90deg,#F59E0B,#FBBF24)}\n.box .bt{font-size:11.5px;font-weight:700;color:#475569;letter-spacing:1.5px;margin-bottom:6px}\n.box .pair{display:grid;grid-template-columns:1fr;gap:0}\n.box .cell{display:grid;grid-template-columns:1fr 1fr;align-items:center;padding:5px 0;min-height:47px;border-bottom:1px dashed #E6EDF6}\n.box .cell:last-child{border-bottom:none}\n.box .pk{font-size:11.5px;color:#5A6675;white-space:nowrap;text-align:left}\n.box .pk .sub{display:block;font-size:10.5px;line-height:1.3;color:#94A3B8;margin-top:1px}\n.box .pv{font-size:27px;font-weight:800;line-height:1.2;letter-spacing:-.6px;margin:0;font-variant-numeric:tabular-nums;text-align:center}\n.box .pv.blue{color:#2563EB}.box .pv.green{color:#059669}.box .pv.orange{color:#EA580C}.box .pv.red{color:#DC2626}\n.box .pf{margin-top:8px;padding-top:7px;border-top:1px dashed #EDF2F8;font-size:10.5px;color:#94A3B8;min-height:18px;line-height:1.6;text-align:left}\n.sec{background:#fff;border:1px solid #E2E9F2;border-radius:16px;padding:26px 30px 28px;margin-bottom:20px;box-shadow:0 5px 22px rgba(20,38,70,.055)}\n.sec-h{display:flex;align-items:baseline;gap:12px;margin-bottom:6px;flex-wrap:wrap;padding-bottom:11px;border-bottom:1px solid #EEF2F7}\n.sec-n{font-size:12px;font-weight:800;color:#fff;background:linear-gradient(135deg,#2563EB,#3B82F6);padding:4px 10px;border-radius:7px;white-space:nowrap;box-shadow:0 2px 6px rgba(37,99,235,.2)}\n.sec-h h2{margin:0;font-size:20px;font-weight:800;letter-spacing:.2px;color:#16202E}\n.sec-h .sectip{font-size:11.5px;color:#8A95A5;margin-left:auto}\n.lead{margin:12px 0 18px;padding:13px 17px;background:linear-gradient(90deg,#EFF6FF,#F8FBFF);border-left:3px solid #3B82F6;border-radius:0 8px 8px 0;font-size:14px;line-height:1.85;color:#334155}\n.legend{display:flex;gap:18px;flex-wrap:wrap;font-size:11.5px;color:#5A6675;margin:0 0 14px}\n.legend i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}\n.plat{border:1px solid #EAF0F7;border-radius:11px;padding:14px 18px 12px;margin-bottom:10px;break-inside:avoid;background:linear-gradient(180deg,#FFFFFF,#FCFDFE)}\n.plat:hover{border-color:#CFDEF0}\n.plat-h{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap;margin-bottom:9px}\n.plat-nm{font-size:14px;font-weight:700;color:#1B2430}\n.plat-tot{font-size:12px;color:#5A6675}\n.plat-rate{margin-left:auto;font-size:12px;color:#5A6675;white-space:nowrap}\n.plat-rate b{font-size:16px;font-variant-numeric:tabular-nums;margin-left:4px}\n.stack{display:flex;width:100%;height:18px;border-radius:6px;overflow:hidden;background:#F1F4F8;box-shadow:inset 0 1px 2px rgba(15,23,42,.05)}\n.stack i{display:block;height:100%}\n.plat-lg{display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:#8A95A5;margin-top:8px}\n.plat-lg span i{display:inline-block;width:7px;height:7px;border-radius:2px;margin-right:5px}\n.badge{display:inline-block;font-size:10.5px;font-weight:700;padding:1px 7px;border-radius:10px;border:1px solid;white-space:nowrap;margin-left:6px}\n.badge.ok{color:#059669;border-color:#A7F3D0;background:#ECFDF5}\n.badge.mid{color:#2563EB;border-color:#BFDBFE;background:#EFF6FF}\n.badge.bad{color:#DC2626;border-color:#FECACA;background:#FEF2F2}\n.badge.na{color:#64748B;border-color:#E2E8F0;background:#F8FAFC}\n.rank{display:grid;grid-template-columns:170px 1fr 68px 116px 76px;align-items:center;gap:12px;padding:5px 0;border-bottom:1px solid #F1F4F8;break-inside:avoid}\n.rank:last-child{border-bottom:none}\n.rank-nm{font-size:12.5px;font-weight:700;color:#1B2430;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}\n.rank-nm .code{display:inline-block;min-width:30px;color:#2563EB;font-weight:800}\n.rank-bar{position:relative;height:16px;background:#EEF2F7;border-radius:5px;overflow:visible}\n.rank-bar .fill{position:absolute;left:0;top:0;height:100%;border-radius:5px;box-shadow:inset 0 -2px 4px rgba(15,23,42,.06)}\n.rank-bar .target{position:absolute;top:-3px;height:22px;width:0;border-left:2px dashed #64748B;z-index:2}\n.rank-pct{font-size:12.5px;font-weight:800;text-align:right;font-variant-numeric:tabular-nums}\n.rank-cnt{font-size:11.5px;color:#8A95A5;text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}\n.rank-bg{text-align:right}\ntable{width:100%;border-collapse:collapse;margin:16px 0 4px;font-size:12.5px;line-height:1.5}\nth{background:linear-gradient(180deg,#F6F9FC,#EEF3F9);color:#1E293B;font-weight:700;text-align:left;padding:9px 14px;border-bottom:1px solid #D5DFEB;white-space:nowrap}\ntd{padding:8px 14px;border-bottom:1px solid #EFF2F6;color:#334155}\ntr:last-child td{border-bottom:none}\ntd.n,th.n{text-align:right;font-variant-numeric:tabular-nums}\ntbody tr:nth-child(even){background:#FAFBFD}\n.foot{background:linear-gradient(180deg,#FFFFFF,#FBFCFE);border:1px solid #E2E9F2;border-radius:13px;padding:18px 24px;font-size:12px;color:#5A6675;line-height:1.9;box-shadow:0 4px 18px rgba(20,38,70,.05)}\n.foot h3{margin:0 0 8px;font-size:13.5px;color:#1B2430}\n.foot ul{margin:0;padding-left:20px}\n/* 04 逐小时趋势 */\n.shifts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0 16px}\n.shift{border:1px solid #E5E9F0;border-left:3px solid #94A3B8;border-radius:10px;padding:11px 14px;min-width:0}\n.shift.overnight{border-left-color:#7C3AED;background:linear-gradient(135deg,#FBFAFF,#FFFFFF)}\n.shift.day{border-left-color:#2563EB;background:linear-gradient(135deg,#F7FAFF,#FFFFFF)}\n.shift.night{border-left-color:#EA580C;background:linear-gradient(135deg,#FFFCF7,#FFFFFF)}\n.shift .sh{display:flex;align-items:baseline;gap:7px;white-space:nowrap}\n.shift .sh b{font-size:12.5px;color:#1B2430}.shift .sh span{font-size:10.5px;color:#94A3B8}\n.shift .sm{display:flex;justify-content:space-between;gap:8px;margin-top:6px;font-size:11.5px;color:#5A6675}\n.shift .sm em{font-style:normal;font-weight:800;color:#1B2430;font-variant-numeric:tabular-nums}\n.chartbox{position:relative;border:1px solid #EAF0F7;border-radius:11px;padding:10px 10px 3px;background:linear-gradient(180deg,#FFFFFF,#FCFDFE)}\n.chartbox svg{display:block;width:100%;height:auto}\n.hovertip{position:absolute;display:none;pointer-events:none;z-index:30;min-width:216px;background:#fff;border:1px solid #CBD5E1;border-radius:10px;padding:9px 12px;box-shadow:0 10px 26px rgba(15,23,42,.16);font-size:11.5px;line-height:1.65;color:#334155}\n.hovertip .th{font-weight:800;font-size:12.5px;color:#16202E}\n.hovertip .tt{color:#5A6675;margin-bottom:5px}\n.hovertip .tr{display:flex;justify-content:space-between;gap:16px}\n.hovertip .tr i{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px}\n.hovertip .tr b{font-variant-numeric:tabular-nums}\n.hovertip .sep{height:1px;background:#E2E8F0;margin:6px 0}\n.hovertip .sum b{color:#059669;font-size:12.5px}\n/* 05-07 报错 */\n.stage-lg{display:flex;gap:14px;flex-wrap:wrap;font-size:11.5px;color:#5A6675;margin:0 0 12px}\n.stage-lg span i{display:inline-block;width:9px;height:9px;border-radius:2px;margin-right:5px;vertical-align:middle}\n.barsvg{display:block;width:100%;height:auto}\n.errgrp{border:1px solid #EEF1F6;border-radius:10px;padding:12px 16px 10px;margin-bottom:10px;break-inside:avoid}\n.errgrp-h{display:flex;align-items:baseline;gap:9px;margin-bottom:7px;flex-wrap:wrap}\n.errgrp-h b{font-size:13px;color:#1B2430}\n.errgrp-h .dot{display:inline-block;width:9px;height:9px;border-radius:2px}\n.errgrp-h span{font-size:11px;color:#94A3B8}\n.errrow{display:grid;grid-template-columns:1fr 62px 70px 62px;align-items:center;gap:10px;padding:4px 0;border-bottom:1px solid #F4F6F9;font-size:11.5px}\n.errrow:last-child{border-bottom:none}\n.errrow .erm{color:#334155;overflow:visible;white-space:normal;word-break:break-word;line-height:1.55}\n.errrow .erb{height:9px;background:#F1F4F8;border-radius:3px;overflow:hidden}\n.errrow .erb i{display:block;height:100%;border-radius:3px}\n.errrow .ern,.errrow .erp{text-align:right;color:#5A6675;font-variant-numeric:tabular-nums}\n.errrow .erp{color:#94A3B8}\n.hit5{cursor:pointer}\n@media(max-width:900px){.boxes{grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.box{padding:11px 10px 9px}.box .bt{font-size:10px;letter-spacing:1px;margin-bottom:4px}.box .cell{min-height:42px}.box .pv{font-size:18px}.box .pk{font-size:10px}.box .pk .sub{font-size:10px}.box .pf{font-size:9.5px;min-height:16px}.head{padding:22px 14px 20px}.head h1{font-size:24px;letter-spacing:1.5px}.head .meta{font-size:10.5px}.head .meta .mi{padding:3px 8px}.rank{grid-template-columns:130px 1fr 62px 70px}.rank .rank-bg{display:none}.wrap{padding:14px}.shifts{gap:7px}.shift{padding:8px 9px}.shift .sh b{font-size:11px}.shift .sh span{font-size:9px}.shift .sm{font-size:10px}}\n@media print{body{background:#fff}.wrap{max-width:none;padding:0}.head,.sec,.foot,.box{break-inside:avoid;box-shadow:none;border-color:#D9DEE6}@page{margin:12mm}}\n/* ===== 视觉精修层（不改 DOM / 数据 / 口径） ===== */\n:root{--ui-line:#E7EDF5;--ui-mute:#93A1B3;--ui-shadow:0 6px 22px rgba(24,48,90,.08);--ui-shadow-hover:0 13px 32px rgba(24,48,90,.14)}\n.head .meta .mi{padding:6px 13px}\n.head h1{color:#0B1220}\n.boxes{gap:18px}\n.box{padding:18px 20px 15px;border-radius:16px;box-shadow:var(--ui-shadow);transition:transform .18s ease,box-shadow .18s ease}\n.box:hover{transform:translateY(-3px);box-shadow:var(--ui-shadow-hover)}\n.box .bt{display:flex;align-items:center;gap:7px;font-size:11.5px;letter-spacing:1.4px;color:#475569}\n.box .bt:before{content:\"\";width:7px;height:7px;border-radius:50%;flex:none}\n.box:nth-child(1) .bt:before{background:#2563EB}\n.box:nth-child(2) .bt:before{background:#059669}\n.box:nth-child(3) .bt:before{background:#EA580C}\n.box .pv{font-size:30px;letter-spacing:-1px}\n.box .cell{min-height:50px}\n.sec{padding:26px 30px 30px;border-radius:16px;box-shadow:var(--ui-shadow);margin-bottom:22px}\n.sec-h{padding-bottom:13px}\n.sec-n{padding:5px 11px;border-radius:8px;letter-spacing:.5px;box-shadow:0 3px 8px rgba(37,99,235,.28)}\n.sec-h h2{font-size:21px;letter-spacing:.3px}\n.lead{background:linear-gradient(90deg,#EEF5FF 0%,#F7FBFF 72%,#FFFFFF 100%);border-left-width:4px;padding:14px 18px;line-height:1.9}\n.legend,.stage-lg{gap:8px 10px}\n.legend span:not(:only-child),.stage-lg span:not(:last-child){display:inline-flex;align-items:center;gap:5px;background:#F8FAFD;border:1px solid var(--ui-line);border-radius:7px;padding:3px 10px;font-size:11px;line-height:1.5;color:#475569}\n.legend i,.stage-lg span i{margin-right:0;flex:none}\n.legend span:only-child,.stage-lg>span:last-child{border:none;background:none;padding-left:2px;color:var(--ui-mute)}\n.plat{padding:15px 18px 13px;border-radius:12px}\n.plat-nm{font-size:14.5px}\n.stack{height:22px;border-radius:7px}\n.plat-rate b{font-size:17px}\n.shift{border-radius:11px;padding:13px 16px}\n.shift .sm em{font-size:13px}\n.rank{padding:6px 0}\n.rank-bar{height:18px;border-radius:6px}\n.rank-bar .fill{border-radius:6px}\n.rank-nm{font-size:12.5px}\nth{padding:11px 14px;letter-spacing:.3px}\ntd{padding:10px 14px}\ntbody tr:hover{background:#F4F8FE}\n.hovertip{border-radius:12px;box-shadow:0 14px 36px rgba(15,23,42,.2);padding:11px 14px}\n@media(max-width:900px){.box .pv{font-size:19px}.box .bt{font-size:10px;gap:5px}.box .bt:before{width:6px;height:6px}.legend span:not(:only-child),.stage-lg span:not(:last-child){padding:2px 7px;font-size:10px}}\n";
var DONUT_JS = "\n(function(){\n  var box=document.getElementById('donutBox'), tip=document.getElementById('donutTip'), metaEl=document.getElementById('donutMeta');\n  if(!box||!tip||!metaEl) return;\n  var meta; try{meta=JSON.parse(metaEl.textContent);}catch(e){return;}\n  var rows=meta.rows||[], colors=meta.colors||{}, total=meta.total||0;\n  var f=function(n){return Number(n||0).toLocaleString('zh-CN');};\n  function show(i,e){\n    var r=rows[i]; if(!r) return;\n    var share=total?(r.n/total*100).toFixed(2):'0.00';\n    tip.innerHTML='<div class=\"th\"><i style=\"display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;background:'+(colors[r.s]||'#94A3B8')+'\"></i>'+r.s+'</div>'+\n      '<div class=\"tt\">报错 <b>'+f(r.n)+'</b> 单 · 占'+meta.pw+' <b>'+share+'%</b></div>'+\n      '<div class=\"sep\"></div><div class=\"sum\">'+meta.pw+'报错合计 <b>'+f(total)+'</b> 单</div>';\n    tip.style.display='block';\n    var br=box.getBoundingClientRect();\n    var x=e.clientX-br.left+14, y=e.clientY-br.top+10;\n    if(x+tip.offsetWidth>br.width-6) x=e.clientX-br.left-tip.offsetWidth-14;\n    if(x<6) x=6;\n    if(y+tip.offsetHeight>br.height-6) y=br.height-tip.offsetHeight-6;\n    if(y<6) y=6;\n    tip.style.left=x+'px'; tip.style.top=y+'px';\n  }\n  function hide(){tip.style.display='none';}\n  Array.prototype.forEach.call(box.querySelectorAll('.hit5'),function(el){\n    el.addEventListener('mousemove',function(e){show(parseInt(el.getAttribute('data-i'),10),e);});\n    el.addEventListener('mouseleave',hide);\n  });\n})();\n";
var STAGE_TREND_JS = "\n(function(){\n  var box=document.getElementById('errBox'), tip=document.getElementById('errTip'),\n      metaEl=document.getElementById('errMeta');\n  if(!box||!tip||!metaEl) return;\n  var meta; try{meta=JSON.parse(metaEl.textContent);}catch(e){return;}\n  var rows=meta.rows||[], series=meta.series||[], colors=meta.colors||{};\n  var f=function(n){return Number(n||0).toLocaleString('zh-CN');};\n  function show(i,e){\n    var r=rows[i]; if(!r) return;\n    var html='<div class=\"th\">'+String(i).padStart(2,'0')+':00 – '+String(i+1).padStart(2,'0')+':00</div>'+\n      '<div class=\"tt\">报错合计 <b>'+f(r.total)+'</b> 单</div>';\n    series.forEach(function(s){\n      html+='<div class=\"tr\"><span><i style=\"background:'+(colors[s]||'#94A3B8')+'\"></i>'+s+'</span><b>'+f(r[s]||0)+' 单</b></div>';\n    });\n    tip.innerHTML=html;\n    tip.style.display='block';\n    var br=box.getBoundingClientRect();\n    var x=e.clientX-br.left+14, y=e.clientY-br.top+10;\n    if(x+tip.offsetWidth>br.width-6) x=e.clientX-br.left-tip.offsetWidth-14;\n    if(x<6) x=6;\n    if(y+tip.offsetHeight>br.height-6) y=br.height-tip.offsetHeight-6;\n    if(y<6) y=6;\n    tip.style.left=x+'px'; tip.style.top=y+'px';\n  }\n  function hide(){tip.style.display='none';}\n  Array.prototype.forEach.call(box.querySelectorAll('.hit'),function(el){\n    el.addEventListener('mousemove',function(e){show(parseInt(el.getAttribute('data-i'),10),e);});\n    el.addEventListener('mouseleave',hide);\n  });\n})();\n";
var HOUR_JS = "\n(function(){\n  var box=document.getElementById('hourBox'), tip=document.getElementById('hourTip'),\n      metaEl=document.getElementById('hourMeta');\n  if(!box||!tip||!metaEl) return;\n  var meta; try{meta=JSON.parse(metaEl.textContent);}catch(e){return;}\n  var hours=meta.hours||[], staff=meta.staff_n||0, sts=meta.staff_by_hour||[];\n  var f=function(n){return Number(n||0).toLocaleString('zh-CN');};\n  var p=function(v){return Number(v||0).toFixed(1)+'%';};\n  var dot=function(c){return '<i style=\"background:'+c+'\"></i>';};\n  function show(i,e){\n    var r=hours[i]; if(!r) return;\n    var A=r.A||0,B=r.B||0,C=r.C||0,D=r.D||0,t=r.total||0,auto=A+B,need=B+C+D;\n    var st=sts[i]||staff||1;\n    tip.innerHTML='<div class=\"th\">'+String(i+1).padStart(2,'0')+':00</div>'+\n      '<div class=\"tt\">总计 <b>'+f(t)+'</b> 单 · 需处理 <b>'+f(need)+'</b> 单（人均 '+(need/st).toFixed(1)+' 单/人）</div>'+\n      '<div class=\"tr\"><span>'+dot('#059669')+'A 全自动成功</span><b>'+f(A)+' 单 ('+p(auto?A/auto*100:0)+')</b></div>'+\n      '<div class=\"tr\"><span>'+dot('#DC2626')+'B 全自动失败</span><b>'+f(B)+' 单 ('+p(auto?B/auto*100:0)+')</b></div>'+\n      '<div class=\"tr\"><span>'+dot('#EA580C')+'C 订单转人工</span><b>'+f(C)+' 单 ('+p(t?C/t*100:0)+')</b></div>'+\n      '<div class=\"tr\"><span>'+dot('#94A3B8')+'D 订单处理中</span><b>'+f(D)+' 单 ('+p(t?D/t*100:0)+')</b></div>'+\n      '<div class=\"sep\"></div><div class=\"sum\">成功率 <b>'+p(t?A/t*100:0)+'</b> · 覆盖率 '+p(t?auto/t*100:0)+'</div>';\n    tip.style.display='block';\n    var br=box.getBoundingClientRect();\n    var x=e.clientX-br.left+14, y=e.clientY-br.top+10;\n    if(x+tip.offsetWidth>br.width-6) x=e.clientX-br.left-tip.offsetWidth-14;\n    if(x<6) x=6;\n    if(y+tip.offsetHeight>br.height-6) y=br.height-tip.offsetHeight-6;\n    if(y<6) y=6;\n    tip.style.left=x+'px'; tip.style.top=y+'px';\n  }\n  function hide(){tip.style.display='none';}\n  Array.prototype.forEach.call(box.querySelectorAll('.hit'),function(el){\n    el.addEventListener('mousemove',function(e){show(parseInt(el.getAttribute('data-i'),10),e);});\n    el.addEventListener('mouseleave',hide);\n  });\n})();\n";/* ============================================================
   自动化数据汇报 · 浏览器端渲染引擎
   1:1 复刻 gen_daily_report.py 的 build_html 及全部章节函数，
   保证前端实时生成的 HTML 与 Python 离线版数字/口径完全一致。
   输入：ctx（与 Python ctx 同构）；输出：完整 HTML 字符串。
   ============================================================ */
(function (root) {
  'use strict';

  var C_A = "#059669", C_B = "#DC2626", C_C = "#EA580C", C_D = "#94A3B8", BLUE = "#2563EB";
  var STAGES8 = ["人工环节", "系统环节", "预定环节", "支付环节", "取票环节", "验真环节", "回填环节", "平台环节", "其他环节"];
  var STAGE8_COLOR = {
    "人工环节": "#FF6B9D", "系统环节": "#FFD93D", "预定环节": "#FF4757",
    "支付环节": "#FF6348", "取票环节": "#FFA502", "验真环节": "#9C88FF",
    "回填环节": "#70A1FF", "平台环节": "#5F27CD", "其他环节": "#A0B4CC"
  };
  var FALLBACK_STAGE = "未细分报错", FALLBACK_COLOR = "#94A3B8";
  var FB_B = "全自动失败", FB_D = "订单处理中";
  var DONUT_COLORS = ["#FF4757", "#FF6348", "#FFD93D", "#FFA502", "#FF6B9D", "#A0B4CC", "#60A5FA", "#A78BFA", "#34D399"];
  var SHIFTS = [
    ["通宵班", "00:00–08:00", "overnight", [0, 1, 2, 3, 4, 5, 6, 7]],
    ["白班", "08:00–18:00", "day", [8, 9, 10, 11, 12, 13, 14, 15, 16, 17]],
    ["晚班", "18:00–24:00", "night", [18, 19, 20, 21, 22, 23]]
  ];
  var SHIFT_STAFF = { "通宵班": 2, "白班": 8, "晚班": 8 };

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
  }
  function num(v) {
    return Math.round(Number(v || 0)).toLocaleString('en-US');
  }
  function pct(v, d) {
    d = d == null ? 2 : d;
    return Number(v || 0).toFixed(d) + '%';
  }
  function safeDiv(a, b, digits) {
    digits = digits == null ? 2 : digits;
    return b ? parseFloat((Number(a) / Number(b) * 100).toFixed(digits)) : 0.0;
  }
  function weekdayCn(dateStr) {
    var w = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    var dt = new Date(dateStr + 'T00:00:00');
    return isNaN(dt.getTime()) ? '' : w[dt.getDay()];
  }
  function stage8OfFamily(fam) {
    fam = String(fam || '');
    for (var i = 0; i < STAGES8.length; i++) if (fam.indexOf(STAGES8[i]) === 0) return STAGES8[i];
    return "其他环节";
  }
  function stage8Counts(reasons) {
    var c = {}; STAGES8.forEach(function (s) { c[s] = 0; });
    (reasons || []).forEach(function (x) { c[stage8OfFamily(x.family)] += int(x.count); });
    return c;
  }
  function int(v) { return parseInt(v || 0, 10) || 0; }
  function escText(s) {
    var t = String(s == null ? '' : s).replace(/\s+/g, ' ').trim();
    if (!t || t === '(无)') return '（无失败原因）';
    return esc(t);
  }
  function rateClass(rate, target) {
    if (rate >= target) return { cls: "ok", txt: "达标", diff: "+" + (rate - target).toFixed(2) + "%", color: C_A };
    if (rate >= 50) return { cls: "mid", txt: "中等", diff: "差 " + (target - rate).toFixed(2) + "%", color: BLUE };
    return { cls: "bad", txt: "待改", diff: "差 " + (target - rate).toFixed(2) + "%", color: C_B };
  }

  // ---------- 01 平台 / 02-03 航司渠道 ----------
  function buildRankRows(items, target, nameKey) {
    var ordered = items.slice().sort(function (a, b) { return -float(a.auto_succ_rate) + float(b.auto_succ_rate); });
    var rows = [], okN = 0;
    ordered.forEach(function (x) {
      var rate = float(x.auto_succ_rate), autoBase = float(x.A) + float(x.B);
      var cls, txt, diff, color;
      if (autoBase === 0) { cls = "na"; txt = "未走自动"; diff = ""; color = C_D; }
      else if (rate === 0) { cls = "na"; txt = "无自动成功"; diff = ""; color = C_D; }
      else { var rc = rateClass(rate, target); cls = rc.cls; txt = rc.txt; diff = rc.diff; color = rc.color; if (cls === "ok") okN++; }
      var name = esc(x[nameKey]);
      var nm = nameKey === "airline" ? '<span class="code">' + name + '</span>' : '<span>' + name + '</span>';
      rows.push('<div class="rank">' +
        '<div class="rank-nm" title="' + name + '">' + nm + '</div>' +
        '<div class="rank-bar"><i class="target" style="left:' + target.toFixed(2) + '%"></i>' +
        '<i class="fill" style="width:' + rate.toFixed(2) + '%;background:' + color + '"></i></div>' +
        '<div class="rank-pct" style="color:' + color + '">' + pct(rate) + '</div>' +
        '<div class="rank-bg"><span class="badge ' + cls + '">' + (txt + ' ' + diff).trim() + '</span></div>' +
        '<div class="rank-cnt">' + num(x.total) + ' 单</div></div>');
    });
    return { html: rows.join(''), okN: okN };
  }
  function float(v) { var f = parseFloat(v || 0); return isNaN(f) ? 0 : f; }

  function buildPlatformCards(items, target, total) {
    var sorted = items.slice().sort(function (a, b) { return -float(a.total) + float(b.total); });
    var cards = [];
    sorted.forEach(function (x, idx) {
      var tot = float(x.total), rate = float(x.auto_succ_rate);
      var color = rateClass(rate, target).color;
      var segs = [["A 全自动成功", x.A, C_A], ["B 全自动失败", x.B, C_B], ["C 订单转人工", x.C, C_C], ["D 订单处理中", x.D, C_D]];
      var stack = segs.map(function (p) {
        return '<i style="width:' + (tot ? (float(p[1]) / tot * 100).toFixed(3) : '0.000') + '%;background:' + p[2] + '" title="' + p[0] + ' ' + num(p[1]) + ' 单"></i>';
      }).join('');
      var lg = segs.map(function (p) { return '<span><i style="background:' + p[2] + '"></i>' + p[0] + ' ' + num(p[1]) + '</span>'; }).join('');
      cards.push('<div class="plat">' +
        '<div class="plat-h"><span class="plat-nm">' + (idx + 1) + '. ' + esc(x.platform) + '</span>' +
        '<span class="plat-tot">' + num(tot) + ' 单 · 占全量 ' + pct(tot / total * 100) + '</span>' +
        '<span class="plat-rate">全自动成功率<b style="color:' + color + '">' + pct(rate) + '</b></span></div>' +
        '<div class="stack">' + stack + '</div><div class="plat-lg">' + lg + '</div></div>');
    });
    return { html: cards.join(''), items: sorted };
  }

  function buildTable(items) {
    var rows = items.map(function (x) {
      return '<tr><td>' + esc(x.platform) + '</td><td class="n">' + num(x.total) + '</td>' +
        '<td class="n">' + pct(x.auto_succ_rate) + '</td><td class="n">' + num(x.A) + '</td>' +
        '<td class="n">' + num(x.B) + '</td></tr>';
    });
    return '<table><thead><tr><th>平台</th><th class="n">订单数</th><th class="n">全自动成功率</th>' +
      '<th class="n">全自动成功数</th><th class="n">全自动失败数</th></tr></thead><tbody>' + rows.join('') + '</tbody></table>';
  }

  function leadPlatform(items, target, total) {
    var top = items[0];
    var ok = items.filter(function (x) { return float(x.auto_succ_rate) >= target; }).length;
    var large = items.filter(function (x) { return int(x.total) >= 100; });
    if (!large.length) large = items;
    var best = large.slice().sort(function (a, b) { return -float(a.auto_succ_rate) + float(b.auto_succ_rate); })[0];
    return '共 ' + items.length + ' 个平台、' + num(total) + ' 单。单量最大的是' + esc(top.platform) +
      '，' + num(top.total) + ' 单、全自动成功率 ' + pct(top.auto_succ_rate) +
      '；在订单量 100 单以上的平台里，' + esc(best.platform) + '成功率最高 ' + pct(best.auto_succ_rate) +
      '（' + num(best.total) + ' 单）。按 ' + pct(target, 0) + ' 的目标看，' + items.length + ' 个平台里 ' + ok + ' 个达标。';
  }

  function leadRank(items, target, label, unit, okN) {
    var big = items.slice().sort(function (a, b) { return -int(a.total) + int(b.total); })[0];
    var name = esc(big.channel || big.airline);
    return label + '共 ' + items.length + ' ' + unit + '，按全自动成功率从高到低排列，' +
      okN + ' ' + unit + '达到 ' + pct(target, 0) + ' 目标；单量最大的是' + name +
      '，' + num(big.total) + ' 单、成功率 ' + pct(big.auto_succ_rate) + '。';
  }

  // ---------- 04 逐小时趋势 ----------
  function hourlyValue(row, key) {
    if (key === "A" || key === "B") {
      var base = int(row.A) + int(row.B);
      return base ? float(row[key]) / base * 100 : 0.0;
    }
    var t = int(row.total);
    return t ? float(row[key]) / t * 100 : 0.0;
  }
  function buildShiftCards(hours, staffN) {
    var cards = [], stats = {};
    SHIFTS.forEach(function (sh) {
      var name = sh[0], span = sh[1], cls = sh[2], rng = sh[3];
      var g = hours.filter(function (r) { return rng.indexOf(int(r.hour)) >= 0; });
      function sum(k) { return g.reduce(function (a, r) { return a + int(r[k]); }, 0); }
      var t = sum('total'), a = sum('A'), b = sum('B'), c = sum('C'), d = sum('D');
      var need = b + c + d, rate = (a + b) ? a / (a + b) * 100 : 0.0, per = need / SHIFT_STAFF[name];
      stats[name] = { total: t, need: need, per: per, rate: rate };
      cards.push('<div class="shift ' + cls + '"><div class="sh"><b>' + name + '</b><span>' + span + '</span></div>' +
        '<div class="sm"><span>需处理单 <em>' + num(need) + '</em></span>' +
        '<span>人均处理 <em>' + per.toFixed(1) + '</em> 单/人</span></div>' +
        '<div class="sm"><span>全自动成功率 <em>' + pct(rate) + '</em></span></div></div>');
    });
    return { html: cards.join(''), stats: stats };
  }
  function leadHourly(total, stats, needAll) {
    var over = stats["通宵班"], day = stats["白班"], night = stats["晚班"];
    var totalStaff = SHIFT_STAFF["通宵班"] + SHIFT_STAFF["白班"] + SHIFT_STAFF["晚班"];
    var perAll = totalStaff ? needAll / totalStaff : 0.0;
    var rates = [stats["通宵班"].rate, stats["白班"].rate, stats["晚班"].rate];
    return '全天 ' + num(total) + ' 单按创建时间分布：白班 ' + num(day.total) + ' 单、晚班 ' + num(night.total) +
      ' 单、通宵班 ' + num(over.total) + ' 单。除全自动成功外，实际需处理 ' + num(needAll) + ' 单，人均处理 ' +
      perAll.toFixed(1) + ' 单（白班 ' + day.per.toFixed(1) + '、晚班 ' + night.per.toFixed(1) + '、通宵班 ' + over.per.toFixed(1) +
      '）。三个班次的全自动成功率分别是通宵班 ' + pct(over.rate) + '、白班 ' + pct(day.rate) + '、晚班 ' + pct(night.rate) +
      '，相差 ' + (Math.max.apply(null, rates) - Math.min.apply(null, rates)).toFixed(2) + ' 个百分点。';
  }
  function buildHourlySvg(hours) {
    var W = 1080, H = 372, L = 52, R = 18, T = 46, B = 42;
    var pw = W - L - R, ph = H - T - B, step = pw / 24, bw = step * 0.66;
    function X(i) { return L + (i + 0.5) * step; }
    function Y(v) { return T + ph - (Math.max(0, Math.min(100, v)) / 100 * ph); }
    var p = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="逐小时四路径比率折线图">'];
    [[0, 8, "#F5F3FF", "通宵班 00:00–08:00"], [8, 18, "#EFF6FF", "白班 08:00–18:00"], [18, 24, "#FFF7ED", "晚班 18:00–24:00"]].forEach(function (b) {
      var x0 = L + b[0] * step, x1 = L + b[1] * step;
      p.push('<rect x="' + x0.toFixed(1) + '" y="' + T + '" width="' + (x1 - x0).toFixed(1) + '" height="' + ph + '" fill="' + b[2] + '" opacity="0.7"/>');
      p.push('<text x="' + ((x0 + x1) / 2).toFixed(1) + '" y="' + (T - 12) + '" text-anchor="middle" font-size="11" font-weight="700" fill="#64748B">' + b[3] + '</text>');
    });
    for (var v = 0; v <= 100; v += 20) {
      var y = Y(v);
      p.push('<line x1="' + L + '" y1="' + y.toFixed(1) + '" x2="' + (W - R) + '" y2="' + y.toFixed(1) + '" stroke="#E2E8F0" stroke-width="1"/>');
      p.push('<text x="' + (L - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end" font-size="10.5" fill="#94A3B8">' + v + '%</text>');
    }
    [8, 18].forEach(function (a) {
      var x = L + a * step;
      p.push('<line x1="' + x.toFixed(1) + '" y1="' + T + '" x2="' + x.toFixed(1) + '" y2="' + (T + ph) + '" stroke="#94A3B8" stroke-width="1.4" stroke-dasharray="6 4"/>');
    });
    var series = [["A 全自动成功率", "A", C_A, "2.6", false], ["B 全自动失败率", "B", C_B, "2.2", false],
      ["C 订单转人工率", "C", C_C, "2.0", false], ["D 订单处理中率", "D", C_D, "1.8", true]];
    series.forEach(function (se) {
      var pts = hours.map(function (r, i) { return X(i).toFixed(1) + ',' + Y(hourlyValue(r, se[1])).toFixed(1); });
      var da = se[4] ? ' stroke-dasharray="5 3"' : '';
      p.push('<polyline points="' + pts.join(' ') + '" fill="none" stroke="' + se[2] + '" stroke-width="' + se[3] + '" stroke-linejoin="round" stroke-linecap="round"' + da + '/>');
      hours.forEach(function (r, i) {
        p.push('<circle cx="' + X(i).toFixed(1) + '" cy="' + Y(hourlyValue(r, se[1])).toFixed(1) + '" r="2.6" fill="' + se[2] + '"/>');
      });
    });
    ["A", "B"].forEach(function (key) {
      var vals = hours.map(function (r) { return hourlyValue(r, key); });
      if (!vals.length) return;
      var mx = 0, mn = 0;
      for (var i = 1; i < vals.length; i++) { if (vals[i] > vals[mx]) mx = i; if (vals[i] < vals[mn]) mn = i; }
      [[mx, "#059669"], [mn, "#DC2626"]].forEach(function (q) {
        var cx = X(q[0]), cy = Y(vals[q[0]]);
        p.push('<circle cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="8" fill="' + q[1] + '" stroke="#fff" stroke-width="2"/>');
        p.push('<text x="' + cx.toFixed(1) + '" y="' + (cy + 3).toFixed(1) + '" text-anchor="middle" font-size="8.5" font-weight="800" fill="#fff">' + vals[q[0]].toFixed(0) + '</text>');
      });
    });
    for (var i = 0; i < 24; i++) {
      var x = X(i);
      p.push('<text x="' + x.toFixed(1) + '" y="' + (T + ph + 18) + '" text-anchor="middle" font-size="10" fill="#94A3B8">' + String(i + 1).padStart(2, '0') + ':00</text>');
      p.push('<rect class="hit" data-i="' + i + '" x="' + (L + i * step).toFixed(1) + '" y="' + T + '" width="' + step.toFixed(1) + '" height="' + ph + '" fill="transparent" pointer-events="all" style="cursor:crosshair"/>');
    }
    p.push('<text x="' + (W - R) + '" y="' + (H - 6) + '" text-anchor="end" font-size="9.5" fill="#94A3B8">横轴为小时区间右端点，01:00 = 00:00–01:00</text></svg>');
    return p.join('');
  }
  function buildHourSection(ctx) {
    var hours = ctx.hourly || [];
    if (!hours.length) return '';
    var staffN = int(ctx.staff_n), total = int(ctx.summary.total_orders);
    var sc = buildShiftCards(hours, staffN);
    var needAll = hours.reduce(function (a, r) { return a + int(r.B) + int(r.C) + int(r.D); }, 0);
    var staffByHour = hours.map(function (r) {
      var h = int(r.hour);
      for (var i = 0; i < SHIFTS.length; i++) if (SHIFTS[i][3].indexOf(h) >= 0) return SHIFT_STAFF[SHIFTS[i][0]];
      return staffN;
    });
    var meta = { staff_n: staffN, staff_by_hour: staffByHour,
      hours: hours.map(function (r) { return { hour: int(r.hour), total: int(r.total), A: int(r.A), B: int(r.B), C: int(r.C), D: int(r.D) }; }) };
    return '<div class="sec"><div class="sec-h"><span class="sec-n">04</span><h2>逐小时自动化趋势</h2>' +
      '<span class="sectip">按创建时间 · 0–24 点 · 鼠标悬浮看明细</span></div>' +
      '<div class="lead">' + leadHourly(total, sc.stats, needAll) + '</div>' +
      '<div class="shifts">' + sc.html + '</div>' +
      '<div class="legend"><span><i style="background:' + C_A + '"></i>A 全自动成功率</span>' +
      '<span><i style="background:' + C_B + '"></i>B 全自动失败率</span>' +
      '<span><i style="background:' + C_C + '"></i>C 订单转人工率</span>' +
      '<span><i style="background:' + C_D + '"></i>D 订单处理中率</span>' +
      '<span>灰色虚线＝班次分界；彩色圆点为各路径的高／低点</span></div>' +
      '<div class="chartbox" id="hourBox">' + buildHourlySvg(hours) + '<div class="hovertip" id="hourTip"></div></div>' +
      '<script type="application/json" id="hourMeta">' + jsonInline(meta) + '</script><script>' + HOUR_JS + '</script></div>';
  }

  // ---------- 05 每日各环节报错（环形图） ----------
  function buildDailyStageSection(ctx) {
    var reasons = ctx.fail_b || [], counts = stage8Counts(reasons);
    var pairs = STAGES8.map(function (s) { return [s, int(counts[s])]; });
    var total = pairs.reduce(function (a, p) { return a + p[1]; }, 0);
    if (!total) return '';
    var d = ctx.date, pw = ctx.period_word || '当天';
    var ranked = pairs.filter(function (p) { return p[1]; }).sort(function (a, b) { return b[1] - a[1]; });
    var colors = {};
    ranked.forEach(function (p, i) { colors[p[0]] = DONUT_COLORS[i % DONUT_COLORS.length]; });
    var cx = 250, cy = 160, r = 108, sw = 46, circ = 2 * Math.PI * r;
    var out = ['<svg class="barsvg" viewBox="0 0 1080 330" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="各环节报错占比环形图">'];
    out.push('<circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="#EEF2F7" stroke-width="' + sw + '"/>');
    var offset = 0;
    ranked.forEach(function (p, i) {
      var s = p[0], n = p[1], seg = n / total * circ;
      out.push('<g class="hit5" data-i="' + i + '"><circle cx="' + cx + '" cy="' + cy + '" r="' + r + '" fill="none" stroke="' + colors[s] +
        '" stroke-width="' + sw + '" stroke-dasharray="' + seg.toFixed(2) + ' ' + (circ - seg).toFixed(2) +
        '" stroke-dashoffset="' + (-offset).toFixed(2) + '" transform="rotate(-90 ' + cx + ' ' + cy + ')"/></g>');
      offset += seg;
    });
    out.push('<text x="' + cx + '" y="154" text-anchor="middle" font-size="40" font-weight="800" fill="#16202E">' + num(total) + '</text>');
    out.push('<text x="' + cx + '" y="180" text-anchor="middle" font-size="13" fill="#8A95A5">单报错</text>');
    out.push('<text x="500" y="24" font-size="11.5" font-weight="700" fill="#8A95A5">按报错量排序</text>');
    var maxn = ranked[0][1] || 1;
    ranked.forEach(function (p, i) {
      var s = p[0], n = p[1], y = 32 + i * 40, share = n / total * 100, bw = 250 * n / maxn;
      out.push('<g class="hit5" data-i="' + i + '">' +
        '<rect x="500" y="' + y + '" width="12" height="12" rx="3" fill="' + colors[s] + '"/>' +
        '<text x="520" y="' + (y + 13) + '" font-size="13" font-weight="700" fill="#1B2430">' + esc(s) + '</text>' +
        '<text x="520" y="' + (y + 31) + '" font-size="10.5" fill="#94A3B8">占比 ' + share.toFixed(1) + '%</text>' +
        '<rect x="650" y="' + (y + 10) + '" width="250" height="8" rx="4" fill="#F1F4F8"/>' +
        '<rect x="650" y="' + (y + 10) + '" width="' + bw.toFixed(1) + '" height="8" rx="4" fill="' + colors[s] + '"/>' +
        '<text x="914" y="' + (y + 18) + '" font-size="14" font-weight="800" fill="#1B2430">' + num(n) + '</text></g>');
    });
    out.push('</svg>');
    var top3 = ranked.slice(0, 3), zeros = pairs.filter(function (p) { return !p[1]; }).map(function (p) { return p[0]; });
    var lead = esc(d) + ' ' + pw + '全自动失败 ' + num(total) + ' 单，按失败原因归到 ' + pairs.length +
      ' 类环节（口径同看板「失败原因排行」B 路径）。报错最多的是 ' +
      top3.map(function (p) { return p[0] + ' ' + num(p[1]) + ' 单（' + pct(p[1] / total * 100) + '）'; }).join('、') + '。';
    if (zeros.length) lead += pw + '有 ' + zeros.length + ' 个环节没有报错：' + zeros.join('、') + '。';
    var meta = { rows: ranked.map(function (p) { return { s: p[0], n: p[1] }; }), colors: colors, total: total, pw: pw };
    return '<div class="sec"><div class="sec-h"><span class="sec-n">05</span><h2>每日各环节报错</h2>' +
      '<span class="sectip">' + esc(d) + ' · 共 ' + num(total) + ' 单 · 环形占比图，悬浮看明细</span></div>' +
      '<div class="lead">' + lead + '</div>' +
      '<div class="chartbox" id="donutBox">' + out.join('') + '<div class="hovertip" id="donutTip"></div></div>' +
      '<script type="application/json" id="donutMeta">' + jsonInline(meta) + '</script><script>' + DONUT_JS + '</script></div>';
  }

  // ---------- 06 24小时各环节报错（堆叠柱） ----------
  function buildStageStackedSvg(rows, series, colors) {
    var W = 1080, H = 380, L = 52, R = 18, T = 46, B = 42;
    var pw = W - L - R, ph = H - T - B, step = pw / 24, bw = step * 0.66;
    function X(i) { return L + (i + 0.5) * step; }
    var maxv = Math.max.apply(null, rows.map(function (r) { return r.total; }).concat([1])) || 1;
    var top = Math.max(20, Math.ceil(maxv / 20) * 20);
    function Y(v) { return T + ph - (Math.max(0, Math.min(top, v)) / top * ph); }
    var p = ['<svg viewBox="0 0 ' + W + ' ' + H + '" role="img" aria-label="24 小时各环节报错堆叠柱状图" xmlns="http://www.w3.org/2000/svg">'];
    [[0, 8, "#F5F3FF", "通宵班 00:00–08:00"], [8, 18, "#EFF6FF", "白班 08:00–18:00"], [18, 24, "#FFF7ED", "晚班 18:00–24:00"]].forEach(function (b) {
      var x0 = L + b[0] * step, x1 = L + b[1] * step;
      p.push('<rect x="' + x0.toFixed(1) + '" y="' + T + '" width="' + (x1 - x0).toFixed(1) + '" height="' + ph + '" fill="' + b[2] + '" opacity="0.7"/>');
      p.push('<text x="' + ((x0 + x1) / 2).toFixed(1) + '" y="' + (T - 12) + '" text-anchor="middle" font-size="11" font-weight="700" fill="#64748B">' + b[3] + '</text>');
    });
    for (var k = 0; k <= 5; k++) {
      var v = Math.floor(top * k / 5), y = Y(v);
      p.push('<line x1="' + L + '" y1="' + y.toFixed(1) + '" x2="' + (W - R) + '" y2="' + y.toFixed(1) + '" stroke="#E2E8F0" stroke-width="1"/>');
      p.push('<text x="' + (L - 8) + '" y="' + (y + 4).toFixed(1) + '" text-anchor="end" font-size="10.5" fill="#94A3B8">' + v + '</text>');
    }
    [8, 18].forEach(function (a) {
      var x = L + a * step;
      p.push('<line x1="' + x.toFixed(1) + '" y1="' + T + '" x2="' + x.toFixed(1) + '" y2="' + (T + ph) + '" stroke="#94A3B8" stroke-width="1.4" stroke-dasharray="6 4"/>');
    });
    rows.forEach(function (r, i) {
      var x = X(i) - bw / 2, acc = 0;
      series.forEach(function (s) {
        var v = int(r[s]);
        if (v <= 0) return;
        var y0 = Y(acc + v), y1 = Y(acc);
        p.push('<rect x="' + x.toFixed(1) + '" y="' + y0.toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + (y1 - y0).toFixed(1) + '" fill="' + colors[s] + '" stroke="#FFFFFF" stroke-width="0.6"/>');
        acc += v;
      });
      if (r.total > 0) p.push('<text x="' + X(i).toFixed(1) + '" y="' + (Y(r.total) - 4).toFixed(1) + '" text-anchor="middle" font-size="9.5" font-weight="700" fill="#334155">' + r.total + '</text>');
    });
    for (var i = 0; i < 24; i++) {
      var x = X(i);
      if (i % 2 === 0) p.push('<text x="' + x.toFixed(1) + '" y="' + (T + ph + 18) + '" text-anchor="middle" font-size="10" fill="#94A3B8">' + String(i + 1).padStart(2, '0') + ':00</text>');
      p.push('<rect class="hit" data-i="' + i + '" x="' + (L + i * step).toFixed(1) + '" y="' + T + '" width="' + step.toFixed(1) + '" height="' + ph + '" fill="transparent" pointer-events="all" style="cursor:crosshair"/>');
    }
    p.push('<text x="' + (W - R) + '" y="' + (H - 6) + '" text-anchor="end" font-size="9.5" fill="#94A3B8">横轴为小时区间右端点，01:00 = 00:00–01:00；柱高＝该小时报错单数，色块＝环节构成</text></svg>');
    return p.join('');
  }
  function buildHourlyStageSection(ctx) {
    var stageRowsB = ctx.hourly_stage_B || [], stageRowsAB = ctx.hourly_stage || [], hours = ctx.hourly || [];
    if (!hours.length) return '';
    function valid(rows) { return rows.length === 24 && rows.every(function (r) { return STAGES8.some(function (s) { return Object.prototype.hasOwnProperty.call(r, s); }); }); }
    var hasB = valid(stageRowsB), hasAB = valid(stageRowsAB), real = hasB || hasAB;
    var stageRows = hasB ? stageRowsB : (hasAB ? stageRowsAB : []);
    var colors = {}, series;
    if (real) { STAGES8.forEach(function (s) { colors[s] = STAGE8_COLOR[s]; }); series = STAGES8.slice(); }
    else { colors[FB_B] = C_B; colors[FB_D] = C_D; series = [FB_B, FB_D]; }
    var caliber = hasB ? "纯 B 全自动失败 · 口径同看板" : (hasAB ? "B+D 全自动失败＋订单处理中" : "真实 B/D 两段");
    var srcNote = real ? ("按创建时间 · 失败原因归 8 大环节 · " + caliber + " · 堆叠柱") : "按创建时间 · 真实 B/D 两段 · 环节细分待字段上线";
    var data = [];
    if (real) {
      var byHour = {}; stageRows.forEach(function (r) { byHour[int(r.hour)] = r; });
      hours.forEach(function (r) {
        var h = int(r.hour), src = byHour[h] || {}, row = { hour: h };
        series.forEach(function (s) { row[s] = int(src[s]); });
        row.total = series.reduce(function (a, s) { return a + row[s]; }, 0);
        data.push(row);
      });
    } else {
      hours.forEach(function (r) {
        var row = { hour: int(r.hour), "全自动失败": int(r.B), "订单处理中": int(r.D) };
        row.total = row[FB_B] + row[FB_D]; data.push(row);
      });
    }
    data.sort(function (a, b) { return a.hour - b.hour; });
    var meta = { rows: data, series: series, colors: colors };
    var lg = series.map(function (s) { return '<span><i style="background:' + colors[s] + '"></i>' + s + '</span>'; }).join('');
    var tot = data.reduce(function (a, r) { return a + r.total; }, 0);
    var peak = data.slice().sort(function (a, b) { return b.total - a.total; })[0] || { hour: 0, total: 0 };
    var tail = hasB ? "每根柱按环节分色堆叠，口径为纯 B 全自动失败（同看板），悬浮看每小时各环节条数。"
      : (hasAB ? "每根柱按环节分色堆叠；本地数据尚无纯 B 小时环节字段，此处为 B＋D 合计（含订单处理中），生产机补 pure-B 字段后自动切换。"
        : "当前数据没有按小时拆分的环节字段，先按真实结果画出全自动失败 / 订单处理中两段；生产机补上字段后，这里会自动变成 8 个环节分色堆叠。");
    var lead = '全天 ' + num(tot) + ' 单' + (hasB ? '全自动失败' : '报错') + '，最多的是 ' +
      String(peak.hour).padStart(2, '0') + ':00 时段（' + num(peak.total) + ' 单）。' + tail;
    return '<div class="sec"><div class="sec-h"><span class="sec-n">06</span><h2>24 小时各环节报错</h2>' +
      '<span class="sectip">' + srcNote + ' · 悬浮看明细</span></div>' +
      '<div class="lead">' + lead + '</div>' +
      '<div class="stage-lg">' + lg + '<span>灰虚线＝班次分界（08 / 18 点）</span></div>' +
      '<div class="chartbox" id="errBox">' + buildStageStackedSvg(data, series, colors) + '<div class="hovertip" id="errTip"></div></div>' +
      '<script type="application/json" id="errMeta">' + jsonInline(meta) + '</script><script>' + STAGE_TREND_JS + '</script></div>';
  }

  // ---------- 07 各环节 TOP5 报错 ----------
  function buildFailTop5Section(ctx) {
    var reasons = ctx.fail_b || [], grouped = {}, merged = {};
    reasons.forEach(function (x) {
      var st = stage8OfFamily(x.family);
      var label = String(x.near_reason || '').trim() || String(x.full || '').trim() || String(x.reason || '').trim();
      var key = st + '\u0000' + label;
      merged[key] = (merged[key] || 0) + int(x.count);
    });
    Object.keys(merged).forEach(function (key) {
      var parts = key.split('\u0000'), st = parts[0], label = parts[1];
      if (!grouped[st]) grouped[st] = [];
      grouped[st].push([merged[key], label]);
    });
    if (!Object.keys(grouped).length) return '';
    var partsSec = [], totalFail = 0;
    STAGES8.forEach(function (st) {
      (grouped[st] || []).forEach(function (p) { totalFail += p[0]; });
    });
    STAGES8.forEach(function (st) {
      var items = (grouped[st] || []).slice().sort(function (a, b) { return b[0] - a[0]; }).slice(0, 5);
      if (!items.length) return;
      var stSum = (grouped[st] || []).reduce(function (a, p) { return a + p[0]; }, 0);
      var mx = items[0][0] || 1;
      var rows = items.map(function (it) {
        var n = it[0], reason = it[1];
        return '<div class="errrow">' +
          '<div class="erm" title="' + esc(reason.replace(/\s+/g, ' ').trim()) + '">' + escText(reason) + '</div>' +
          '<div class="erb"><i style="width:' + (n / mx * 100).toFixed(1) + '%;background:' + STAGE8_COLOR[st] + '"></i></div>' +
          '<div class="ern">' + num(n) + ' 单</div>' +
          '<div class="erp">' + (totalFail ? pct(n / totalFail * 100) : '0.00%') + '</div></div>';
      });
      partsSec.push('<div class="errgrp"><div class="errgrp-h">' +
        '<i class="dot" style="background:' + STAGE8_COLOR[st] + '"></i><b>' + st + '</b>' +
        '<span>合计 ' + num(stSum) + ' 单 · 下列为该环节报错最多的 5 种</span></div>' + rows.join('') + '</div>');
    });
    var pw = ctx.period_word || '当天';
    var lead = pw + '全自动失败单按失败原因归到 8 大环节，实际有报错的有 ' + partsSec.length +
      ' 个环节、共 ' + num(totalFail) + ' 单；每个环节列出报错最多的 5 种原因（占全量失败的比例，口径同看板 B 路径）。';
    return '<div class="sec"><div class="sec-h"><span class="sec-n">07</span><h2>各环节 TOP5 报错</h2>' +
      '<span class="sectip">全自动失败 B 口径 · 归 8 大环节 · 每环节前 5 种</span></div>' +
      '<div class="lead">' + lead + '</div>' +
      '<div class="legend"><span>左：失败原因（与看板口径一致，完整显示）　中：环节内相对条数　右：单量／占全量报错比例</span></div>' +
      partsSec.join('') + '</div>';
  }

  function jsonInline(obj) {
    return JSON.stringify(obj).replace(/<\//g, '<\\/');
  }

  // ---------- 主入口：复刻 build_html ----------
  function buildHtml(ctx) {
    var d = ctx.date, s = ctx.summary;
    var total = int(s.total_orders), seg = int(s.total_segments);
    var A = int(s.A), B = int(s.B), C = int(s.C), D = int(s.D);
    var succ = float(s.auto_succ_rate), target = ctx.target;
    var pw = ctx.period_word || '当天';
    var pc = buildPlatformCards(ctx.platform, target, total);
    var platSorted = pc.items;
    var air = buildRankRows(ctx.airline, target, "airline");
    var ch = buildRankRows(ctx.channel, target, "channel");
    var parts = [];
    parts.push('<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">' +
      '<meta name="viewport" content="width=device-width,initial-scale=1"><title>自动化数据汇报</title><style>' + CSS + '</style></head><body><div class="wrap">');
    var dateCn = d.indexOf('~') >= 0 ? (esc(d) + ' · 共 ' + int(ctx.summary.total_days || 1) + ' 天') : (esc(d) + '（' + weekdayCn(d) + '）');
    var metas = ['数据日期 <b>' + dateCn + '</b>',
      '数据更新 <b>' + esc(String(ctx.generated_at || '').slice(0, 16)) + '</b>',
      '全自动成功率目标 <b>' + pct(target, 0) + '</b>'];
    parts.push('<div class="head"><h1>自动化数据汇报</h1><div class="rule"></div><div class="meta">' +
      metas.map(function (m) { return '<span class="mi">' + m + '</span>'; }).join('') + '</div></div>');
    parts.push('<div class="boxes">');
    parts.push('<div class="box"><div class="bt">整体规模</div><div class="pair">' +
      '<div class="cell"><div class="pk">订单总数</div><div class="pv blue">' + num(total) + '</div></div>' +
      '<div class="cell"><div class="pk">航段总数</div><div class="pv blue">' + num(seg) + '</div></div></div>' +
      '<div class="pf">平均每单 ' + (seg / total).toFixed(2) + ' 个航段</div></div>');
    parts.push('<div class="box"><div class="bt">自动出票结果</div><div class="pair">' +
      '<div class="cell"><div class="pk">全自动成功率</div><div class="pv green">' + pct(succ) + '</div></div>' +
      '<div class="cell"><div class="pk">全自动成功数</div><div class="pv green">' + num(A) + '</div></div></div>' +
      '<div class="pf">占全量 ' + pct(A / total * 100) + '</div></div>');
    parts.push('<div class="box"><div class="bt">转人工与失败</div><div class="pair">' +
      '<div class="cell"><div class="pk">订单转人工<span class="sub">（手工政策转人工）</span></div><div class="pv orange">' + num(C) + '</div></div>' +
      '<div class="cell"><div class="pk">全自动失败</div><div class="pv red">' + num(B) + '</div></div></div>' +
      '<div class="pf">占全量：转人工 ' + pct(C / total * 100) + '　失败 ' + pct(B / total * 100) + '</div></div>');
    parts.push('</div>');
    parts.push('<div class="sec"><div class="sec-h"><span class="sec-n">01</span><h2>各平台对比</h2>' +
      '<span class="sectip">按订单量降序 · 堆叠条为 4 路径构成</span></div>' +
      '<div class="lead">' + leadPlatform(platSorted, target, total) + '</div>' +
      '<div class="legend"><span><i style="background:' + C_A + '"></i>A 全自动成功</span>' +
      '<span><i style="background:' + C_B + '"></i>B 全自动失败</span>' +
      '<span><i style="background:' + C_C + '"></i>C 订单转人工</span>' +
      '<span><i style="background:' + C_D + '"></i>D 订单处理中</span></div>' +
      pc.html + buildTable(platSorted) + '</div>');
    parts.push('<div class="sec"><div class="sec-h"><span class="sec-n">02</span><h2>航司自动化成功率</h2>' +
      '<span class="sectip">全量 ' + ctx.airline.length + ' 家 · 目标 ' + pct(target, 0) + ' · 按成功率降序</span></div>' +
      '<div class="lead">' + leadRank(ctx.airline, target, "航司", "家", air.okN) + '</div>' +
      '<div class="legend"><span>进度条＝全自动成功率，灰色虚线＝目标线；右侧为达标情况与' + pw + '订单量</span></div>' + air.html + '</div>');
    parts.push('<div class="sec"><div class="sec-h"><span class="sec-n">03</span><h2>渠道自动化成功率</h2>' +
      '<span class="sectip">全量 ' + ctx.channel.length + ' 个 · 目标 ' + pct(target, 0) + ' · 按成功率降序</span></div>' +
      '<div class="lead">' + leadRank(ctx.channel, target, "渠道", "个", ch.okN) + '</div>' +
      '<div class="legend"><span>进度条＝全自动成功率，灰色虚线＝目标线；右侧为达标情况与' + pw + '订单量</span></div>' + ch.html + '</div>');
    parts.push(buildHourSection(ctx));
    parts.push(buildDailyStageSection(ctx));
    parts.push(buildHourlyStageSection(ctx));
    parts.push(buildFailTop5Section(ctx));
    parts.push('</div></body></html>');
    return parts.join('');
  }

  // ---------- 区间合并：复刻 merge_days ----------
  function mergeDays(days, start, end) {
    days = days.slice().sort(function (a, b) { return String(a.date || '').localeCompare(String(b.date || '')); });
    var n = days.length;
    if (!n) return null;
    function sm(x) { return x.summary || {}; }
    function sum(key) { return days.reduce(function (a, x) { return a + int(sm(x)[key]); }, 0); }
    var tot = sum('total_orders'), seg = sum('total_segments');
    var A = sum('A'), B = sum('B'), C = sum('C'), D = sum('D'), auto = A + B;
    var profit = days.reduce(function (a, x) { return a + float(sm(x).total_profit); }, 0);
    var profitPos = sum('profit_pos');
    var summary = {
      month: start + '~' + end, total_days: n, total_orders: tot, total_segments: seg,
      A: A, B: B, C: C, D: D,
      A_ratio: safeDiv(A, tot), B_ratio: safeDiv(B, tot), C_ratio: safeDiv(C, tot), D_ratio: safeDiv(D, tot),
      auto_coverage_rate: safeDiv(auto, tot), auto_succ_rate: safeDiv(A, tot), B_to_manual_rate: safeDiv(B, auto),
      total_profit: parseFloat(profit.toFixed(2)), avg_profit: tot ? parseFloat((profit / tot).toFixed(2)) : 0.0,
      profit_pos: profitPos, profit_pos_rate: safeDiv(profitPos, tot)
    };
    // 逐小时
    var hourMap = {};
    days.forEach(function (x) {
      var ht = sm(x).hourly_today || {};
      (ht.data || []).forEach(function (r) {
        var h = int(r.hour);
        if (!hourMap[h]) hourMap[h] = { hour: h, total: 0, A: 0, B: 0, C: 0, D: 0 };
        ['total', 'A', 'B', 'C', 'D'].forEach(function (k) { hourMap[h][k] += int(r[k]); });
      });
    });
    var hourlyData = Object.keys(hourMap).map(Number).sort(function (a, b) { return a - b; }).map(function (h) {
      var r = hourMap[h];
      r.auto_coverage_rate = safeDiv(r.A + r.B, r.total);
      r.auto_succ_rate = safeDiv(r.A, r.total);
      return r;
    });
    summary.hourly_today = { date: start + '~' + end, data: hourlyData };
    // 平台/航司/渠道
    function mergeNamed(keyName, label) {
      var mp = {};
      days.forEach(function (x) {
        (x[keyName] || []).forEach(function (row) {
          if (!row || !row[label]) return;
          var name = String(row[label]);
          if (!mp[name]) mp[name] = { total: 0, A: 0, B: 0, C: 0, D: 0, profit_sum: 0 };
          ['total', 'A', 'B', 'C', 'D'].forEach(function (k) { mp[name][k] += int(row[k]); });
          mp[name].profit_sum += float(row.profit_sum);
          if ('name' in row && !('name' in mp[name])) mp[name].name = row.name;
          if ('tier' in row && !('tier' in mp[name])) mp[name].tier = row.tier;
        });
      });
      return Object.keys(mp).map(function (name) {
        var agg = mp[name]; agg[label] = name;
        agg.auto_succ_rate = safeDiv(agg.A, agg.total);
        agg.auto_coverage_rate = safeDiv(agg.A + agg.B, agg.total);
        agg.avg_profit = agg.total ? parseFloat((agg.profit_sum / agg.total).toFixed(2)) : 0.0;
        agg.profit_sum = parseFloat(agg.profit_sum.toFixed(2));
        return agg;
      });
    }
    var platform = mergeNamed('platform', 'platform'), airline = mergeNamed('airline', 'airline'), channel = mergeNamed('channel', 'channel');
    airline.sort(function (a, b) { return b.total - a.total; });
    channel.sort(function (a, b) { return b.total - a.total; });
    // 小时×环节
    function mergeHourlyStage(key) {
      var hsMap = {};
      days.forEach(function (x) {
        (x[key] || []).forEach(function (r) {
          var h = int(r.hour);
          if (!hsMap[h]) hsMap[h] = { hour: h };
          STAGES8.forEach(function (s) { hsMap[h][s] = int(hsMap[h][s]) + int(r[s]); });
          hsMap[h].total = STAGES8.reduce(function (a, s) { return a + int(hsMap[h][s]); }, 0);
        });
      });
      return Object.keys(hsMap).map(Number).sort(function (a, b) { return a - b; }).map(function (h) { return hsMap[h]; });
    }
    // 失败原因
    function mergeReasons(key) {
      var mp = {};
      days.forEach(function (x) {
        (x[key] || []).forEach(function (r) {
          var k = String(r.reason || '') + '\u0000' + String(r.family || '');
          if (!mp[k]) mp[k] = { reason: k.split('\u0000')[0], family: k.split('\u0000')[1], count: 0,
            full: String(r.full || ''), near_reason: String(r.near_reason || '') };
          mp[k].count += int(r.count);
          if (!mp[k].near_reason && r.near_reason) mp[k].near_reason = String(r.near_reason);
        });
      });
      return Object.keys(mp).map(function (k) { return mp[k]; });
    }
    var staffNames = {};
    days.forEach(function (x) { (x.staff || []).forEach(function (r) { if (r && r.name) staffNames[r.name] = 1; }); });
    return {
      month: days[0].month, date: start + '~' + end, summary: summary,
      daily: [{ date: start + '~' + end, total: tot, A: A, B: B, C: C, D: D, total_segments: seg, auto_succ_rate: summary.auto_succ_rate }],
      platform: platform, airline: airline, channel: channel,
      staff: Object.keys(staffNames).map(function (nm) { return { name: nm }; }),
      hourly_stage: mergeHourlyStage('hourly_stage'), hourly_stage_B: mergeHourlyStage('hourly_stage_B'),
      fail_reasons_B: mergeReasons('fail_reasons_B'), fail_reasons_D: mergeReasons('fail_reasons_D')
    };
  }

  // ---------- 从 daily_detail 构造 ctx（复刻 main 里的 ctx 组装） ----------
  function makeCtx(opts) {
    // opts: { day, ym, date, isRange, target, generatedAt, periodWord }
    var day = opts.day, s = day.summary || {};
    var row = (day.daily || [{}])[0];
    ['total_orders', 'total_segments', 'A', 'B', 'C', 'D', 'auto_succ_rate'].forEach(function (k) {
      if (s[k] == null) s[k] = k === 'total_orders' ? (row.total || 0) : (row[k] || 0);
    });
    // v14: 全自动成功率分母统一为 A+B+C+D（全天单量），不依赖数据管道是否已重算。
    function rateABCD(o) {
      var a = int(o.A), b = int(o.B), c = int(o.C), d = int(o.D), den = a + b + c + d;
      o.auto_succ_rate = den ? safeDiv(a, den) : 0;
    }
    rateABCD(s);
    ['platform', 'airline', 'channel'].forEach(function (key) {
      (day[key] || []).forEach(rateABCD);
    });
    var hourly = ((s.hourly_today || {}).data || []).slice().sort(function (a, b) { return int(a.hour) - int(b.hour); });
    return {
      month: opts.ym, date: opts.date, summary: s,
      period_word: opts.isRange ? '区间内' : '当天',
      platform: day.platform || [], airline: day.airline || [], channel: day.channel || [],
      hourly: hourly, staff_n: (day.staff || []).length, target: opts.target,
      generated_at: opts.generatedAt || '',
      hourly_stage: day.hourly_stage || [], hourly_stage_B: day.hourly_stage_B || [],
      fail_b: day.fail_reasons_B || [], fail_d: day.fail_reasons_D || []
    };
  }

  var api = { buildHtml: buildHtml, makeCtx: makeCtx, mergeDays: mergeDays, weekdayCn: weekdayCn };
  root.ReportRender = api;
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
