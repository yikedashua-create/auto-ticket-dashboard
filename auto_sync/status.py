"""auto_sync 状态持久化模块

SQLite 表设计：
  - sync_status：单行，记录当前监控状态（运行中/已停止 + 上次触发时间 + 上次结果）
  - trigger_history：每次触发的记录（成功/失败 + 时长 + 文件）

为什么用 SQLite：
  - 零依赖（Python 自带）
  - 单文件，可直接放在项目目录
  - 读写快（千行/秒）
  - 适合"几十个触发/天"这个量级
"""
import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, asdict
from typing import Optional, List


@dataclass
class SyncStatus:
    """当前监控状态（单行记录）"""
    is_running: bool = False
    started_at: Optional[str] = None  # ISO 时间
    watch_dir: str = ""
    last_trigger_at: Optional[str] = None
    last_file: Optional[str] = None
    last_status: Optional[str] = None  # success / failed / skipped
    last_duration: Optional[float] = None
    total_triggers: int = 0
    total_successes: int = 0
    total_failures: int = 0

    def to_dict(self):
        return asdict(self)


@dataclass
class TriggerHistory:
    """单次触发记录"""
    id: int
    triggered_at: str
    file_path: str
    file_size: int
    status: str  # success / failed / skipped
    duration: float
    error: Optional[str] = None
    gen_output: Optional[str] = None  # gen_dashboard_data.py 的输出（前 500 字）

    def to_dict(self):
        return asdict(self)


class StatusStore:
    """SQLite 状态存储（线程安全）"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._init_db()

    @contextmanager
    def _conn(self):
        """线程安全的连接（每个请求一个新连接）"""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """初始化表结构"""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sync_status (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    is_running INTEGER NOT NULL DEFAULT 0,
                    started_at TEXT,
                    watch_dir TEXT NOT NULL DEFAULT '',
                    last_trigger_at TEXT,
                    last_file TEXT,
                    last_status TEXT,
                    last_duration REAL,
                    total_triggers INTEGER NOT NULL DEFAULT 0,
                    total_successes INTEGER NOT NULL DEFAULT 0,
                    total_failures INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS trigger_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    triggered_at TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    duration REAL NOT NULL,
                    error TEXT,
                    gen_output TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_history_at ON trigger_history(triggered_at DESC);

                -- 初始化 sync_status 单行
                INSERT OR IGNORE INTO sync_status (id, watch_dir) VALUES (1, '');
            """)

    # ========== sync_status 操作 ==========

    def update_status(
        self,
        is_running: Optional[bool] = None,
        started_at: Optional[str] = None,
        watch_dir: Optional[str] = None,
        last_trigger_at: Optional[str] = None,
        last_file: Optional[str] = None,
        last_status: Optional[str] = None,
        last_duration: Optional[float] = None,
        increment_triggers: int = 0,
        increment_successes: int = 0,
        increment_failures: int = 0,
    ) -> SyncStatus:
        """原子更新 sync_status（只更新非 None 字段）"""
        sets = []
        params = []
        if is_running is not None:
            sets.append("is_running = ?")
            params.append(int(is_running))
        if started_at is not None:
            sets.append("started_at = ?")
            params.append(started_at)
        if watch_dir is not None:
            sets.append("watch_dir = ?")
            params.append(watch_dir)
        if last_trigger_at is not None:
            sets.append("last_trigger_at = ?")
            params.append(last_trigger_at)
        if last_file is not None:
            sets.append("last_file = ?")
            params.append(last_file)
        if last_status is not None:
            sets.append("last_status = ?")
            params.append(last_status)
        if last_duration is not None:
            sets.append("last_duration = ?")
            params.append(last_duration)
        if increment_triggers:
            sets.append("total_triggers = total_triggers + ?")
            params.append(increment_triggers)
        if increment_successes:
            sets.append("total_successes = total_successes + ?")
            params.append(increment_successes)
        if increment_failures:
            sets.append("total_failures = total_failures + ?")
            params.append(increment_failures)
        sets.append("updated_at = CURRENT_TIMESTAMP")

        with self._lock, self._conn() as conn:
            conn.execute(f"UPDATE sync_status SET {', '.join(sets)} WHERE id = 1", params)
            row = conn.execute("SELECT * FROM sync_status WHERE id = 1").fetchone()
            return SyncStatus(
                is_running=bool(row["is_running"]),
                started_at=row["started_at"],
                watch_dir=row["watch_dir"],
                last_trigger_at=row["last_trigger_at"],
                last_file=row["last_file"],
                last_status=row["last_status"],
                last_duration=row["last_duration"],
                total_triggers=row["total_triggers"],
                total_successes=row["total_successes"],
                total_failures=row["total_failures"],
            )

    def get_status(self) -> SyncStatus:
        """获取当前状态"""
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM sync_status WHERE id = 1").fetchone()
            return SyncStatus(
                is_running=bool(row["is_running"]),
                started_at=row["started_at"],
                watch_dir=row["watch_dir"],
                last_trigger_at=row["last_trigger_at"],
                last_file=row["last_file"],
                last_status=row["last_status"],
                last_duration=row["last_duration"],
                total_triggers=row["total_triggers"],
                total_successes=row["total_successes"],
                total_failures=row["total_failures"],
            )

    # ========== trigger_history 操作 ==========

    def add_history(
        self,
        triggered_at: str,
        file_path: str,
        file_size: int,
        status: str,
        duration: float,
        error: Optional[str] = None,
        gen_output: Optional[str] = None,
    ) -> int:
        """记录一次触发"""
        with self._lock, self._conn() as conn:
            cursor = conn.execute(
                """INSERT INTO trigger_history
                   (triggered_at, file_path, file_size, status, duration, error, gen_output)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (triggered_at, file_path, file_size, status, duration, error,
                 (gen_output[:500] if gen_output else None)),
            )
            return cursor.lastrowid

    def get_history(self, limit: int = 50) -> List[TriggerHistory]:
        """获取最近 N 条触发记录"""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM trigger_history ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [
                TriggerHistory(
                    id=row["id"],
                    triggered_at=row["triggered_at"],
                    file_path=row["file_path"],
                    file_size=row["file_size"],
                    status=row["status"],
                    duration=row["duration"],
                    error=row["error"],
                    gen_output=row["gen_output"],
                )
                for row in rows
            ]

    def cleanup_history(self, max_rows: int):
        """清理超出 max_rows 的旧记录"""
        with self._lock, self._conn() as conn:
            conn.execute("""
                DELETE FROM trigger_history
                WHERE id NOT IN (
                    SELECT id FROM trigger_history ORDER BY id DESC LIMIT ?
                )
            """, (max_rows,))

    # ========== 调试用 ==========

    def reset(self):
        """清空所有状态（调试用）"""
        with self._lock, self._conn() as conn:
            conn.executescript("""
                DELETE FROM trigger_history;
                DELETE FROM sync_status;
                INSERT INTO sync_status (id, watch_dir) VALUES (1, '');
            """)