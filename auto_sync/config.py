"""auto_sync 配置模块"""
import os
from dataclasses import dataclass, field
from typing import List


@dataclass
class AutoSyncConfig:
    """auto_sync 全部配置项

    默认值适合 auto-ticket-dashboard 项目，
    其他项目接入时可通过覆盖字段或传 dict 给 AutoSyncManager。
    """

    # ===== 监控目录 =====
    # 2026-07-23 修正：项目从 C 盘迁到 E 盘后，桌面快捷方式已失效，
    # 直接监控 E 盘真实数据目录（同时桌面仍保留一个快捷方式方便双击打开）。
    watch_dir: str = r"E:\Work\Data\订单\出票总订单数据"
    """要监控的 xlsx 所在目录"""

    # ===== 文件过滤 =====
    file_patterns: List[str] = field(default_factory=lambda: ["*.xlsx"])
    """只处理匹配这些 glob 的文件（支持多个）"""
    ignore_patterns: List[str] = field(default_factory=lambda: [
        "~*",         # Excel 临时文件（~开头）
        "*.tmp",      # 通用临时文件
        "~$*",        # Office 锁文件
    ])
    """忽略这些 glob 模式的文件"""

    # ===== 触发条件 =====
    stability_check_seconds: float = 3.0
    """文件大小稳定多少秒后才认为写完了（OTA 导出 xlsx 时这个数要够）"""
    min_file_age_seconds: float = 2.0
    """文件最后修改时间最少这么久了才触发（避免边写边读）"""
    cooldown_seconds: float = 30.0
    """两次触发的最小间隔（秒），防止短时间内多次触发"""

    # ===== 处理命令 =====
    gen_script: str = "gen_dashboard_data.py"
    """相对 SCRIPT_DIR 的 gen 脚本"""
    git_remote: str = "origin"
    git_branch: str = "main"
    git_commit_message_template: str = "data: 自动同步 {filename} ({trigger_time})"
    """commit message 模板，支持 {filename} / {trigger_time} 占位"""
    push_enabled: bool = True
    """是否 git push（false 时只 commit 不 push，调试用）"""

    # ===== 状态持久化 =====
    status_db_path: str = "auto_sync/data/status.db"
    """SQLite 数据库路径（相对 SCRIPT_DIR）"""
    history_max_rows: int = 1000
    """历史记录最大保留行数（超出自动清理）"""

    # ===== 错误处理 =====
    max_retries: int = 3
    """单次触发失败重试次数"""
    retry_delay_seconds: float = 10.0
    """重试间隔"""

    # ===== 调试 =====
    log_level: str = "INFO"  # DEBUG / INFO / WARNING / ERROR

    # ===== 自动接入工作台 =====
    workbench_integration: dict = field(default_factory=lambda: {
        # 预留：未来 Dora 工作台接入
        # "dora_skill_id": "auto_sync_xlsx",
        # "dora_api_url": "http://localhost:8765/skills/auto_sync_xlsx",
    })
    """工作台接入配置（预留字段，未来 Dora 接入时填）"""


# 默认配置实例（推荐用这个）
DEFAULT_CONFIG = AutoSyncConfig()


def resolve_paths(config: AutoSyncConfig, script_dir: str) -> AutoSyncConfig:
    """把相对路径转绝对路径（基于 script_dir）

    在 AutoSyncManager 初始化时调用，确保所有路径都是绝对路径。
    """
    config.gen_script = os.path.join(script_dir, config.gen_script)
    if not os.path.isabs(config.status_db_path):
        config.status_db_path = os.path.join(script_dir, config.status_db_path)
    return config