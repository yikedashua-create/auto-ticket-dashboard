"""
auto_sync — 自动同步 xlsx 到 dashboard

功能：
  - 监控目录（watchdog 实现），新 xlsx 文件出现自动触发
  - 跑 gen_dashboard_data.py 生成 dashboard_data.json
  - git commit + push 到 GitHub → streamlit cloud 自动部署
  - 状态持久化（SQLite），让外部系统（TicketOrderAnalyzer / Dora 工作台）能查询

接入方式：
  1. 命令行：python -m auto_sync start   （后台守护进程）
  2. Python 模块：
        from auto_sync import AutoSyncManager
        mgr = AutoSyncManager()
        mgr.start_background()  # 后台线程
        mgr.trigger_now()       # 立即触发一次
        mgr.get_status()        # 查询状态
  3. HTTP API（Dora 工作台用）：
        from auto_sync import create_api
        app = create_api()  # FastAPI app，可挂载到 Dora 后端

设计原则：
  - 单一职责：监控、触发、状态分离
  - 模块化：所有外部依赖（gen_dashboard_data.py / git）都封装在 trigger.py
  - 状态可查：每次处理的结果都入库（status.db）
  - 失败可重试：网络/git 失败不丢任务
  - 幂等：同一文件多次触发不会重复跑（用 mtime + md5 去重）

作者：Mavis
版本：v1.0 (2026-07-08)
"""
from .manager import AutoSyncManager
from .status import SyncStatus, TriggerHistory
from .trigger import TriggerResult
from .config import AutoSyncConfig, DEFAULT_CONFIG

__version__ = "1.0.0"
__all__ = [
    "AutoSyncManager",
    "SyncStatus",
    "TriggerHistory",
    "TriggerResult",
    "AutoSyncConfig",
    "DEFAULT_CONFIG",
]