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
from pathlib import Path  # cmd_daily_report --output 用

# 2026-08-05 修复: PowerShell 5.1 + 中文 Windows 默认 GBK 编码
# start_background() 起 daemon 线程，print emoji 会触发 UnicodeEncodeError
# 整个主进程退出 → 守护线程一起死 → auto_sync 假启动
# 修法: 启动时强制 stdout/stderr utf-8 + 后续 print 用 ASCII 替代 emoji
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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

    if args.foreground:
        # 前台阻塞（开发调试用）
        mgr = AutoSyncManager(config=config)
        mgr.start_blocking()
    else:
        # 2026-08-05 修复: 原来用 daemon 线程（mgr.start_background()），
        # 主进程退出 → 守护线程一起死 → auto_sync 假启动。
        # 改用 detached 子进程跑 foreground watchdog，父进程 print 后立即退出，
        # 子进程独立存活。
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(script_dir, "auto_sync", "data", "daemon.log")
        err_path = os.path.join(script_dir, "auto_sync", "data", "daemon.err.log")
        pid_path = os.path.join(script_dir, "auto_sync", "data", "daemon.pid")
        # 写 daemon.pid 让外部知道子进程 PID
        with open(pid_path, "w") as f:
            f.write("")  # 占位，下面子进程自己覆写

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS: 子进程独立 session，父进程退出不影响
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        log_fh = open(log_path, "a", encoding="utf-8")
        child = subprocess.Popen(
            [sys.executable, "-m", "auto_sync", "start", "--foreground"],
            cwd=script_dir,
            env=env,
            stdout=log_fh,
            stderr=log_fh,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
            close_fds=True,
        )
        with open(pid_path, "w") as f:
            f.write(str(child.pid))
        log_fh.close()

        print(f"[OK] auto_sync 已后台启动 (v{__version__})")
        print(f"     子进程 PID: {child.pid}")
        print(f"     监控目录: {config.watch_dir}")
        print(f"     状态库: {config.status_db_path}")
        print(f"     日志: {log_path}")
        print()
        print("     常用命令：")
        print("       python -m auto_sync status    # 看状态")
        print("       python -m auto_sync history   # 看历史")
        print("       python -m auto_sync trigger   # 手动触发一次")
        print("       taskkill /F /PID " + str(child.pid) + "  # 停止守护")
        print()
        print("     子进程独立 session，父进程退出后继续跑")


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
                encoding="utf-8", errors="replace",  # tasklist 输出 GBK
            )
            daemon_alive = (str(daemon_pid) in (r.stdout or ""))
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

    # v1.2（2026-08-31）：防重入守卫——已有存活 daemon 时直接退出，不再起第二个。
    # 背景：开机任务 + 手动启动可能叠加（双 daemon = 每个文件事件跑两次 gen）。
    pid_file = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "auto_sync", "data", "daemon.pid",
    )
    if os.path.exists(pid_file):
        try:
            with open(pid_file) as f:
                old_pid = int(f.read().strip())
            r = subprocess.run(
                ["tasklist", "/FI", f"PID eq {old_pid}", "/NH"],
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",  # tasklist 输出 GBK
            )
            if str(old_pid) in (r.stdout or ""):
                print(f"[OK] auto_sync daemon 已在运行 (PID {old_pid})，跳过本次启动")
                return 0
        except (ValueError, OSError):
            pass  # pid 文件损坏 → 视为未运行，正常启动

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

    # daily-report（生成日报/周报/月报并推送）
    p_report = subparsers.add_parser("daily-report", help="生成归因分析报告并推送（钉钉/飞书/控制台）")
    p_report.add_argument("--date", help="报告日期 YYYY-MM-DD（默认最近一天）")
    p_report.add_argument("--prev-date", help="环比日期 YYYY-MM-DD（默认自动取前一天）")
    p_report.add_argument("--period", default="daily", choices=["daily", "weekly", "monthly"], help="报告周期")
    p_report.add_argument("--channel", default="console", choices=["console", "dingtalk", "feishu"], help="推送通道")
    p_report.add_argument("--config", help="推送配置文件（YAML）")
    p_report.add_argument("--output", help="输出报告到指定文件（JSON）")
    p_report.set_defaults(func=cmd_daily_report)

    # fetch（2026-08-27 新增：API 拉 xlsx，替代手动下载）
    p_fetch = subparsers.add_parser("fetch", help="调 API 拉 xlsx 到 DATA_DIR（替代手动下载）")
    p_fetch.add_argument("--days", "-n", type=int, default=7, help="拉最近 N 天（默认 7, 含今天）")
    p_fetch.add_argument("--date", help="拉指定日期 YYYY-MM-DD（覆盖 --days）")
    p_fetch.add_argument("--force", action="store_true", help="覆盖已存在的 xlsx")
    p_fetch.add_argument("--trigger", action="store_true", help="拉完自动触发 gen+git+push")
    p_fetch.set_defaults(func=cmd_fetch)

    # ai-rules（2026-09-03 新增：AI 语义归因结果 → 建议采纳为规则，人工审批）
    p_airules = subparsers.add_parser("ai-rules", help="查看 AI 语义归因结果，产出可采纳为正则规则的建议")
    p_airules.add_argument("--limit", type=int, default=30, help="展示条数（默认 30）")
    p_airules.set_defaults(func=cmd_ai_rules)

    # ai-insight（2026-09-03 新增：AI 解读灰度审查预览）
    p_aiinsight = subparsers.add_parser("ai-insight", help="预览 AI 点评/处置描述（灰度审查用，不推送）")
    p_aiinsight.add_argument("--date", help="预览日期 YYYY-MM-DD（默认最新一天）")
    p_aiinsight.set_defaults(func=cmd_ai_insight)

    args = parser.parse_args()
    setup_logging(args.log_level)
    return args.func(args) or 0


