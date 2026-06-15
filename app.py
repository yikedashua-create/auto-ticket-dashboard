"""Streamlit 入口：把 dashboard_v5.html 原样嵌入，自动加载最新 dashboard_data.json

部署到 Streamlit Cloud：
  1. 把整个 dashboard 目录（dashboard_v5.html, dashboard_data.json, app.py, requirements.txt）
     push 到 GitHub repo
  2. Streamlit Cloud 选这个 repo + app.py 入口
  3. URL 类似 https://xxx.streamlit.app

本地测试：
  streamlit run app.py
"""
import json
import os
import streamlit as st

# ============== 1. 页面配置 ==============
st.set_page_config(
    page_title="自动出票数据看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============== 2. 加载数据 ==============
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_data.json")

if not os.path.exists(DATA_FILE):
    st.error(f"❌ 找不到数据文件：{DATA_FILE}")
    st.info("请先运行 `python gen_dashboard_data.py --month all` 生成数据")
    st.stop()

with open(DATA_FILE, "r", encoding="utf-8") as f:
    data_text = f.read()

# ============== 3. 加载 HTML 模板 ==============
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_v5.html")
if not os.path.exists(HTML_FILE):
    st.error(f"❌ 找不到 HTML 模板：{HTML_FILE}")
    st.stop()

with open(HTML_FILE, "r", encoding="utf-8") as f:
    html = f.read()

# ============== 4. 注入数据到 HTML（核心） ==============
# HTML 里的 loadData() 会优先读 window.__DASHBOARD_DATA__
# 用 JSON 序列化 + </script> 防御，避免 HTML 解析出错
safe_data = (
    data_text
    .replace("</script>", "<\\/script>")   # 防止 JSON 里的 </script> 提前闭合
    .replace("<!--", "<\\!--")              # 防止 HTML 注释闭合
)

# 在 <head> 末尾注入 window.__DASHBOARD_DATA__
injection = f"<script>window.__DASHBOARD_DATA__ = {safe_data};</script>"
if "</head>" in html:
    html = html.replace("</head>", injection + "</head>", 1)
else:
    # 兜底：插到 <body> 开头
    html = html.replace("<body>", "<body>" + injection, 1)

# ============== 5. 渲染（关键：st.components.v1.html 保真） ==============
# height 设大点让整个看板完整展示，scrolling=True 允许内部滚动
# iframe 隔离环境，Streamlit 不会动里面的 CSS——1:1 复刻本地效果
st.components.v1.html(html, height=4000, scrolling=True)

# ============== 6. 底部状态条（可选，方便排查） ==============
try:
    data = json.loads(data_text)
    months = data.get("available_months", [])
    total = data.get("summary", {}).get("total_orders", 0)
    current = data.get("current_month", "")
    st.caption(
        f"📅 数据月份：{current} · 可选：{months} · "
        f"📊 总单数：{total:,} · "
        f"🕐 看板刷新：{data.get('generated_at', 'N/A')}"
    )
except Exception:
    pass
