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
# 注意：标题/info 仍然保留作为部署成功的快速信号，但通过 CSS 隐藏掉，
# 避免占据 iframe 上方的空间造成"白条"。
st.markdown(
    """
<style>
    /* 隐藏部署状态条，腾出空间给 dashboard iframe */
    [data-testid="stToolbar"] { display: none !important; }
    [data-testid="stDecoration"] { display: none !important; }
    [data-testid="stHeader"] { display: none !important; }
    [data-testid="stStatusWidget"] { visibility: hidden !important; }
    #MainMenu { visibility: hidden !important; }
    footer { visibility: hidden !important; }
    /* streamlit 右下角 "Manage app" 按钮 */
    .viewerBadge_link__qRIco,
    [class*="viewerBadge"] { display: none !important; }

    /* 关键：把 streamlit 外层背景改成和 dashboard 一样的 #0a0e1a，
       消除 iframe 周围的白边（白边的根本原因） */
    .stApp { background: #0a0e1a !important; }
    [data-testid="stAppViewContainer"] { background: #0a0e1a !important; }

    /* 干掉 main 区域的 padding 和 max-width 限制 */
    .main .block-container {
        padding: 0 !important;
        max-width: 100% !important;
        margin: 0 !important;
    }
    section.main { padding: 0 !important; }
    div[data-testid="stVerticalBlock"] { padding: 0 !important; gap: 0 !important; }

    /* iframe 撑满 + 去边框 */
    iframe {
        width: 100% !important;
        border: none !important;
        display: block !important;
        background: #0a0e1a !important;
    }
</style>
""",
    unsafe_allow_html=True,
)
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
# 保留 components.html()（iframe 模式）而不是 st.html()——原因：
# 1. st.html() 走 DOMPurify 剥 Alpine `x-data`/`x-show` 等属性，dashboard 会废
# 2. components.html() 通过上面的 CSS 注入已经把"白边"问题解决
import streamlit.components.v1 as components

components.html(html, height=5200, scrolling=True)