def cmd_daily_report(args):
    """生成归因分析报告并推送"""
    from .notify import NotifyConfig, send, load_config_from_yaml
    from .daily_report import build_pushable_report, build_report, render_markdown

    # 1. 确定报告日期（默认最近一天）
    import json as _json
    data_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "dashboard_data.json",
    )
    with open(data_path, encoding="utf-8") as f:
        data = _json.load(f)
    daily_dates = sorted([d.get("date", "") for d in data.get("daily", []) if d.get("date")])
    # v9：日报基准 = 今天之前的最新完整日（今天的文件 8:30 只有早晨部分数据）
    from datetime import date as _date
    _today = _date.today().isoformat()
    complete = [d for d in daily_dates if d < _today]
    target_date = args.date or (complete[-1] if complete else (daily_dates[-1] if daily_dates else None))
    if not target_date:
        print("[X] dashboard_data.json 里没有 daily 数据")
        return 1

    # 2. 生成报告
    print(f">>> 生成报告: {target_date} ({args.period})")
    pushable = build_pushable_report(target_date, args.period, args.prev_date)

    # 3. 输出到文件（如果指定）
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # _raw 太大，只输出可推送部分
        save = {k: v for k, v in pushable.items() if k != "_raw"}
        save["_raw_summary"] = {
            "date": pushable["_raw"]["date"],
            "prev_date": pushable["_raw"].get("prev_date"),
            "generated_at": pushable["_raw"]["generated_at"],
            "sections_keys": list(pushable["_raw"]["sections"].keys()),
        }
        with open(out_path, "w", encoding="utf-8") as f:
            _json.dump(save, f, ensure_ascii=False, indent=2)
        print(f"   已输出: {out_path}")

    # 4. 推送
    if args.config:
        cfg = load_config_from_yaml(args.config)
        print(f"   加载配置: {args.config} → channel={cfg.channel}")
    else:
        cfg = NotifyConfig(channel=args.channel)
        print(f"   用默认配置: channel={cfg.channel}")

    # 强制覆盖 channel（命令行优先）
    cfg.channel = args.channel
    print(f">>> 推送 (channel={cfg.channel})")
    result = send(pushable, cfg)
    if result.success:
        print(f"[OK] 推送成功 (channel={result.channel}, {result.duration_ms}ms)")
    else:
        print(f"[X] 推送失败: {result.error}")
        return 1
    return 0


def _classify_failure(r) -> str:
    """分类失败类型, 用于决定是否告警.

    Returns:
        'no_access' - 业务码 NO_ACCESS (token 过期/无效)
        'http_5xx'  - 后端 5xx 错误
        'network'   - 网络/超时
        'unknown'   - 其他
    """
    if r.error_code == '-1' or r.error_msg == 'NO_ACCESS':
        return 'no_access'
    if 500 <= r.http_status < 600:
        return 'http_5xx'
    if r.error.startswith('网络失败') or r.error.startswith('HTTP '):
        return 'network'
    return 'unknown'


