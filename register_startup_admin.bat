@echo off
REM ============================================
REM   一键注册 auto_sync 开机自启（需右键 → 以管理员身份运行）
REM
REM   为什么需要 admin？
REM   - schtasks /Create /SC ONSTART 触发器要 admin 权限（注册到 SYSTEM 级）
REM   - 普通用户只能注册用户级任务（/SC ONLOGON 也不够，仍需 admin）
REM
REM   装完效果：
REM   - 开机 → auto_sync 后台启动 → 监控 E:\Work\Data\订单\出票总订单数据
REM   - 新 xlsx 拖进目录 → 自动 gen_dashboard_data + git commit + push
REM
REM   已有 30 分钟兜底任务：auto_ticket_dashboard_sync_30min
REM   这个脚本额外加一个开机自启（电脑重启后立即启动 daemon，不用等 30 分钟）
REM ============================================
chcp 65001 >nul
title 注册 auto_sync 开机自启（需 admin）

echo.
echo ============================================
echo   auto_sync 开机自启 - 注册器
echo ============================================
echo.

REM 检查 admin 权限
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 需要管理员权限
    echo 请右键此文件 → 选择"以管理员身份运行"
    pause
    exit /b 1
)

cd /d "%~dp0"

echo [1/3] 注册开机启动任务...
schtasks /Create /TN "auto_ticket_dashboard_sync" /SC ONSTART ^
    /TR "cmd /c cd /d E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard ^&^& python -m auto_sync start --foreground" ^
    /RL HIGHEST /F
if %errorLevel% neq 0 (
    echo [错误] 注册开机任务失败
    pause
    exit /b 1
)

echo.
echo [2/3] 检查 30 分钟兜底任务...
schtasks /Query /TN "auto_ticket_dashboard_sync_30min" >nul 2>&1
if %errorLevel% neq 0 (
    echo 注册 30 分钟兜底任务...
    schtasks /Create /TN "auto_ticket_dashboard_sync_30min" /SC MINUTE /MO 30 ^
        /TR "cmd /c cd /d E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard ^&^& python -m auto_sync trigger" ^
        /F
)

echo.
echo [3/3] 验证任务...
echo.
echo --- 开机启动任务 ---
schtasks /Query /TN "auto_ticket_dashboard_sync" 2>nul | findstr /C:"TaskName" /C:"Status" /C:"Next Run Time"
echo.
echo --- 30 分钟兜底任务 ---
schtasks /Query /TN "auto_ticket_dashboard_sync_30min" 2>nul | findstr /C:"TaskName" /C:"Status" /C:"Next Run Time"

echo.
echo ============================================
echo   完成！电脑重启后 daemon 会自动启动
echo.
echo   状态查询:
echo     schtasks /Query /TN "auto_ticket_dashboard_sync"
echo     schtasks /Query /TN "auto_ticket_dashboard_sync_30min"
echo.
echo   停止:
echo     schtasks /Delete /TN "auto_ticket_dashboard_sync" /F
echo ============================================
echo.
timeout /t 10 /nobreak >nul
