"""auto_sync 监控模块

用 watchdog 监控目录，新 xlsx 文件出现后：
  1. 文件稳定性检查（大小/修改时间稳定才触发）
  2. 冷却时间（短时间内多次事件只触发一次）
  3. 文件去重（mtime + md5 避免重复处理）
  4. 触发 execute_trigger()

设计要点：
  - watchdog 在独立 Observer 线程跑
  - 触发处理在 ThreadPoolExecutor 跑（异步不阻塞 watchdog）
  - 全部状态写 status.db，可被外部查询
"""
import fnmatch
import hashlib
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, Future
from datetime import datetime, timezone, timedelta
from typing import Callable, Optional, Set

try:
    from watchdog.events import FileSystemEventHandler, FileSystemEvent
    from watchdog.observers import Observer
except ImportError:
    raise ImportError(
        "watchdog 未安装，请先：pip install watchdog"
    )

from .config import AutoSyncConfig, DEFAULT_CONFIG, resolve_paths
from .status import StatusStore
from .trigger import TriggerResult, execute_trigger

log = logging.getLogger("auto_sync.watcher")
BJ_TZ = timezone(timedelta(hours=8))


def _matches_any(name: str, patterns: list) -> bool:
    """检查文件名是否匹配任一 glob 模式"""
    return any(fnmatch.fnmatch(name, p) for p in patterns)


