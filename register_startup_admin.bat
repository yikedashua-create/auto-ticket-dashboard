@echo off
REM ============================================
REM   注册 auto_sync 计划任务（需右键 -> 以管理员身份运行）
REM
REM   2026-09-16 迁移到 D 盘后重写：
REM     1) 任务改用本脚本所在目录（%~dp0），不再写死盘符路径，
REM        避免中文路径在不同编码下被写坏
REM     2) 用 venv 解释器绝对路径（不依赖 PATH 里的 python）
REM     3) 顺手结束 E 盘旧副本残留的守护进程、清理其锁文件
REM
REM   为什么需要 admin？
REM   - schtasks 创建 SYSTEM 级任务（/RL HIGHEST）需要管理员权限
REM   - 结束由 SYSTEM 启动的旧 daemon 也需要管理员权限
REM ============================================
chcp 65001 >nul
title 注册 auto_sync 计划任务（需 admin）

set "PROJ=%~dp0"
if "%PROJ:~-1%"=="\" set "PROJ=%PROJ:~0,-1%"
set "PY=D:\pycharm3\.venv\Scripts\python.exe"
set "OLDE=E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard"

echo.
echo ============================================
echo   auto_sync 计划任务 - 注册器
echo ============================================
echo.

net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 需要管理员权限
    echo        请右键此文件 -^> 选择"以管理员身份运行"
    pause
    exit /b 1
)

echo [校验] 项目目录 = %PROJ%
if not exist "%PROJ%\gen_dashboard_data.py" (
    echo [错误] 项目目录里找不到 gen_dashboard_data.py，路径可能被写坏，已中止
    pause
    exit /b 1
)
if not exist "%PROJ%\.git" (
    echo [错误] 项目目录不是 git 仓库，已中止
    pause
    exit /b 1
)
if not exist "%PY%" (
    echo [错误] 找不到 venv 解释器: %PY%
    pause
    exit /b 1
)
echo [校验] 解释器 = %PY%
echo.

echo [1/6] 结束残留的 auto_sync / gen 进程（含 E 盘 SYSTEM 旧守护进程）...
REM 注意：过滤条件必须限定 Name like python* —— 否则 powershell 自己的
REM       命令行里含 "auto_sync" 字面量，会把自身也杀掉
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.Name -like 'python*' -and ($_.CommandLine -like '*auto_sync*' -or $_.CommandLine -like '*gen_dashboard_data.py*') } | ForEach-Object { Write-Host ('        kill PID ' + $_.ProcessId + '  ' + $_.Name); Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul

echo.
echo [2/6] 清理 E 盘旧副本的锁文件（防止旧副本再被拉起）...
for %%F in ("%OLDE%\auto_sync\data\daemon.lock" "%OLDE%\auto_sync\data\daemon.pid" "%OLDE%\auto_sync\data\gen.lock") do (
    if exist %%F ( del /q %%F & echo         removed %%~nxF )
)

echo.
echo [3/6] 注册开机自启任务 -^> %PROJ%
schtasks /Create /TN "auto_ticket_dashboard_sync" /SC ONSTART /RL HIGHEST /F ^
    /TR "cmd /c cd /d \"%PROJ%\" && \"%PY%\" -m auto_sync start --foreground"
if %errorLevel% neq 0 echo [警告] 开机自启任务注册失败

echo.
echo [4/6] 注册每日 08:35 主拉取任务（fetch 昨天+前天 + gen + push）-^> %PROJ%
REM 2026-09-24 修复：重装前 30 分钟任务只跑 trigger 从不 fetch，
REM 导致 9/17 起数据断更（watcher 等不到新文件）。主路径改为每日定点拉取。
schtasks /Create /TN "auto_ticket_dashboard_sync_fetch" /SC DAILY /ST 08:35 /RL HIGHEST /F ^
    /TR "cmd /c cd /d \"%PROJ%\" && \"%PY%\" -m auto_sync fetch --days 2 --trigger"
if %errorLevel% neq 0 echo [警告] 每日拉取任务注册失败

echo.
echo [5/6] 注册 30 分钟兜底任务（fetch 昨天，存在即跳过；新文件落地由 daemon watcher 触发 gen）-^> %PROJ%
schtasks /Create /TN "auto_ticket_dashboard_sync_30min" /SC MINUTE /MO 30 /F ^
    /TR "cmd /c cd /d \"%PROJ%\" && \"%PY%\" -m auto_sync fetch --yesterday"
if %errorLevel% neq 0 echo [警告] 30 分钟兜底任务注册失败

echo.
echo [6/6] 立即启动 daemon 并验证...
cd /d "%PROJ%"
"%PY%" -m auto_sync daemon
timeout /t 5 /nobreak >nul
"%PY%" -m auto_sync status

echo.
echo ============================================
echo   完成。三个任务都已指向当前项目目录：
echo     auto_ticket_dashboard_sync         开机自启 daemon（watcher+token保活）
echo     auto_ticket_dashboard_sync_fetch   每日 08:35 拉数+生成+推送（主路径）
echo     auto_ticket_dashboard_sync_30min   每 30 分钟补拉昨天（兜底，按文件驱动）
echo.
echo   查看任务:
echo     schtasks /Query /TN "auto_ticket_dashboard_sync" /V /FO LIST
echo     schtasks /Query /TN "auto_ticket_dashboard_sync_fetch" /V /FO LIST
echo     schtasks /Query /TN "auto_ticket_dashboard_sync_30min" /V /FO LIST
echo.
echo   删除任务（如需）:
echo     schtasks /Delete /TN "auto_ticket_dashboard_sync" /F
echo     schtasks /Delete /TN "auto_ticket_dashboard_sync_fetch" /F
echo     schtasks /Delete /TN "auto_ticket_dashboard_sync_30min" /F
echo ============================================
pause
