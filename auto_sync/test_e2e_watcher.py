"""端到端测试 watcher 自动触发

模拟：
  1. 创建临时监控目录
  2. 启动 watcher 后台监控
  3. 复制一个新 xlsx 到目录（用项目里现有的 xlsx 模拟）
  4. 等 10 秒看是否自动触发
  5. 检查 status.db 是否有触发记录
  6. 停止 watcher

用 --no-push 避免真推 GitHub。
"""
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, r"C:\Users\admin\Desktop\auto-ticket-dashboard")

from auto_sync import AutoSyncManager, AutoSyncConfig


def test_watcher_auto_trigger():
    print("=" * 60)
    print("测试 1: watcher 自动触发")
    print("=" * 60)

    # 创建临时监控目录
    tmpdir = tempfile.mkdtemp(prefix="auto_sync_test_")
    print(f"临时监控目录: {tmpdir}")

    # 找一个真实的 xlsx 作为"新文件"源
    src_xlsx = None
    src_dir = r"C:\Users\admin\Desktop\出票总订单数据"
    if os.path.isdir(src_dir):
        for f in sorted(os.listdir(src_dir)):
            if f.endswith(".xlsx") and not f.startswith("~"):
                src_xlsx = os.path.join(src_dir, f)
                break

    if not src_xlsx:
        print(f"❌ 找不到源 xlsx in {src_dir}")
        return

    print(f"源文件: {src_xlsx}")

    # 创建 manager（指向临时目录 + --no-push）
    config = AutoSyncConfig(
        watch_dir=tmpdir,
        stability_check_seconds=1.0,
        min_file_age_seconds=0.5,
        cooldown_seconds=2.0,
        push_enabled=False,
        status_db_path=os.path.join(tmpdir, "test_status.db"),
    )

    mgr = AutoSyncManager(config=config, script_dir=r"C:\Users\admin\Desktop\auto-ticket-dashboard")

    # 启动后台
    print("\n启动 watcher 后台...")
    mgr.start_background()
    time.sleep(0.5)
    assert mgr.is_running(), "watcher 没启动"
    print("✅ watcher 已启动")

    # 复制 xlsx 到监控目录（模拟"新文件出现"）
    test_xlsx = os.path.join(tmpdir, "test_2026-07-08.xlsx")
    print(f"\n复制 xlsx → {test_xlsx}")
    shutil.copy2(src_xlsx, test_xlsx)

    # 让 watcher 检测到（需要稳定性检查 1s + 触发时间 ~125s）
    print(f"\n等待 watcher 检测 + 触发（稳定性 1s + 触发 ~125s）...")
    time.sleep(3)  # 先等 3 秒让稳定性检查 + 触发启动
    status = mgr.get_status()
    print(f"\n[3s 后] last_trigger_at: {status.last_trigger_at}")
    print(f"[3s 后] last_file:       {status.last_file}")

    if status.last_trigger_at:
        print("✅ watcher 已检测到文件并触发！")
    else:
        print("⚠️  还在稳定性检查中（再等 5s）...")
        time.sleep(5)
        status = mgr.get_status()
        print(f"[8s 后] last_trigger_at: {status.last_trigger_at}")
        print(f"[8s 后] last_file:       {status.last_file}")

    # 看历史
    history = mgr.get_history(limit=5)
    print(f"\n历史记录: {len(history)} 条")
    for h in history:
        print(f"  {h.triggered_at} {h.file_path} {h.status} {h.duration:.1f}s")

    # 停止 watcher
    print("\n停止 watcher...")
    mgr.stop()
    assert not mgr.is_running()
    print("✅ watcher 已停止")

    # 清理
    shutil.rmtree(tmpdir)
    print(f"\n清理: {tmpdir}")


if __name__ == "__main__":
    test_watcher_auto_trigger()