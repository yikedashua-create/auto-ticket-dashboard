@echo off
REM ============================================
REM   Register auto_sync scheduled tasks (user level, no admin needed)
REM   2026-09-25: post-reinstall recovery without UAC.
REM   Difference vs register_startup_admin.bat:
REM     - tasks run as current user (only while logged on)
REM     - no /RL HIGHEST, no SYSTEM process cleanup
REM   Same task names: whichever runs later /F-overwrites the other.
REM   NOTE: keep this file pure ASCII - it may be run via Git Bash/cmd
REM   with mixed codepages; Chinese here breaks parsing.
REM ============================================
set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1]"
set "PY=D:\pycharm3\.venv\Scripts\python.exe"
set "PYW=D:\pycharm3\.venv\Scripts\pythonw.exe"

echo [check] project dir = %PROJ%
if not exist "%PROJ%\gen_dashboard_data.py" (
    echo [error] gen_dashboard_data.py not found, path broken, abort
    exit /b 1
)
if not exist "%PY%" (
    echo [error] venv python not found: %PY%
    exit /b 1
)

echo [1/4] register on-logon daemon task...
schtasks /Create /TN "auto_ticket_dashboard_sync" /SC ONLOGON /F ^
    /TR "cmd /c cd /d \"%PROJ%\" && \"%PY%\" -m auto_sync start --foreground"
if %errorLevel% neq 0 echo [warn] on-logon task failed

echo [2/4] register daily 08:35 fetch task...
REM 2026-11-03: 加 --force —— eod 任务(17:10)拉过今日盘中版后，次日 08:35
REM 若无 force 会因"文件已存在"跳过拉取→不 gen→昨天完整终值永不上线（11-03 实证）
schtasks /Create /TN "auto_ticket_dashboard_sync_fetch" /SC DAILY /ST 08:35 /F ^
    /TR "\"%PYW%\" \"%PROJ%\silent_task.pyw\" fetch --days 2 --force --trigger"
if %errorLevel% neq 0 echo [warn] daily fetch task failed

echo [3/4] register 2-hour fallback task (hidden, skip if exists)...
schtasks /Create /TN "auto_ticket_dashboard_sync_30min" /SC MINUTE /MO 120 /F ^
    /TR "\"%PYW%\" \"%PROJ%\silent_task.pyw\" fetch --yesterday"
if %errorLevel% neq 0 echo [warn] fallback task failed

echo [3.5/4] register watchdog task (every 30 min, self-heal + alert)...
REM 2026-11-03 新增：数据链路自愈看门狗（补提交/补锚点/补推送/数据新鲜度）
schtasks /Create /TN "auto_ticket_dashboard_sync_watchdog" /SC MINUTE /MO 30 /F ^
    /TR "\"%PYW%\" \"%PROJ%\silent_task.pyw\" watchdog"
if %errorLevel% neq 0 echo [warn] watchdog task failed

echo [4/4] start daemon now...
cd /d "%PROJ%"
"%PY%" -m auto_sync daemon
"%PY%" -m auto_sync status

echo.
echo done. to delete tasks:
echo   schtasks /Delete /TN "auto_ticket_dashboard_sync" /F
echo   schtasks /Delete /TN "auto_ticket_dashboard_sync_fetch" /F
echo   schtasks /Delete /TN "auto_ticket_dashboard_sync_30min" /F