class XlsxEventHandler(FileSystemEventHandler):
    """watchdog 事件 handler：把事件丢给 Worker 处理"""

    def __init__(self, worker: "WatcherWorker"):
        super().__init__()
        self.worker = worker

    def on_created(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.worker.on_file_event(event.src_path, "created")

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return
        self.worker.on_file_event(event.src_path, "modified")

    def on_moved(self, event: FileSystemEvent):
        """处理 OTA 平台"先创建临时文件，再 rename 成正式文件"的情况"""
        if event.is_directory:
            return
        # 移动的目标路径才是正式文件
        dest = getattr(event, "dest_path", None) or event.src_path
        self.worker.on_file_event(dest, "moved")


class WatcherWorker:
    """实际干活的 worker（独立于 watchdog 线程）

    职责：
      1. 接收文件事件
      2. 稳定性检查（等文件大小稳定 + mtime 老化）
      3. 冷却时间控制
      4. 去重（mtime + md5）
      5. 触发 execute_trigger
      6. 写状态到 status.db
    """

    def __init__(
        self,
        config: AutoSyncConfig,
        script_dir: str,
        status_store: StatusStore,
        on_complete: Optional[Callable[[TriggerResult], None]] = None,
    ):
        self.config = config
        self.script_dir = script_dir
        self.status_store = status_store
        self.on_complete = on_complete  # 外部回调（Dora 工作台用它）

        # 已处理的文件（mtime + md5 去重）
        self._processed: Set[str] = set()
        self._processed_lock = threading.Lock()

        # 待处理队列（path -> 首次事件时间）
        self._pending: dict = {}
        self._pending_lock = threading.Lock()

        # 冷却时间（最后一次触发时间）
        self._last_trigger_time: float = 0.0
        self._last_trigger_lock = threading.Lock()

        # 后台处理线程
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="auto_sync_worker")
        self._stop_event = threading.Event()

        # watchdog observer
        self._observer: Optional[Observer] = None

        log.info(f"WatcherWorker init: watch_dir={config.watch_dir}, script_dir={script_dir}")

    # ========== 生命周期 ==========

    def start(self):
        """启动 watchdog observer + 后台处理"""
        if self._observer is not None:
            log.warning("WatcherWorker 已经启动，跳过")
            return

        if not os.path.isdir(self.config.watch_dir):
            raise FileNotFoundError(f"监控目录不存在: {self.config.watch_dir}")

        event_handler = XlsxEventHandler(self)
        self._observer = Observer()
        self._observer.schedule(event_handler, self.config.watch_dir, recursive=False)
        self._observer.start()

        # 更新状态：运行中
        self.status_store.update_status(
            is_running=True,
            started_at=datetime.now(BJ_TZ).isoformat(timespec="seconds"),
            watch_dir=self.config.watch_dir,
        )

        log.info(f"WatcherWorker 已启动，监控 {self.config.watch_dir}")

    def stop(self, timeout: float = 10.0):
        """停止"""
        self._stop_event.set()
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=timeout)
            self._observer = None
        self._executor.shutdown(wait=True, cancel_futures=True)
        self.status_store.update_status(is_running=False)
        log.info("WatcherWorker 已停止")

    # ========== 事件入口 ==========

    def on_file_event(self, file_path: str, event_type: str):
        """watchdog 事件回调（同步触发，不做耗时操作）"""
        # 过滤：只处理 xlsx 且不在 ignore 列表
        if not _matches_any(os.path.basename(file_path), self.config.file_patterns):
            return
        if _matches_any(os.path.basename(file_path), self.config.ignore_patterns):
            log.debug(f"忽略（匹配 ignore）: {file_path}")
            return

        log.debug(f"文件事件 [{event_type}]: {file_path}")
        with self._pending_lock:
            if file_path not in self._pending:
                # 第一次见到，加入 pending 队列
                self._pending[file_path] = {
                    "first_seen": time.time(),
                    "event_type": event_type,
                }
                # 后台线程会定期 scan pending 队列，做稳定性检查
                self._executor.submit(self._process_pending, file_path)

    def _process_pending(self, file_path: str):
        """后台线程：等文件稳定后再触发"""
        try:
            # 等 stability_check_seconds（让文件写完）
            time.sleep(self.config.stability_check_seconds)

            # 再次检查文件是否还存在（OTA 平台可能导出失败删了）
            if not os.path.exists(file_path):
                log.debug(f"文件已删除，跳过: {file_path}")
                self._remove_pending(file_path)
                return

            # 检查文件 mtime 是否太近（边写边读风险）
            mtime = os.path.getmtime(file_path)
            age = time.time() - mtime
            if age < self.config.min_file_age_seconds:
                # 文件还在被修改，再等一会
                log.debug(f"文件太新（age={age:.1f}s < {self.config.min_file_age_seconds}s），重排队: {file_path}")
                # 重新调度（不要无限循环，最多重试 3 次）
                with self._pending_lock:
                    info = self._pending.get(file_path, {})
                    retries = info.get("retries", 0)
                    if retries < 3:
                        self._pending[file_path]["retries"] = retries + 1
                        self._executor.submit(self._process_pending, file_path)
                    else:
                        log.warning(f"文件稳定超时（重试 3 次），放弃: {file_path}")
                        self._remove_pending(file_path)
                return

            # 冷却时间检查（避免短时间内多次触发）
            with self._last_trigger_lock:
                if time.time() - self._last_trigger_time < self.config.cooldown_seconds:
                    wait = self.config.cooldown_seconds - (time.time() - self._last_trigger_time)
                    log.info(f"冷却中（还需 {wait:.1f}s），延迟触发: {file_path}")
                    time.sleep(wait)

            # 去重：mtime + md5（避免同一文件被多次处理）
            file_size = os.path.getsize(file_path)
            file_md5 = self._compute_md5(file_path)
            dedup_key = f"{mtime}:{file_size}:{file_md5}"
            with self._processed_lock:
                if dedup_key in self._processed:
                    log.debug(f"已处理过（mtime+md5 一致），跳过: {file_path}")
                    self._remove_pending(file_path)
                    return

            # 触发！
            with self._last_trigger_lock:
                self._last_trigger_time = time.time()
            self._trigger(file_path)

            # 标记为已处理
            with self._processed_lock:
                self._processed.add(dedup_key)
                # 限制 _processed 大小，避免内存泄漏
                if len(self._processed) > 1000:
                    # 保留最近 500 个
                    self._processed = set(list(self._processed)[-500:])

            self._remove_pending(file_path)
        except Exception as e:
            log.exception(f"_process_pending 异常: {e}")
            self._remove_pending(file_path)

    def _remove_pending(self, file_path: str):
        with self._pending_lock:
            self._pending.pop(file_path, None)

    def _compute_md5(self, file_path: str) -> str:
        """算文件 md5（前 1MB 就够，避免大文件慢）"""
        h = hashlib.md5()
        with open(file_path, "rb") as f:
            h.update(f.read(1024 * 1024))
        return h.hexdigest()

    def _trigger(self, file_path: str):
        """真正触发：跑 gen + git push"""
        file_size = os.path.getsize(file_path)
        filename = os.path.basename(file_path)
        triggered_at = datetime.now(BJ_TZ).isoformat(timespec="seconds")
        commit_message = self.config.git_commit_message_template.format(
            filename=filename,
            trigger_time=triggered_at,
        )

        log.info(f"触发: {filename} ({file_size:,} bytes)")

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

        # 写历史记录
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

        # 更新当前状态
        self.status_store.update_status(
            last_trigger_at=triggered_at,
            last_file=filename,
            last_status="success" if result.success else "failed",
            last_duration=result.duration,
            increment_triggers=1,
            increment_successes=1 if result.success else 0,
            increment_failures=0 if result.success else 1,
        )

        if result.success:
            log.info(f"成功: {filename} 用时 {result.duration:.1f}s")
        else:
            log.error(f"失败: {filename} - {result.error}")

        # 外部回调（Dora 工作台用它做实时通知）
        if self.on_complete:
            try:
                self.on_complete(result)
            except Exception as e:
                log.warning(f"on_complete 回调异常: {e}")