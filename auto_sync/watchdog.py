# -*- coding: utf-8 -*-
"""
auto_sync 看门狗 v1（2026-11-03）—— 数据同步链路自愈 + 告警

背景：2026-10 下旬起"数据不及时更新"反复发生，共 4 类故障模式：
  A. gen 中途静默死亡（eod 17:10 任务 4 天败 3 次；10-15 前 numpy 崩溃 5 次）
  B. gen 完成但 trigger 不提交（10-31、11-01 两次，靠人工补推）
  C. push 被拒（non-fast-forward）无重试（10-18 互踩，卡 4 小时）
  D. 08:35 主任务"文件已存在即跳过"→ 昨天完整终值不上线
     （10-30 新增 eod 任务拉过今日盘中版后必现：次日主任务 SKIP → 不 gen）

本看门狗由计划任务每 30 分钟触发（pythonw silent_task.pyw watchdog），
按序执行检查与自愈；gen 运行中（gen.lock 新鲜）则整轮跳过，避免打架。

检查项（顺序执行，全部只动数据文件、不碰代码）：
  1. 数据文件未提交（dashboard_data.json / monthly / targets.json 修改中）
     → commit + push(rebase重试) + 锚点同步                    ← 兜住 B
  2. 锚点漂移（dashboard_v5.html 的 const COMMIT != HEAD short hash）
     → 自动补锚点 commit+push                                  ← 兜住"锚点失败次日不自愈"
  3. 本地领先 origin（有 commit 没 push 成功）
     → push(rebase重试)                                        ← 兜住 C 残留
  4. 数据新鲜度：dashboard_data.json 未覆盖到"昨天"
     且当前已过 09:30（给 08:35 正常流程留时间）
     → 自动 fetch --days 2 --force --trigger 补拉补算          ← 兜住 A/D
每次自愈动作汇总推钉钉（状态翻转去重，同一状态连续出现只报一次）。
"""
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta

log = logging.getLogger("auto_sync.watchdog")

_REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA_DIR = os.path.join(_REPO, "auto_sync", "data")
_GEN_LOCK = os.path.join(_DATA_DIR, "gen.lock")
_STATE_FILE = os.path.join(_DATA_DIR, "watchdog_state.json")
NOTIFY_YAML = r"E:\Work\Documents\凭据\elephant_notify.yaml"
GIT_REMOTE = "origin"
GIT_BRANCH = "main"
BJ = timezone(timedelta(hours=8))


# ---------- 工具 ----------

def _now_bj() -> datetime:
    return datetime.now(BJ)


def _run(cmd, timeout=600, cwd=_REPO):
    """跑命令并捕获输出（与 trigger._run 同风格）"""
    cmd = list(cmd)
    if cmd[0] == "python":
        py_dir = os.path.dirname(sys_executable())
        candidate = os.path.join(py_dir, "python.exe")
        cmd[0] = candidate if os.path.exists(candidate) else sys_executable()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        return r.returncode == 0, (r.stdout or ""), (r.stderr or ""), r.returncode
    except subprocess.TimeoutExpired:
        return False, "", f"超时 ({timeout}s)", -1
    except Exception as e:
        return False, "", str(e), -1


def sys_executable():
    import sys
    return sys.executable


def gen_running():
    """gen.lock 存在、未超龄(50min)、持有者进程存活 → gen 正在跑"""
    if not os.path.exists(_GEN_LOCK):
        return False
    try:
        age = time.time() - os.path.getmtime(_GEN_LOCK)
        with open(_GEN_LOCK) as f:
            pid = f.read().strip().split("|")[0]
        r = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"],
                           capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0)
        return str(pid) in (r.stdout or "") and age < 50 * 60
    except (OSError, ValueError):
        return False


# ---------- 检查与自愈 ----------

