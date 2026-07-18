# -*- coding: utf-8 -*-
"""
update_data.py — 一键更新数据 + 推送到 GitHub + 弹窗反馈

新人日常操作：
  1. 把 xlsx 放到 桌面\出票总订单数据\
  2. 双击桌面"更新数据.bat"
  3. 看弹窗（✅关掉）

本脚本自动完成：
  - 跑 gen_dashboard_data.py（数据生成）
  - 解析输出提取 KPI（新增天数 / 总单数 / B路径失败数）
  - git add + commit（自动 commit message）
  - git push（GitHub → Streamlit Cloud 自动重新部署）
  - 弹窗显示结果（成功 / 失败 / 详细原因）
"""
import os
import re
import sys
import subprocess
from datetime import datetime, timezone, timedelta

# 2026-07-17 修复：Windows cmd 默认 GBK 编码，打印 ✓/✖ 这类 Unicode 字符
# 会 UnicodeEncodeError 崩溃。强制 stdout 用 UTF-8（Python 3.7+）。
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass  # 旧版 Python 跳过，崩了再走 ASCII 兜底

# ============== 配置 ==============
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GEN_SCRIPT = os.path.join(SCRIPT_DIR, "gen_dashboard_data.py")
DATA_DIR = r"C:\Users\admin\Desktop\出票总订单数据"
GIT_REMOTE = "origin"
GIT_BRANCH = "main"
BJ_TZ = timezone(timedelta(hours=8))
DESKTOP = os.path.join(os.path.expanduser("~"), "Desktop")
SHORTCUT_NAME = "更新数据.lnk"
SHORTCUT_BAT = "更新数据.bat"


def show_result(title, message, is_error=False):
    """显示结果（✅/❌）
    v10.14.2（2026-07-02）：彻底放弃弹窗
    原因：tkinter 和 ctypes.MessageBoxW 在用户 Windows 环境都闪退（GUI 子系统兼容问题）
    方案：写 _last_result.txt + print 到 cmd，由 bat 脚本调 notepad 打开文件
    优势：纯文件 I/O + cmd 输出，不依赖任何 GUI 框架，绝对不闪退
    """
    # 2026-07-17 修复：原 "✖"/"✔" 在 Windows GBK 编码下崩码。改 ASCII 兜底。
    icon = "[FAIL]" if is_error else "[OK]"
    full_title = f"{icon} {title}"
    # 1) 写文件（兜底，永远成功）
    try:
        log_path = os.path.join(SCRIPT_DIR, "_last_result.txt")
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"{full_title}\n{'=' * 50}\n{message}\n")
    except Exception as e:
        print(f"[警告] 写结果文件失败：{e}")
    # 2) print 到 stdout（cmd 窗口看）
    print(f"\n{full_title}\n{'-' * 50}\n{message}\n")
    sys.stdout.flush()


def ensure_desktop_shortcut():
    """第一次跑时自动在桌面创建快捷方式（只创建一次，后续检查）"""
    shortcut_path = os.path.join(DESKTOP, SHORTCUT_NAME)
    bat_path = os.path.join(SCRIPT_DIR, SHORTCUT_BAT)
    if os.path.exists(shortcut_path):
        return  # 已有
    if not os.path.exists(bat_path):
        return
    try:
        # 用 PowerShell 创建 .lnk（避免 pywin32 依赖）
        ps_cmd = (
            f'$ws = New-Object -ComObject WScript.Shell; '
            f'$lnk = $ws.CreateShortcut("{shortcut_path}"); '
            f'$lnk.TargetPath = "{bat_path}"; '
            f'$lnk.WorkingDirectory = "{SCRIPT_DIR}"; '
            f'$lnk.IconLocation = "shell32.dll,12"; '
            f'$lnk.Save()'
        )
        rc, _, err = run_cmd(["powershell", "-Command", ps_cmd])
        if rc == 0:
            print(f"  [setup] 已在桌面创建快捷方式: {shortcut_path}")
        else:
            print(f"  [setup] 桌面快捷方式创建失败: {err[:100]}")
    except Exception as e:
        print(f"  [setup] 桌面快捷方式异常: {e}")