def _maybe_alert(results: list, fail_n: int, total: int):
    """严重失败时推钉钉告警（v2，2026-08-27）.

    告警规则:
    - 任何 no_access / http_5xx / network → 告警
    - 全部失败 → 告警（@所有人）
    - 单天未知失败 → 不告警（可能是今天数据还没生成）
    """
    # 1. 分类失败
    severe_failures = []  # (result, category)
    for r in results:
        if not r.success:
            cat = _classify_failure(r)
            if cat in ('no_access', 'http_5xx', 'network'):
                severe_failures.append((r, cat))

    if not severe_failures:
        return  # 严重失败 0 个 → 不告警

    # 2. 构造告警内容
    lines = []
    lines.append(f"**自动拉取失败告警** (失败 {len(severe_failures)}/{total})\n")
    for r, cat in severe_failures:
        cat_label = {'no_access': '🔑 Token 失效', 'http_5xx': '🌐 后端 5xx',
                     'network': '📡 网络异常'}[cat]
        lines.append(f"- {r.date} | {cat_label}")
        if r.error:
            lines.append(f"  - 错误: {r.error[:200]}")
        if r.trace_id:
            lines.append(f"  - traceId: `{r.trace_id}`")

    if any(cat == 'no_access' for _, cat in severe_failures):
        lines.append("\n**🔴 疑似 Token 过期**, 请:")
        lines.append("1. 浏览器登录 elephant 系统")
        lines.append("2. F12 → Network → 抓新 header")
        lines.append("3. 更新凭据文件: `E:\\Work\\Documents\\凭据\\elephant_api.yaml`")
        lines.append("4. 手动重跑: `python -m auto_sync fetch --days 1`")

    title = "🔴 auto-ticket 拉取失败"
    body = "\n".join(lines)

    # 3. 推钉钉
    print(f"\n[!] 严重失败, 推送告警到钉钉...")
    try:
        from .notify import NotifyConfig, send, load_config_from_yaml
        from . import notify as _notify

        # 优先用 elephant 专用的告警配置, 没有则用日报配置
        elephant_cfg = r'E:\Work\Documents\凭据\elephant_notify.yaml'
        if os.path.exists(elephant_cfg):
            cfg = load_config_from_yaml(elephant_cfg)
            print(f"  使用凭据: {elephant_cfg}")
        else:
            # 复用日报的钉钉配置
            daily_cfg = r'E:\Work\Documents\凭据\dingtalk_notify.yaml'
            if os.path.exists(daily_cfg):
                cfg = load_config_from_yaml(daily_cfg)
                cfg.channel = 'dingtalk'
                print(f"  使用日报凭据: {daily_cfg}")
            else:
                cfg = NotifyConfig(channel='console')
                print("  无钉钉凭据, 用 console 输出")

        # 告警推 dingtalk, 其他推 console
        cfg.channel = 'dingtalk' if cfg.dingtalk_webhook else 'console'
        # 严重 → @所有人
        if any(cat == 'no_access' for _, cat in severe_failures):
            cfg.at_all = True

        # 用 markdown 推 (action card 看起来更好, 但 markdown 兼容性更广)
        report = {
            "title": title,
            "markdown": body,
        }
        result = send(report, cfg)
        if result.success:
            print(f"[OK] 告警已推送 (channel={result.channel}, {result.duration_ms}ms)")
        else:
            print(f"[X] 告警推送失败: {result.error}")
    except Exception as e:
        print(f"[X] 告警推送异常: {type(e).__name__}: {e}")
        # 不影响 fetch 主流程, 继续往下走


def cmd_ai_insight(args):
    """灰度审查：预览某天的 AI 解读产出（不推送，不受 insight_enabled 开关影响）"""
    from .ai_insight import daily_comment, reason_note, insight_enabled
    from .daily_report import build_brief, _load_data, _load_dd_for_months, _recent_month_keys

    full = _load_data()
    daily_dates = sorted([d.get("date", "") for d in full.get("daily", []) if d.get("date")])
    date = args.date or daily_dates[-1] if daily_dates else None
    if not date:
        print("[X] 无可用数据日期")
        return 1
    print(f"预览日期: {date}（当前灰度开关 insight_enabled={insight_enabled()}）\n")
    b = build_brief(date)
    print(f"🤖 AI 点评: {b.get('ai_comment') or '（未生成/被闸门丢弃）'}")
    for it in b.get("attention", []):
        if it["kind"] == "new":
            print(f"📝 新根因处置 [{it['reason'][:40]}]: {it.get('ai_note') or '（未生成）'}")
    print(f"\n预览文件: E:\\Work\\Tools\\_workbench\\_ai_insight_preview.txt（含历史所有产出与丢弃记录）")
    return 0


