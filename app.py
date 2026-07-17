"""Streamlit 入口：把 dashboard_v5.html 嵌入，**数据由 HTML 自己去 jsDelivr fetch**

2026-07-17 修复：原来把 12.77MB dashboard_data.json 注入到 HTML 头，streamlit cloud
WebSocket 推 12.88MB srcdoc 时会 hang（实测 streamlit 1.58 / 1.59 都中招）。
新方案：streamlit 只渲染 107KB 的 HTML 骨架，浏览器自己从 jsDelivr CDN 拉数据
（自动 gzip + 国内节点）。
"""
import os
import streamlit as st

# ============== 1. 页面配置 ==============
st.set_page_config(
    page_title="自动出票数据看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ============== 2. 顶部状态条（让 streamlit 立刻有输出，验证部署成功） ==============
st.title("📊 自动出票数据看板")
st.info("💡 数据从 jsDelivr CDN 加载 · 首次加载约 5-10 秒（12.77MB gzipped ≈ 2-3MB）")

# ============== 3. 加载 HTML 模板 ==============
HTML_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_v5.html")
if not os.path.exists(HTML_FILE):
    st.error(f"❌ 找不到 HTML 模板：{HTML_FILE}")
    st.stop()

with open(HTML_FILE, "r", encoding="utf-8") as f:
    html = f.read()

# ============== 4. 渲染：streamlit 只发 107KB HTML，**不注入 12.77MB 数据** ==============
import streamlit.components.v1 as components

components.html(html, height=5000, scrolling=True)
