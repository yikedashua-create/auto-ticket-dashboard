"""
TicketOrderAnalyzer 集成示例

把这个文件内容粘到 TicketOrderAnalyzer/main.py 的合适位置，
或作为独立模块引用。

设计：
  - 在 streamlit 界面顶部加"自动同步"开关
  - 后台线程跑 auto_sync
  - 显示状态（运行中/已停止、上次触发、历史）
  - 提供"立即触发"按钮
"""
import streamlit as st
import pandas as pd
from auto_sync import AutoSyncManager, TriggerResult


@st.cache_resource
def get_auto_sync_manager():
    """Streamlit 缓存（避免重复创建 manager）"""
    return AutoSyncManager()


def render_auto_sync_panel():
    """在 streamlit 侧栏或主页渲染 auto_sync 控制面板"""
    st.sidebar.markdown("---")
    st.sidebar.subheader("🔄 自动同步（auto_sync）")

    mgr = get_auto_sync_manager()
    status = mgr.get_status()

    # 状态指示
    if mgr.is_running():
        st.sidebar.success("🟢 后台监控运行中")
    else:
        st.sidebar.warning("🔴 后台监控未启动")

    st.sidebar.caption(f"📁 监控: `{status.watch_dir or mgr.config.watch_dir}`")
    if status.last_trigger_at:
        icon = "✅" if status.last_status == "success" else "❌"
        st.sidebar.caption(f"{icon} 上次: {status.last_trigger_at} ({status.last_duration:.1f}s)")
    st.sidebar.caption(f"📊 累计: {status.total_successes}/{status.total_triggers} 成功")

    # 控制按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("▶️ 启动监控", disabled=mgr.is_running(), use_container_width=True):
            mgr.start_background()
            st.rerun()
    with col2:
        if st.button("⏹️ 停止", disabled=not mgr.is_running(), use_container_width=True):
            mgr.stop()
            st.rerun()

    # 手动触发
    if st.button("🚀 立即触发一次（处理最新 xlsx）", use_container_width=True):
        with st.spinner("跑 gen + git push 中..."):
            result = mgr.trigger_now()
        if result.success:
            st.success(f"✅ 成功！用时 {result.duration:.1f}s")
        else:
            st.error(f"❌ 失败：{result.error}")

    # 历史记录
    with st.expander("📜 历史记录", expanded=False):
        history = mgr.get_history(limit=20)
        if not history:
            st.info("(无历史)")
        else:
            df = pd.DataFrame([h.to_dict() for h in history])
            st.dataframe(df[["triggered_at", "file_path", "status", "duration", "file_size"]],
                         use_container_width=True)


# 在 main.py 的主函数最前面调用：
#   render_auto_sync_panel()
#
# 或者放在侧栏：放在你已有的 st.sidebar.xxx 后面