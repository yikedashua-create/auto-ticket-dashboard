# silent_task.pyw — 计划任务无窗口入口
# 用法（schtasks /TR）：
#   "D:\pycharm3\.venv\Scripts\pythonw.exe" "D:\自动出票数据分析项目\silent_task.pyw" fetch --yesterday
#   "D:\pycharm3\.venv\Scripts\pythonw.exe" "D:\自动出票数据分析项目\silent_task.pyw" fetch --days 2 --trigger
# 原理：pythonw 本身无控制台；再把 stdout/stderr 引到 devnull，
# 避免 auto_sync 内部 print 在无控制台环境下抛错。
import os
import sys

_base = os.path.dirname(os.path.abspath(__file__))
os.chdir(_base)
sys.path.insert(0, _base)

sys.stdout = open(os.devnull, 'w', encoding='utf-8', errors='replace')
sys.stderr = sys.stdout

sys.argv = ['auto_sync'] + sys.argv[1:]

from auto_sync.__main__ import main

sys.exit(main())
