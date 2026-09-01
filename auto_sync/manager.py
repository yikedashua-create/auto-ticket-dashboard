r"""auto_sync 主管理器

外部使用方式：
  1. 后台守护进程（CLI: python -m auto_sync start）
  2. Python 模块导入（TicketOrderAnalyzer / Dora 工作台集成）

    from auto_sync import AutoSyncManager

    # 创建（默认配置）
    mgr = AutoSyncManager()

    # 自定义配置
    mgr = AutoSyncManager(
        watch_dir=r"D:\other\xlsx",
        cooldown_seconds=60.0,
    )

    # 后台启动（不阻塞）
    mgr.start_background()

    # 同步启动（阻塞，直到 stop）
    mgr.start_blocking()  # 通常用 signal handler 优雅退出

    # 立即触发一次（不依赖文件事件）
    result = mgr.trigger_now(file_path=r"D:\data\today.xlsx")

    # 查询状态
    status = mgr.get_status()
    history = mgr.get_history(limit=20)

    # 停止
    mgr.stop()
"""
import logging
import os
import signal
import subprocess
import sys
import threading
from typing import Callable, Optional

from .config import AutoSyncConfig, DEFAULT_CONFIG, resolve_paths
from .status import StatusStore, SyncStatus, TriggerHistory
from .trigger import TriggerResult, execute_trigger
from .watcher import WatcherWorker

log = logging.getLogger("auto_sync.manager")


