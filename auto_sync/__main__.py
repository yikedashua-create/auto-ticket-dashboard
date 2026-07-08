"""auto_sync 命令行入口

用法：
  python -m auto_sync start                # 后台启动 watchdog（推荐）
  python -m auto_sync start --foreground   # 前台阻塞启动（Ctrl+C 退出）
  python -m auto_sync trigger              # 立即触发一次（处理最新 xlsx）
  python -m auto_sync trigger --file PATH  # 立即触发指定文件
  python -m auto_sync status               # 查看当前状态
  python -m auto_sync history              # 查看历史触发记录
  python -m auto_sync stop                 # 停止后台进程（如果是另一个进程，需要用服务管理器）
  python -m auto_sync reset                # 清空状态（调试用）
"""
import argparse
import json
import logging
import os
import subprocess
import sys

from . import __version__
from .config import AutoSyncConfig, DEFAULT_CONFIG
from .manager import AutoSyncManager


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_start(args):
    """启动后台监控"""
    config_overrides = {}
    if args.watch_dir:
        config_overrides["watch_dir"] = args.watch_dir
    if args.cooldown is not None:
        config_overrides["cooldown_seconds"] = args.cooldown
    if args.no_push:
        config_overrides["push_enabled"] = False

    config = DEFAULT_CONFIG
    for k, v in config_overrides.items():
        setattr(config, k, v)

    mgr = AutoSyncManager(config=config)

    if args.foreground:
        # 前台阻塞（开发调试用）
        mgr.start_blocking()
    else:
        # 后台线程（daemon=True，进程退出时自动停止）
        mgr.start_background()
        print(f"✅ auto_sync 已后台启动 (v{__version__})")
        print(f"   监控目录: {config.watch_dir}")
        print(f"   状态库: {config.status_db_path}")
        print()
        print("   常用命令：")
        print("     python -m auto_sync status    # 看状态")
        print("     python -m auto_sync history   # 看历史")
        print("     python -m auto_sync trigger   # 手动触发一次")
        print()
        print("   进程退出时自动停止（daemon 线程）")
        print("   如需常驻，建议用 Windows Task Scheduler / NSSM 注册服务")


def cmd_trigger(args):
    """立即触发一次"""
    config_overrides = {}
    if args.watch_dir:
        config_overrides["watch_dir"] = args.watch_dir
    if args.no_push:
        config_overrides["push_enabled"] = False

    config = DEFAULT_CONFIG
    for k, v in config_overrides.items():
        setattr(config, k, v)

    mgr = AutoSyncManager(config=config)
    result = mgr.trigger_now(file_path=args.file)

    print(f"\n{'='*60}")
    print(f"触发: {result.file_path}")
    print(f"结果: {'✅ 成功' if result.success else '❌ 失败'}")
    print(f"用时: {result.duration:.1f}s")
    if result.error:
        print(f"错误: {result.error}")
    print(f"{'='*60}")
    print("\n步骤详情：")
    for step in result.steps:
        icon = "✓" if step.success else "✗"
        print(f"  {icon} {step.name} ({step.duration:.1f}s)")
        if step.error:
            print(f"    错误: {step.error[:200]}")
    return 0 if result.success else 1


def cmd_status(args):
    """查看状态"""
    config_overrides = {}
    if args.watch_dir:
        config_overrides["watch_dir"] = args.watch_dir
    config = DEFAULT_CONFIG
    for k, v in config_overrides.items():
        setattr(config, k, v)

    mgr = AutoSyncManager(config=config)
    status = mgr.get_status()

    # 检查 daemon 进程是否存在（通过 PID 文件）
    daemon_pid = None
    daemon_alive = False
    pid_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "auto_sync", "data", "daemon.pid",
    )
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                daemon_pid = int(f.read().strip())
            # Windows: 用 tasklist 检查
            import subprocess
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {daemon_pid}", "/NH"],
                capture_output=True, text=True,
            )
            daemon_alive = (str(daemon_pid) in r.stdout)
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"auto_sync 状态 (v{__version__})")
    print(f"{'='*60}")
    if daemon_alive:
        print(f"daemon 状态:     🟢 运行中 (PID {daemon_pid})")
    elif daemon_pid:
        print(f"daemon 状态:     🔴 PID {daemon_pid} 不存在（僵尸）")
    else:
        print(f"daemon 状态:     🔴 未启动（用 start_auto_sync.bat 启动）")
    print(f"持久化状态:      {'🟢 运行中' if status.is_running else '🔴 已停止'}")
    print(f"监控目录:        {status.watch_dir or mgr.config.watch_dir}")
    print(f"启动时间:        {status.started_at or '(未启动)'}")
    print(f"上次触发:        {status.last_trigger_at or '(从未触发)'}")
    print(f"上次文件:        {status.last_file or '-'}")
    print(f"上次结果:        {status.last_status or '-'}")
    print(f"上次用时:        {f'{status.last_duration:.1f}s' if status.last_duration else '-'}")
    print()
    print(f"累计触发: {status.total_triggers} 次  "
          f"✅ 成功: {status.total_successes}  "
          f"❌ 失败: {status.total_failures}")
    return 0