def run_cmd(cmd, cwd=None, timeout=None):
    """跑命令，返回 (returncode, stdout, stderr)"""
    try:
        result = subprocess.run(
            cmd, shell=True, cwd=cwd,
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "命令超时"
    except Exception as e:
        return -1, "", str(e)


def check_environment():
    """检查环境（python / pyarrow / xlsx 目录 / git 仓库）"""
    # Python
    rc, out, _ = run_cmd("python --version")
    if rc != 0:
        return False, f"Python 未安装或未配置 PATH\n请先安装 Python 3.10+"
    # pyarrow
    rc, _, _ = run_cmd("python -c \"import pyarrow; print(pyarrow.__version__)\"")
    if rc != 0:
        return False, f"pyarrow 未安装\n请运行: pip install pyarrow"
    # xlsx 源目录
    if not os.path.isdir(DATA_DIR):
        return False, f"xlsx 源目录不存在:\n{DATA_DIR}\n请确认桌面有这个目录"
    # git 仓库
    if not os.path.isdir(os.path.join(SCRIPT_DIR, ".git")):
        return False, f"当前目录不是 git 仓库:\n{SCRIPT_DIR}"
    return True, None


def parse_gen_output(stdout):
    """从 gen_dashboard_data.py 输出提取关键 KPI"""
    kpi = {
        "new_days": 0,  # 新增天数
        "total_orders": 0,  # 总单数
        "b_fail": 0,  # B 路径失败
        "sync_count": 0,  # 同步 parquet 数
        "skip_count": 0,  # 跳过 parquet 数
        "monthly_count": 0,  # 月度 json 数
    }
    # 同步统计
    m = re.search(r"\[sync\]\s*xlsx=(\d+),\s*新转=(\d+),\s*跳过=(\d+)", stdout)
    if m:
        kpi["sync_count"] = int(m.group(2))
        kpi["skip_count"] = int(m.group(3))
        kpi["new_days"] = int(m.group(2))  # 新转的就是新增天数
    # 总单数
    m = re.search(r"\[统计\]\s*月份=.*?总单数=([\d,]+)", stdout)
    if m:
        kpi["total_orders"] = int(m.group(1).replace(",", ""))
    # B 路径失败（从 6月族级 或 月度 json）
    m = re.search(r"6月\s*fail_reasons_B 总=([\d,]+)", stdout)
    if m:
        kpi["b_fail"] = int(m.group(1).replace(",", ""))
    return kpi


def run_gen(force=False):
    """跑 gen_dashboard_data.py，捕获输出"""
    print(f"[update_data] 跑 gen_dashboard_data.py ...")
    cmd = f"python \"{GEN_SCRIPT}\" --month all"
    if force:
        cmd += " --force"
    rc, out, err = run_cmd(
        cmd,
        timeout=600  # 10 分钟超时
    )
    return rc, out, err


def git_commit_and_push():
    """git add + commit + push"""
    # 检查变更
    rc, out, _ = run_cmd("git status --porcelain", cwd=SCRIPT_DIR)
    if rc != 0:
        return False, "git status 失败", None
    if not out.strip():
        return True, "无变更（已是最新）", None  # 没东西要 commit

    # add
    rc, _, err = run_cmd("git add dashboard_data.json gen_dashboard_data.py monthly/ raw/ requirements.txt 2>nul || git add -A",
                         cwd=SCRIPT_DIR)
    if rc != 0:
        return False, f"git add 失败: {err}", None

    # commit
    today = datetime.now(BJ_TZ).strftime("%Y-%m-%d %H:%M")
    msg = f"data: 同步 {today}"
    rc, _, err = run_cmd(f'git commit -m "{msg}"', cwd=SCRIPT_DIR)
    if rc != 0:
        return False, f"git commit 失败: {err}", None

    # push
    rc, out, err = run_cmd(f"git push {GIT_REMOTE} {GIT_BRANCH}", cwd=SCRIPT_DIR, timeout=300)
    if rc != 0:
        return False, f"git push 失败（但已 commit，本地有数据）:\n{err[:200]}", msg
    return True, "推送成功", msg


def format_success_message(kpi, commit_msg):
    """格式化成功消息"""
    lines = [
        f"数据已更新并推送到 GitHub",
        f"",
        f"同步 parquet: 新转 {kpi['sync_count']} 个 / 跳过 {kpi['skip_count']} 个",
        f"新增天数: {kpi['new_days']}",
        f"5+6月总单数: {kpi['total_orders']:,}",
        f"6月 B 全自动失败: {kpi['b_fail']:,}",
        f"",
        f"git commit: {commit_msg or '(无变更)'}",
        f"git push: 成功 → Streamlit Cloud 自动重新部署",
        f"",
        f"刷新 dashboard: https://auto-ticket-dashboard.streamlit.app/",
    ]
    return "\n".join(lines)


def main():
    import sys as _sys
    force_mode = "--force" in _sys.argv
    print("=" * 60)
    print(f"[update_data] 启动 {datetime.now(BJ_TZ).strftime('%Y-%m-%d %H:%M:%S')}"
          f"{'  [--force 模式]' if force_mode else ''}")
    print("=" * 60)

    # 1. 检查环境
    print("[1/3] 检查环境 ...")
    ok, err = check_environment()
    if not ok:
        show_result("环境检查失败", err, is_error=True)
        return 1

    # 1.5 第一次跑时自动创建桌面快捷方式
    print("[1.5/3] 检查桌面快捷方式 ...")
    ensure_desktop_shortcut()

    # 2. 跑 gen
    print("[2/3] 跑数据生成 ...")
    rc, out, err = run_gen(force=force_mode)
    if rc != 0:
        msg = f"gen_dashboard_data.py 失败（退出码 {rc}）\n\n" + (err[-500:] if err else out[-500:])
        show_result("数据生成失败", msg, is_error=True)
        return 1
    kpi = parse_gen_output(out)
    print(f"  新转={kpi['sync_count']}, 跳过={kpi['skip_count']}, 总单数={kpi['total_orders']:,}")

    # 3. git commit + push
    print("[3/3] git commit + push ...")
    ok, msg, commit_msg = git_commit_and_push()
    if not ok:
        full = f"{msg}\n\n数据已生成到本地：\n{os.path.join(SCRIPT_DIR, 'dashboard_data.json')}\n\n可手动 git push 重试"
        show_result("推送失败", full, is_error=True)
        return 1

    if "无变更" in msg:
        show_result("已是最新",
                    f"没有新数据或变更。\n\n总单数: {kpi['total_orders']:,}\n6月 B 全自动失败: {kpi['b_fail']:,}")
        return 0

    show_result("更新成功", format_success_message(kpi, commit_msg), is_error=False)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        # 兜底：弹窗显示异常
        import traceback
        show_result("脚本异常", f"未捕获的异常:\n{traceback.format_exc()[-800:]}", is_error=True)
        sys.exit(1)