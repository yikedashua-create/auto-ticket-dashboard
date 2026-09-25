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
schtasks /Create /TN "auto_ticket_dashboard_sync_fetch" /SC DAILY /ST 08:35 /F ^
    /TR "cmd /c cd /d \"%PROJ%\" && \"%PY%\" -m auto_sync fetch --days 2 --trigger"
if %errorLevel% neq 0 echo [warn] daily fetch task failed

echo [3/4] register 30-min fallback task...
schtasks /Create /TN "auto_ticket_dashboard_sync_30min" /SC MINUTE /MO 30 /F ^
    /TR "cmd /c cd /d \"%PROJ%\" && \"%PY%\" -m auto_sync fetch --yesterday"
if %errorLevel% neq 0 echo [warn] 30-min task failed

echo [4/4] start daemon now...
cd /d "%PROJ%"
"%PY%" -m auto_sync daemon
"%PY%" -m auto_sync status

echo.
echo done. to delete tasks:
echo   schtasks /Delete /TN "auto_ticket_dashboard_sync" /F
echo   schtasks /Delete /TN "auto_ticket_dashboard_sync_fetch" /F
echo   schtasks /Delete /TN "auto_ticket_dashboard_sync_30min" /F