def cmd_history(args):
    """查看历史"""
    config_overrides = {}
    if args.watch_dir:
        config_overrides["watch_dir"] = args.watch_dir
    config = DEFAULT_CONFIG
    for k, v in config_overrides.items():
        setattr(config, k, v)

    mgr = AutoSyncManager(config=config)
    history = mgr.get_history(limit=args.limit)

    print(f"\n{'='*60}")
    print(f"最近 {len(history)} 次触发记录")
    print(f"{'='*60}")
    if not history:
        print("(无历史记录)")
        return 0

    print(f"{'时间':<20} {'文件':<30} {'状态':<8} {'用时':<8} {'大小':<10}")
    print("-" * 80)
    for h in history:
        icon = "✅" if h.status == "success" else "❌"
        size_kb = f"{h.file_size/1024:.1f}KB"
        print(f"{h.triggered_at:<20} {h.file_path[-30:]:<30} {icon} {h.status:<6} {h.duration:>5.1f}s  {size_kb}")
        if h.error:
            print(f"  ⚠️  {h.error[:120]}")
    return 0


def cmd_reset(args):
    """清空状态（调试用）"""
    config_overrides = {}
    if args.watch_dir:
        config_overrides["watch_dir"] = args.watch_dir
    config = DEFAULT_CONFIG
    for k, v in config_overrides.items():
        setattr(config, k, v)

    mgr = AutoSyncManager(config=config)
    mgr.status_store.reset()
    print("✅ 状态已清空")
    return 0


def cmd_daemon(args):
    """启动真正独立的守护进程（脱离父进程，父进程退出后子进程继续运行）

    Windows 下用 subprocess.Popen + DETACHED_PROCESS 标志，
    让子进程脱离父进程的 job object（bat 关掉不影响子进程）。
    """
    import subprocess
    import sys
    if sys.platform != "win32":
        # Linux/Mac 用 nohup 即可
        return _start_daemon_unix(args)

    # Windows：用 CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS 启动独立进程
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    flags = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP

    # 启动新 Python 进程，跑 --foreground 模式（内部用 watchdog observer 阻塞）
    cmd = [
        sys.executable,
        "-m", "auto_sync", "start", "--foreground",
    ]
    if args.no_push:
        cmd.append("--no-push")
    if args.watch_dir:
        cmd += ["--watch-dir", args.watch_dir]

    # 写 PID 文件，方便 stop 时 kill
    pid_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "auto_sync", "data", "daemon.pid",
    )
    os.makedirs(os.path.dirname(pid_file), exist_ok=True)

    # 用 pythonw.exe 启动（无窗口，纯后台）
    pythonw = sys.executable.replace("python.exe", "pythonw.exe")
    if not os.path.exists(pythonw):
        pythonw = sys.executable  # fallback

    proc = subprocess.Popen(
        [pythonw] + cmd[1:],
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )

    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    print(f"✅ auto_sync 已后台启动 (PID {proc.pid})")
    print(f"   PID 文件: {pid_file}")
    print(f"   状态查询: python -m auto_sync status")
    print(f"   停止服务: stop_auto_sync.bat 或 python -m auto_sync stop")
    return 0


def _start_daemon_unix(args):
    """Linux/Mac 的 daemon 启动（nohup）"""
    import subprocess
    log_file = "auto_sync/data/daemon.log"
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    cmd = f"nohup {sys.executable} -m auto_sync start --foreground"
    if args.no_push:
        cmd += " --no-push"
    cmd += f" > {log_file} 2>&1 &"
    subprocess.Popen(cmd, shell=True, start_new_session=True)
    print(f"✅ auto_sync 已后台启动（日志: {log_file}）")
    return 0


