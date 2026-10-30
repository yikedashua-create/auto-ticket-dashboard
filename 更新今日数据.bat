@echo off
REM ============================================
REM   更新今日盘中数据（2026-10-26 新增）
REM   拉今日 xlsx（--force 覆盖盘中已拉的版本）→ gen → commit/push → 锚点
REM   用时约 40 分钟（gen 约 33 分钟），完成后线上看板 Ctrl+F5 强刷可见
REM   今日数字约 95% 完整（晚上还有少量订单），明早 08:35 自动校正为终值
REM ============================================
chcp 65001 >nul
title 更新今日盘中数据
cd /d "%~dp0"
cls
echo.
echo ============================================
echo   自动出票数据看板 - 今日盘中数据更新
echo   项目目录: %CD%
echo   预计 40 分钟，完成后线上看板强刷可见
echo ============================================
echo.
"D:\pycharm3\.venv\Scripts\python.exe" -m auto_sync fetch --days 1 --today --force --trigger
echo.
echo ============================================
echo   完成（若上方无 FAIL 字样）。
echo   结果详情见 auto_sync\data\auto_sync.log
echo ============================================
echo 按任意键退出 ...
pause >nul
