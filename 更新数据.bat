@echo off
REM ============================================
REM   一键更新数据
REM   用法：双击本文件即可
REM ============================================
chcp 65001 >nul
title 一键更新数据
cd /d "C:\Users\admin\Desktop\auto-ticket-dashboard"
echo.
echo ==========================================
echo   自动出票数据看板 - 一键更新
echo ==========================================
echo.
echo 正在检查环境并更新数据...
echo.
python update_data.py
echo.
echo 任意键关闭
pause >nul