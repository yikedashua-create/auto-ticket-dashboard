@echo off
REM ============================================
REM   启动 auto_sync 后台守护进程（v1.1）
REM   行为：真正脱离父进程，关 cmd 窗口不影响
REM   状态：python -m auto_sync status
REM   停止：双击 stop_auto_sync.bat
REM ============================================
chcp 65001 >nul
title auto_sync 启动器

cd /d "%~dp0"

echo.
echo ============================================
echo   auto_sync - 后台守护进程启动器
echo ============================================
echo.

REM 用 daemon 子命令启动（独立进程，关 cmd 不影响）
python -m auto_sync daemon %*

echo.
echo ============================================
echo   启动完成。可以关闭此窗口，daemon 仍在后台运行
echo   状态查询: python -m auto_sync status
echo   停止服务: stop_auto_sync.bat
echo ============================================
echo.
timeout /t 5 /nobreak >nul