def check_uncommitted(actions):
    """1) 数据文件修改未提交 → commit + push + 锚点（兜住故障 B）"""
    ok, out, err, _ = _run(["git", "status", "--porcelain", "--",
                            "dashboard_data.json", "monthly/", "targets.json"])
    if not ok:
        actions.append(("检查未提交", False, f"git status 失败: {err[:120]}"))
        return
    if not out.strip():
        return  # 干净，无事
    ok, out, err, _ = _run(["git", "add", "dashboard_data.json", "monthly/", "targets.json"])
    if not ok:
        actions.append(("补提交", False, f"git add 失败: {err[:120]}"))
        return
    msg = f"data: watchdog 自动补提交 (gen 完成但 trigger 未提交, {_now_bj():%m-%d %H:%M})"
    ok, out, err, _ = _run(["git", "commit", "-m", msg])
    if not ok:
        actions.append(("补提交", False, f"git commit 失败: {err[:150]}"))
        return
    from .trigger import git_push_with_rebase
    pr = git_push_with_rebase(_REPO, GIT_REMOTE, GIT_BRANCH)
    if not pr.success:
        actions.append(("补提交", False, f"commit 成功但 push 失败: {pr.error[:150]}"))
        return
    sync = sync_anchor(actions)  # 顺手把锚点也对齐
    actions.append(("补提交", True, f"自动 commit+push 成功 (含锚点同步: {'OK' if sync else '失败,下轮重试'})"))


def sync_anchor(actions) -> bool:
    """锚点 const COMMIT 对齐到 HEAD（兜住锚点漂移）"""
    ok, out, err, _ = _run(["git", "rev-parse", "--short", "HEAD"], timeout=15)
    if not ok:
        return False
    new_hash = out.strip()
    html_path = os.path.join(_REPO, "dashboard_v5.html")
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    import re
    new_html, n = re.subn(r'const\s+COMMIT\s*=\s*"[a-f0-9]+"\s*;',
                          f'const COMMIT = "{new_hash}";', html, count=1)
    if n == 0 or new_html == html:
        return True  # 无需改
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)
    _run(["git", "add", "dashboard_v5.html"], timeout=30)
    ok, out, err, _ = _run(["git", "commit", "-m",
                            f"chore: watchdog 同步 HTML COMMIT 到 {new_hash}"], timeout=30)
    if not ok:
        actions.append(("补锚点", False, f"commit 失败: {err[:120]}"))
        return False
    from .trigger import git_push_with_rebase
    pr = git_push_with_rebase(_REPO, GIT_REMOTE, GIT_BRANCH)
    if not pr.success:
        actions.append(("补锚点", False, f"push 失败: {pr.error[:120]}"))
        return False
    actions.append(("补锚点", True, f"锚点 {new_hash} 已推送"))
    return True


def check_unpushed(actions):
    """3) 本地领先 origin → push（兜住故障 C 残留）"""
    ok, out, err, _ = _run(["git", "rev-parse", "HEAD"], timeout=15)
    if not ok:
        return
    local = out.strip()
    ok, out, err, _ = _run(["git", "rev-parse", f"{GIT_REMOTE}/{GIT_BRANCH}"], timeout=15)
    if not ok:
        _run(["git", "fetch", GIT_REMOTE], timeout=120)
        ok, out, err, _ = _run(["git", "rev-parse", f"{GIT_REMOTE}/{GIT_BRANCH}"], timeout=15)
        if not ok:
            return
    if local == out.strip():
        return
    from .trigger import git_push_with_rebase
    pr = git_push_with_rebase(_REPO, GIT_REMOTE, GIT_BRANCH)
    actions.append(("补推送", pr.success,
                    f"本地领先 origin，push {'成功' if pr.success else '失败: ' + (pr.error or '')[:120]}"))


