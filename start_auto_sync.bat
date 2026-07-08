@echo off
REM ============================================
REM   启动 auto_sync 后台监控（v1.0）
REM   行为：新 xlsx 出现 → 自动跑 gen → 自动 git push
REM   状态查询：python -m auto_sync status
REM   停止：Ctrl+C
REM ============================================
chcp 65001 >nul
title auto_sync 后台监控

cd /d "%~dp0"

echo.
echo ============================================
echo   auto_sync - 自动同步 xlsx 到 dashboard
echo ============================================
echo.
echo   监控目录：C:\Users\admin\Desktop\出票总订单数据\
echo   状态查询：python -m auto_sync status
echo   历史记录：python -m auto_sync history
echo   手动触发：python -m auto_sync trigger
echo.
echo   启动中...

python -m auto_sync start --foreground

echo.
echo ============================================
echo   auto_sync 已停止
echo ============================================
pause