def cmd_stop(args):
    """停止后台守护进程"""
    pid_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "auto_sync", "data", "daemon.pid",
    )
    if not os.path.exists(pid_file):
        print("❌ 没找到 PID 文件，daemon 可能没启动")
        return 1

    with open(pid_file) as f:
        pid = int(f.read().strip())

    print(f"找到 PID {pid}，尝试停止...")

    if sys.platform == "win32":
        # Windows: taskkill /T 杀进程树（包括子进程）
        result = subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"✅ 已停止 (PID {pid})")
            os.remove(pid_file)
            # 更新状态
            try:
                config_overrides = {}
                if args.watch_dir:
                    config_overrides["watch_dir"] = args.watch_dir
                config = DEFAULT_CONFIG
                for k, v in config_overrides.items():
                    setattr(config, k, v)
                mgr = AutoSyncManager(config=config)
                mgr.status_store.update_status(is_running=False)
            except Exception:
                pass
            return 0
        else:
            print(f"❌ 停止失败: {result.stderr}")
            return 1
    else:
        import signal
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"✅ 已发送 SIGTERM 到 PID {pid}")
            os.remove(pid_file)
            return 0
        except ProcessLookupError:
            print(f"⚠️  PID {pid} 不存在（清理 PID 文件）")
            os.remove(pid_file)
            return 0


def cmd_serve(args):
    """暴露 HTTP API（供 Dora 工作台调用）"""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.responses import JSONResponse
        import uvicorn
    except ImportError:
        print("❌ 需要安装 fastapi + uvicorn: pip install fastapi uvicorn")
        return 1

    app = FastAPI(title="auto_sync API", version=__version__)
    mgr = AutoSyncManager()
    if not mgr.is_running():
        mgr.start_background()

    @app.get("/status")
    def api_status():
        return mgr.to_workbench_dict()

    @app.post("/trigger")
    def api_trigger(file_path: str = None):
        result = mgr.trigger_now(file_path=file_path)
        return result.to_dict()

    @app.get("/history")
    def api_history(limit: int = 20):
        return [h.to_dict() for h in mgr.get_history(limit=limit)]

    @app.post("/stop")
    def api_stop():
        mgr.stop()
        return {"stopped": True}

    print(f"✅ auto_sync API 已启动: http://{args.host}:{args.port}")
    print(f"   GET  /status     - 当前状态")
    print(f"   POST /trigger    - 手动触发（可指定 file_path）")
    print(f"   GET  /history    - 历史记录")
    print(f"   POST /stop       - 停止后台监控")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


def main():
    parser = argparse.ArgumentParser(
        prog="auto_sync",
        description=f"auto_sync v{__version__} — 自动监控 xlsx 目录并同步到 dashboard",
    )
    parser.add_argument("--watch-dir", help="覆盖默认监控目录")
    parser.add_argument("--cooldown", type=float, help="覆盖默认冷却时间（秒）")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])

    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(p):
        """给子命令加通用参数"""
        p.add_argument("--no-push", action="store_true", help="只 commit 不 push")
        p.add_argument("--watch-dir", help="覆盖默认监控目录（也可放主命令）")

    # start
    p_start = subparsers.add_parser("start", help="启动后台监控")
    p_start.add_argument("--foreground", "-f", action="store_true", help="前台阻塞模式（Ctrl+C 退出）")
    add_common(p_start)
    p_start.set_defaults(func=cmd_start)

    # trigger
    p_trigger = subparsers.add_parser("trigger", help="立即触发一次")
    p_trigger.add_argument("--file", help="指定要处理的文件路径")
    add_common(p_trigger)
    p_trigger.set_defaults(func=cmd_trigger)

    # status
    p_status = subparsers.add_parser("status", help="查看当前状态")
    add_common(p_status)
    p_status.set_defaults(func=cmd_status)

    # history
    p_history = subparsers.add_parser("history", help="查看历史触发记录")
    p_history.add_argument("--limit", "-n", type=int, default=20, help="显示条数（默认 20）")
    add_common(p_history)
    p_history.set_defaults(func=cmd_history)

    # reset
    p_reset = subparsers.add_parser("reset", help="清空状态（调试用）")
    add_common(p_reset)
    p_reset.set_defaults(func=cmd_reset)

    # serve（HTTP API）
    p_serve = subparsers.add_parser("serve", help="启动 HTTP API（供 Dora 工作台调用）")
    p_serve.add_argument("--host", default="127.0.0.1", help="监听地址")
    p_serve.add_argument("--port", type=int, default=8765, help="监听端口")
    p_serve.set_defaults(func=cmd_serve)

    # daemon（后台守护进程，脱离父进程）
    p_daemon = subparsers.add_parser("daemon", help="启动独立守护进程（关掉 cmd 窗口不影响）")
    add_common(p_daemon)
    p_daemon.set_defaults(func=cmd_daemon)

    # stop（停止守护进程）
    p_stop = subparsers.add_parser("stop", help="停止后台守护进程")
    add_common(p_stop)
    p_stop.set_defaults(func=cmd_stop)

    args = parser.parse_args()
    setup_logging(args.log_level)
    return args.func(args) or 0


if __name__ == "__main__":
    sys.exit(main())