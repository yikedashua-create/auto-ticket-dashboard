# silent_task.pyw — 计划任务无窗口入口
# 用法（schtasks /TR）：
#   "D:\pycharm3\.venv\Scripts\pythonw.exe" "D:\自动出票数据分析项目\silent_task.pyw" fetch --yesterday
#   "D:\pycharm3\.venv\Scripts\pythonw.exe" "D:\自动出票数据分析项目\silent_task.pyw" fetch --days 2 --trigger
# 原理：pythonw 本身无控制台；把 stdout/stderr 引到日志文件，
# 避免 auto_sync 内部 print 在无控制台环境下抛错。
#
# v2（2026-11-02）：输出从 devnull 改为落盘日志 auto_sync/data/task_*.log
#   背景：17:10 eod 任务（fetch --today --trigger）连续 3/4 天 gen 中途静默死亡
#   （11-02 17:10 实测：fetch/parquet/AI归因全部完成，聚合段进程消失，gen.lock 残留，
#    计划任务 lastResult=1），但所有报错输出被 devnull 吞掉，完全无法取证。
#   v2 把每次计划任务运行的完整输出（含 gen 报错 traceback）追加到
#   auto_sync/data/task_<命令>.log，并记录开始/退出码。异常也兜底打印。
import os
import sys
import datetime

_base = os.path.dirname(os.path.abspath(__file__))
os.chdir(_base)
sys.path.insert(0, _base)

_log_dir = os.path.join(_base, "auto_sync", "data")
os.makedirs(_log_dir, exist_ok=True)
_cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
_log_name = "task_{}.log".format(_cmd)
_log_path = os.path.join(_log_dir, _log_name)

sys.stdout = open(_log_path, "a", buffering=1, encoding="utf-8", errors="replace")
sys.stderr = sys.stdout

print(f"\n===== {datetime.datetime.now():%Y-%m-%d %H:%M:%S} pid={os.getpid()} args={sys.argv[1:]} =====", flush=True)

sys.argv = ["auto_sync"] + sys.argv[1:]

from auto_sync.__main__ import main

try:
    _rc = main()
except Exception:
    import traceback
    traceback.print_exc()
    print("===== exit 1 (unhandled exception) =====", flush=True)
    sys.exit(1)

print(f"===== exit {_rc} =====", flush=True)
sys.exit(_rc or 0)