def check_freshness(actions):
    """4) dashboard_data.json 未覆盖到昨天 → force 补拉补算（兜住故障 A/D）"""
    now = _now_bj()
    if now.hour < 9 or (now.hour == 9 and now.minute < 30):
        return  # 08:35 正常流程可能还在跑，别抢
    yest = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    dd = os.path.join(_REPO, "dashboard_data.json")
    try:
        with open(dd, encoding="utf-8") as f:
            d = json.load(f)
        months = d.get("months", {})
        latest_date = ""
        for m in sorted(months):
            daily = months[m].get("daily") or []
            if daily:
                latest_date = daily[-1].get("date", "")
        gen_at = d.get("generated_at", "")
    except Exception as e:
        actions.append(("数据新鲜度", False, f"dashboard_data.json 解析失败: {e}"))
        return
    if latest_date >= yest:
        return  # 覆盖到昨天，新鲜
    actions.append(("数据新鲜度", False,
                    f"数据只到 {latest_date or gen_at}，未覆盖到昨天 {yest} → 自动补拉补算（约40分钟）"))
    ok, out, err, rc = _run(
        ["python", "-m", "auto_sync", "fetch", "--days", "2", "--force", "--trigger"],
        timeout=9000)
    actions.append(("补拉补算", ok,
                    f"fetch --days 2 --force --trigger 退出码 {rc}；{(out or err)[-300:]}"))


# ---------- 告警 ----------

def _load_state():
    try:
        with open(_STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def _save_state(st):
    try:
        with open(_STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(st, f, ensure_ascii=False)
    except OSError:
        pass


def alert_if_changed(status_key: str, detail: str):
    """状态翻转去重告警：同一 status_key 连续相同则不再发"""
    st = _load_state()
    if st.get("last_status_key") == status_key:
        return
    st["last_status_key"] = status_key
    _save_state(st)
    try:
        from .notify import load_config_from_yaml, send
        cfg = load_config_from_yaml(NOTIFY_YAML)
        report = {
            "title": "🛡️ 数据看板看门狗触发自愈",
            "markdown": (
                f"### 🛡️ 看门狗检测到数据链路异常并已自愈\n\n"
                f"- 状态：{status_key}\n"
                f"- 详情：{detail}\n"
                f"- 时间：{_now_bj():%Y-%m-%d %H:%M:%S}\n\n"
                "详细日志见 `auto_sync/data/task_watchdog.log`；"
                "若自愈失败请检查 `gen_dashboard_data.py` 或联系看板维护者。"
            ),
        }
        send(report, cfg)
    except Exception as e:
        log.warning(f"钉钉告警失败: {e}")


# ---------- 主入口 ----------

def run_watchdog() -> int:
    started = _now_bj()
    actions = []  # (名称, 成功?, 说明)
    if gen_running():
        print("[watchdog] gen 正在运行（gen.lock 新鲜），本轮跳过所有自愈")
        print(f"[watchdog] done ({_now_bj() - started}) exit 0")
        return 0

    try:
        check_uncommitted(actions)
        check_unpushed(actions)
        check_freshness(actions)
    except Exception as e:
        actions.append(("看门狗自身", False, f"未捕获异常: {e}"))

    # 汇总状态 + 告警（有动作才评估；全干净则清除告警状态）
    if not actions:
        st = _load_state()
        if st.get("last_status_key") not in (None, "ok"):
            st["last_status_key"] = "ok"
            _save_state(st)
        print(f"[watchdog] 全部检查通过，无需自愈 ({_now_bj() - started}) exit 0")
        return 0

    ok_cnt = sum(1 for _, ok, _ in actions if ok)
    fail_cnt = len(actions) - ok_cnt
    lines = [f"• {'✅' if ok else '❌'} {name}: {detail}" for name, ok, detail in actions]
    status_key = "; ".join(f"{name}:{'ok' if ok else 'FAIL'}" for name, ok, _ in actions)
    alert_if_changed(status_key, "；".join(f"{n}({d})" for n, ok, d in actions if not ok) or "全部自愈成功")
    print(f"[watchdog] 执行了 {len(actions)} 项动作（成功 {ok_cnt} / 失败 {fail_cnt}）：")
    for l in lines:
        print("  " + l)
    print(f"[watchdog] done ({_now_bj() - started}) exit {0 if fail_cnt == 0 else 1}")
    return 0 if fail_cnt == 0 else 1
