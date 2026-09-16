@echo off
REM ============================================
REM   一键更新数据（v10.14.2 不用弹窗）
REM   v10.14.4 支持 --force 参数（强制全转 xlsx）
REM   2026-09-16 迁移修复：
REM     - cd 到 bat 自身所在目录（原来写死 C:\Users\admin\Desktop\auto-ticket-dashboard，该目录已不存在）
REM     - 改用 venv 解释器（裸 python 依赖 PATH，可能缺 pyarrow/watchdog）
REM ============================================
chcp 65001 >nul
title 一键更新数据
cd /d "%~dp0"
cls
echo.
echo ============================================
echo   自动出票数据看板 - 一键更新
echo   项目目录: %CD%
echo ============================================
echo.
echo 正在跑数据生成 + Git 推送 ...
echo.
"D:\pycharm3\.venv\Scripts\python.exe" update_data.py %*
echo.
echo ============================================
echo   完整结果已写入 _last_result.txt
echo   正在用记事本打开 ...
echo ============================================
echo.
start "" notepad.exe "_last_result.txt"
echo 关闭记事本后，按任意键退出 ...
pause >nul