class AutoSyncManager:
    """auto_sync 主管理器

    一个进程一个 manager 实例。
    支持后台线程 / 同步阻塞两种运行模式。
    """

    def __init__(
        self,
        watch_dir: Optional[str] = None,
        config: Optional[AutoSyncConfig] = None,
        on_complete: Optional[Callable[[TriggerResult], None]] = None,
        script_dir: Optional[str] = None,
    ):
        """Args:
            watch_dir:  监控目录（覆盖 config.watch_dir）
            config:     完整配置（覆盖默认值）
            on_complete: 每次触发完成后回调（Dora 工作台用它做通知）
            script_dir: 项目根目录（默认 = auto_sync 包所在目录的父目录）
        """
        # 配置
        self.config = config or AutoSyncConfig()
        if watch_dir:
            self.config.watch_dir = watch_dir

        # 解析路径
        if script_dir is None:
            # 默认 = auto_sync 包的父目录（即仓库根）
            script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.script_dir = script_dir
        self.config = resolve_paths(self.config, self.script_dir)

        # 状态存储
        self.status_store = StatusStore(self.config.status_db_path)

        # watcher worker
        self._worker: Optional[WatcherWorker] = None

        # 外部回调
        self._on_complete = on_complete

        # 后台线程
        self._bg_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # ========== daemon 互斥锁（v1.2，2026-08-31） ==========
    # 背景：daemon 可能被多种途径拉起（开机任务/手动/其它启动器），pid 文件
    # 只在走 cmd_daemon 时写入，检测不到旁路启动的实例。文件锁对所有
    # start_blocking 路径生效，保证任何时刻只有一个 daemon。
    # 持有者被强杀时锁会残留 → 用"pid 存活检查"判 stale 并自动接管。

    def _acquire_daemon_lock(self) -> bool:
        lock_path = os.path.join(self.script_dir, "auto_sync", "data", "daemon.lock")
        os.makedirs(os.path.dirname(lock_path), exist_ok=True)
        if os.path.exists(lock_path):
            try:
                with open(lock_path) as f:
                    old_pid = int(f.read().strip().split("|")[0])
                r = subprocess.run(
                    ["tasklist", "/FI", f"PID eq {old_pid}", "/NH"],
                    capture_output=True, text=True,
                    encoding="utf-8", errors="replace",  # tasklist 输出 GBK，防 UTF-8 环境解码崩
                )
                if str(old_pid) in (r.stdout or ""):
                    log.warning(f"daemon.lock 被 PID {old_pid} 持有且进程存活，拒绝启动")
                    return False
            except (ValueError, OSError):
                pass  # 文件损坏 → 视为 stale
            try:
                os.remove(lock_path)
            except OSError:
                pass
        try:
            with open(lock_path + ".tmp", "w") as f:
                f.write(f"{os.getpid()}")
            os.replace(lock_path + ".tmp", lock_path)
        except OSError as e:
            log.warning(f"写 daemon.lock 失败: {e}")
            return False
        return True

    def _release_daemon_lock(self):
        lock_path = os.path.join(self.script_dir, "auto_sync", "data", "daemon.lock")
        try:
            with open(lock_path) as f:
                owner = f.read().strip().split("|")[0]
            # Windows: 必须先关掉句柄再删，否则 PermissionError
            if owner == str(os.getpid()):
                os.remove(lock_path)
        except (OSError, ValueError):
            pass

    # ========== 生命周期 ==========

    def start_background(self):
        """后台线程跑（非阻塞）"""
        if self._worker is not None:
            log.warning("AutoSyncManager 已经在运行")
            return
        self._stop_event.clear()

        def _run():
            try:
                self._worker = WatcherWorker(
                    config=self.config,
                    script_dir=self.script_dir,
                    status_store=self.status_store,
                    on_complete=self._on_complete,
                )
                self._worker.start()
                # 阻塞直到 stop
                while not self._stop_event.is_set():
                    self._stop_event.wait(timeout=1.0)
                self._worker.stop()
            except Exception as e:
                log.exception(f"后台线程异常: {e}")
            finally:
                self._worker = None

        self._bg_thread = threading.Thread(target=_run, name="auto_sync_bg", daemon=True)
        self._bg_thread.start()
        log.info("AutoSyncManager 后台启动")

    def start_blocking(self):
        """同步阻塞跑（用 Ctrl+C 退出）"""
        if not self._acquire_daemon_lock():
            log.warning("已有 daemon 在运行（锁被持有），本次 start_blocking 直接退出")
            return
        try:
            self._worker = WatcherWorker(
                config=self.config,
                script_dir=self.script_dir,
                status_store=self.status_store,
                on_complete=self._on_complete,
            )
            self._worker.start()
            log.info("AutoSyncManager 阻塞模式启动，Ctrl+C 退出")

            # 注册 SIGINT / SIGTERM 优雅退出
            def _on_signal(signum, frame):
                log.info(f"收到信号 {signum}，准备退出...")
                self.stop()

            if sys.platform != "win32":
                signal.signal(signal.SIGTERM, _on_signal)
            signal.signal(signal.SIGINT, _on_signal)

            # 阻塞主线程（watchdog observer 在它自己的线程跑）
            self._stop_event.wait()
            self._worker.stop()
        except KeyboardInterrupt:
            log.info("用户中断")
            self.stop()

    def stop(self, timeout: float = 10.0):
        """停止"""
        self._stop_event.set()
        if self._bg_thread is not None:
            self._bg_thread.join(timeout=timeout)
            self._bg_thread = None
        if self._worker is not None:
            self._worker.stop(timeout=timeout)
        self._release_daemon_lock()
        log.info("AutoSyncManager 已停止")

    # ========== API：供外部调用 ==========

    def trigger_now(self, file_path: Optional[str] = None) -> TriggerResult:
        """立即触发一次（不依赖文件事件）

        Args:
            file_path: 要处理的文件路径（None 时用 watch_dir 下最新的 xlsx）

        Returns:
            TriggerResult
        """
        if file_path is None:
            file_path = self._find_latest_xlsx()
        if not file_path:
            return TriggerResult(
                success=False,
                file_path="(none)",
                file_size=0,
                started_at="",
                error="找不到要处理的文件",
            )
        if not os.path.exists(file_path):
            return TriggerResult(
                success=False,
                file_path=file_path,
                file_size=0,
                started_at="",
                error=f"文件不存在: {file_path}",
            )

        from datetime import datetime, timezone, timedelta
        bj = timezone(timedelta(hours=8))
        triggered_at = datetime.now(bj).isoformat(timespec="seconds")
        filename = os.path.basename(file_path)
        file_size = os.path.getsize(file_path)

        commit_message = self.config.git_commit_message_template.format(
            filename=filename, trigger_time=triggered_at
        )

        result = execute_trigger(
            file_path=file_path,
            file_size=file_size,
            script_dir=self.script_dir,
            gen_script=self.config.gen_script,
            git_remote=self.config.git_remote,
            git_branch=self.config.git_branch,
            commit_message=commit_message,
            push_enabled=self.config.push_enabled,
        )

        # 写历史 + 更新状态
        gen_output = ""
        for step in result.steps:
            if step.name.startswith("python"):
                gen_output = step.output
                break
        self.status_store.add_history(
            triggered_at=triggered_at,
            file_path=file_path,
            file_size=file_size,
            status="success" if result.success else "failed",
            duration=result.duration,
            error=result.error,
            gen_output=gen_output,
        )
        self.status_store.update_status(
            last_trigger_at=triggered_at,
            last_file=filename,
            last_status="success" if result.success else "failed",
            last_duration=result.duration,
            increment_triggers=1,
            increment_successes=1 if result.success else 0,
            increment_failures=0 if result.success else 1,
        )

        if self._on_complete:
            try:
                self._on_complete(result)
            except Exception as e:
                log.warning(f"on_complete 回调异常: {e}")

        return result

    def _find_latest_xlsx(self) -> Optional[str]:
        """找 watch_dir 下最新的 .xlsx 文件"""
        watch_dir = self.config.watch_dir
        if not os.path.isdir(watch_dir):
            return None
        candidates = []
        for fn in os.listdir(watch_dir):
            if fn.lower().endswith(".xlsx") and not fn.startswith("~"):
                fp = os.path.join(watch_dir, fn)
                if os.path.isfile(fp):
                    candidates.append((os.path.getmtime(fp), fp))
        if not candidates:
            return None
        candidates.sort(reverse=True)
        return candidates[0][1]

    # ========== API：状态查询 ==========

    def get_status(self) -> SyncStatus:
        """获取当前状态"""
        return self.status_store.get_status()

    def get_history(self, limit: int = 50) -> list:
        """获取历史触发记录"""
        return self.status_store.get_history(limit=limit)

    def is_running(self) -> bool:
        """是否在运行"""
        return self._worker is not None

    # ========== API：Dora 工作台集成 ==========

    def to_workbench_dict(self) -> dict:
        """序列化为 Dora 工作台友好的字典

        Dora 工作台可以这样调用：
            from auto_sync import AutoSyncManager
            mgr = AutoSyncManager()
            data = mgr.to_workbench_dict()
            return JSONResponse(data)
        """
        status = self.get_status()
        history = self.get_history(limit=20)
        return {
            "is_running": self.is_running(),
            "watch_dir": self.config.watch_dir,
            "status": status.to_dict(),
            "history": [h.to_dict() for h in history],
            "config": {
                "cooldown_seconds": self.config.cooldown_seconds,
                "stability_check_seconds": self.config.stability_check_seconds,
                "push_enabled": self.config.push_enabled,
            },
        }