def cmd_ai_rules(args):
    """AI 语义归因结果 → 建议采纳为 REASON_FAMILY_RULES 规则（人工审批后粘贴）"""
    from .ai_classifier import suggest_rules, _load_cache
    cache = _load_cache()
    if not cache:
        print("AI 归因缓存为空（尚未跑过 gen 的 AI 预 pass，或历史原因全部被规则命中）")
        return 0
    print(f"AI 归因缓存共 {len(cache)} 条，展示前 {args.limit} 条建议：\n")
    for s in suggest_rules(args.limit):
        print(f"  ◆ {s['ai_family']}")
        print(f"    原因: {s['reason'][:80]}")
        print(f"    建议规则: {s['suggested_rule']}")
    print("\n采纳方式：把'建议规则'行粘贴进 gen_dashboard_data.py 的 REASON_FAMILY_RULES 列表")
    print("（放在具体关键词规则区即可；采纳后该原因回到规则引擎，AI 缓存自动失效于下次全量归因）")
    return 0


def cmd_fetch(args):
    """调 API 拉 xlsx 到 DATA_DIR（v1，2026-08-27）"""
    from .elephant_api import fetch_day, fetch_recent

    # 1. 拉数据
    if args.date:
        # 拉指定日期
        results = [fetch_day(args.date, force=args.force)]
    else:
        # 拉最近 N 天
        results = fetch_recent(days=args.days, force=args.force)

    # 2. 汇总
    success_n = sum(1 for r in results if r.success and not r.skipped)
    skip_n = sum(1 for r in results if r.success and r.skipped)
    fail_n = sum(1 for r in results if not r.success)

    print(f"\n=== 拉取汇总 ===")
    print(f"  成功新拉: {success_n}")
    print(f"  已存在跳过: {skip_n}")
    print(f"  失败: {fail_n}")
    for r in results:
        if r.success and r.skipped:
            mark = "[SKIP]"
        elif r.success:
            mark = "[OK]"
        else:
            mark = "[FAIL]"
        size_str = f"{r.xlsx_size // 1024}KB" if r.xlsx_size else "-"
        dur = f"{r.duration_sec:.1f}s" if r.duration_sec else "-"
        print(f"  {mark} {r.date}  {size_str:8s}  {dur:5s}  {r.error or r.xlsx_path or ''}")

    # 3. 失败处理
    if fail_n > 0:
        print(f"\n[!] {fail_n} 天拉取失败, 详情:")
        for r in results:
            if not r.success:
                print(f"  {r.date}: {r.error}")
                if r.trace_id:
                    print(f"    traceId={r.trace_id} (给后端排查用)")
        # 全部失败（可能 token 过期） → 提示用户重新登录
        if fail_n == len(results):
            print("\n[!] 全部失败 → 可能是 token 过期, 请重新登录 elephant 系统并更新凭据文件:")
            print("    E:\\Work\\Documents\\凭据\\elephant_api.yaml")

    # 3.5 v2（2026-08-27）：严重失败 → 钉钉告警
    if fail_n > 0:
        _maybe_alert(results, fail_n, len(results))

    # 4. 触发 gen + git + push
    if args.trigger and success_n > 0:
        print(f"\n>>> 触发 gen + git + push ...")
        from .trigger import execute_trigger
        repo_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        gen_script = os.path.join(repo_dir, "gen_dashboard_data.py")
        # 用最近一次拉到的文件作 commit message
        latest = max((r for r in results if r.success and not r.skipped), key=lambda r: r.date, default=None)
        file_path = latest.xlsx_path if latest else "(no new file)"
        file_size = latest.xlsx_size if latest else 0
        commit_msg = f"data: API 自动拉取 {latest.date}.xlsx" if latest else "data: API auto fetch"
        result = execute_trigger(
            file_path=file_path,
            file_size=file_size,
            script_dir=repo_dir,
            gen_script=gen_script,
            git_remote="origin",
            git_branch="main",
            commit_message=commit_msg,
            push_enabled=True,
        )
        if result.success:
            print(f"[OK] 触发成功 ({result.duration:.1f}s)")
        else:
            print(f"[X] 触发失败: {result.error}")
            return 1

    return 0 if fail_n == 0 else 1


if __name__ == "__main__":
    sys.exit(main())