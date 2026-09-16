@echo off
REM ============================================
REM   停止 auto_sync 后台守护进程
REM   2026-09-16：改用 venv 解释器
REM   注意：若 daemon 由计划任务以 SYSTEM 身份启动，
REM         此脚本需要"以管理员身份运行"才能停止
REM ============================================
chcp 65001 >nul
title auto_sync 停止器

cd /d "%~dp0"

echo.
echo ============================================
echo   auto_sync - 停止守护进程
echo ============================================
echo.

"D:\pycharm3\.venv\Scripts\python.exe" -m auto_sync stop

echo.
echo ============================================
echo   完成
echo ============================================
timeout /t 3 /nobreak >nul