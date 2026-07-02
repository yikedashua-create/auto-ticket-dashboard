@echo off
REM ============================================
REM   一键更新数据（v10.14.2 不用弹窗）
REM ============================================
chcp 65001 >nul
title 一键更新数据
cd /d "C:\Users\admin\Desktop\auto-ticket-dashboard"
cls
echo.
echo ============================================
echo   自动出票数据看板 - 一键更新
echo ============================================
echo.
echo 正在跑数据生成 + Git 推送 ...
echo.
python update_data.py
echo.
echo ============================================
echo   完整结果已写入 _last_result.txt
echo   正在用记事本打开 ...
echo ============================================
echo.
start "" notepad.exe "_last_result.txt"
echo 关闭记事本后，按任意键退出 ...
pause >nul