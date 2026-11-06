"""auto_sync 触发器模块

触发后做什么：
  1. 跑 gen_dashboard_data.py 生成新 dashboard_data.json
  2. git add + commit
  3. git push 到 GitHub（streamlit cloud 自动重新部署）

设计：每个步骤独立函数，可单独调用（方便测试和扩展）。
"""
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional, List

log = logging.getLogger("auto_sync.trigger")


@dataclass
class StepResult:
    """单个步骤的执行结果"""
    name: str
    success: bool
    duration: float
    output: str = ""
    error: str = ""


@dataclass
class TriggerResult:
    """一次完整触发的结果"""
    success: bool
    file_path: str
    file_size: int
    started_at: str  # ISO 时间
    duration: float = 0.0
    steps: List[StepResult] = None
    error: Optional[str] = None

    def __post_init__(self):
        if self.steps is None:
            self.steps = []

    def to_dict(self):
        return {
            "success": self.success,
            "file_path": self.file_path,
            "file_size": self.file_size,
            "started_at": self.started_at,
            "duration": self.duration,
            "steps": [asdict_step(s) for s in self.steps],
            "error": self.error,
        }


def asdict_step(s: StepResult):
    return {
        "name": s.name,
        "success": s.success,
        "duration": s.duration,
        "output": s.output[:500] if s.output else "",
        "error": s.error[:500] if s.error else "",
    }


def _run(cmd: List[str], cwd: Optional[str] = None, timeout: int = 600) -> StepResult:
    """运行一条 shell 命令，记录耗时/输出/错误

    关键：把 "python" 替换为合适的 Python 解释器：
      - 如果当前 sys.executable 是 pythonw.exe（daemon 模式），不能直接用
        （pythonw.exe 无 console，跑 subprocess 会失败）
      - 用 python.exe（保证是普通 Python，能跑子进程）
      - 用 sys._MEIPASS / sys.executable 的目录（保留 venv 信息）
    """
    cmd = list(cmd)
    if cmd[0] == "python":
        # 2026-11-03：改用 _python_exe()（优先 VIRTUAL_ENV）——
        # 旧解析在部分 venv 布局下落到全局 Python312（11-04 崩溃事件实锤）
        cmd[0] = _python_exe()
    name = " ".join([os.path.basename(c) for c in cmd[:3]])
    t0 = time.time()
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            shell=False,  # 安全：用 list 不用 shell=True
            # 2026-11-03: pythonw 计划任务场景下，git/python 等控制台子进程
            # 会各弹一个黑窗（gen 更是一弹 40 分钟），统一压掉
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
        return StepResult(
            name=name,
            success=(result.returncode == 0),
            duration=time.time() - t0,
            output=(result.stdout or "")[-1000:],  # 末尾 1000 字
            error=(result.stderr or "")[-500:] if result.returncode != 0 else "",
        )
    except subprocess.TimeoutExpired:
        return StepResult(name=name, success=False, duration=time.time() - t0, error=f"超时 ({timeout}s)")
    except Exception as e:
        return StepResult(name=name, success=False, duration=time.time() - t0, error=str(e))


def _python_exe() -> str:
    """解析当前应使用的 python.exe（2026-11-03 修正）

    优先级：VIRTUAL_ENV\\Scripts\\python.exe > sys.executable 同目录 python.exe
    > sys.executable 本身。
    背景：11-04 崩溃事件显示 gen 实际跑在全局 Python312 解释器上（虽然加载了
    venv 的 numpy）——venv pythonw 的 sys.executable 在部分布局下指向 base
    解释器，导致 _run 的旧解析落到全局 python.exe，运行环境漂移不稳定。
    """
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        cand = os.path.join(venv, "Scripts", "python.exe")
        if os.path.exists(cand):
            return cand
    py_dir = os.path.dirname(sys.executable)
    cand = os.path.join(py_dir, "python.exe")
    if os.path.exists(cand):
        return cand
    return sys.executable


def run_gen(gen_script: str, cwd: str) -> StepResult:
    """跑 gen_dashboard_data.py（最多两次，原生崩溃自动重试）

    - timeout 7200s（2026-11-03 从 3600s 上调，10-28 被 60 分钟掐死教训）
    - 2026-11-03：gen 在聚合段被 numpy 原生层 0xc0000005 崩溃杀死
      （11-04 17:25 APPCRASH _multiarray_umath 实锤，10-15 的 BLAS setdefault
      修复未根治）。原生崩溃有随机性，失败后等 60s 自动重试一次；
      完整 stderr 落盘 auto_sync/data/gen_last_stderr.log（此前只留末尾 500 字
      被 openpyxl 警告噪音淹没，真实错误无法取证）。
    """
    import sys as _sys
    exe = _python_exe()
    dump_path = os.path.join(cwd, "auto_sync", "data", "gen_last_stderr.log")
    last_err = ""
    for attempt in (1, 2):
        if attempt == 2:
            time.sleep(60)
        t0 = time.time()
        try:
            r = subprocess.run(
                [exe, gen_script, "--month", "all"], cwd=cwd,
                capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=7200,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            # 完整 stderr/stdout 落盘（覆盖写，只保留最近一次）
            try:
                os.makedirs(os.path.dirname(dump_path), exist_ok=True)
                with open(dump_path, "w", encoding="utf-8", errors="replace") as f:
                    f.write(f"=== attempt {attempt} {_sys.platform} rc={r.returncode} "
                            f"{time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
                    f.write(f"--- stderr ---\n{r.stderr or ''}\n")
                    f.write(f"--- stdout 末尾 2000 字 ---\n{(r.stdout or '')[-2000:]}\n")
            except OSError:
                pass
            if r.returncode == 0:
                return StepResult(
                    name="gen_dashboard_data.py",
                    success=True,
                    duration=time.time() - t0,
                    output=(r.stdout or "")[-1000:],
                )
            last_err = f"rc={r.returncode}: {(r.stderr or '')[-300:]}"
        except subprocess.TimeoutExpired:
            last_err = f"超时 (7200s), attempt={attempt}"
        except Exception as e:
            last_err = str(e)
    return StepResult(
        name="gen_dashboard_data.py",
        success=False,
        duration=7200 * 2,
        error=last_err,
    )


def git_push_with_rebase(repo_dir: str, git_remote: str, git_branch: str) -> StepResult:
    """push（失败自动 rebase 重试一次）——2026-11-03 新增

    背景：两次互踩事故（2026-10-18 协作者直推 main 与生产机管道撞车、
    更早 E/D 双副本血案）。push 被拒（non-fast-forward）时旧逻辑直接失败，
    trigger 整体报错且无重试，数据卡到人工介入（10-18 卡了 4 小时）。
    数据文件与代码几乎不冲突，pull --rebase 后重试基本必成。
    """
    push_step = git_push(repo_dir, git_remote, git_branch)
    if push_step.success:
        return push_step
    t0 = time.time()
    rebase_step = _run(["git", "pull", "--rebase", git_remote, git_branch],
                       cwd=repo_dir, timeout=300)
    if not rebase_step.success:
        return StepResult(
            name="git_push_with_rebase",
            success=False,
            duration=time.time() - t0,
            error=f"push 失败且 rebase 也失败: push_err={push_step.error[:150]} | rebase_err={rebase_step.error[:200]}",
        )
    push_step2 = git_push(repo_dir, git_remote, git_branch)
    if push_step2.success:
        return StepResult(
            name="git_push_with_rebase",
            success=True,
            duration=time.time() - t0,
            output=f"push 被拒后 rebase 重试成功 ({rebase_step.output[:100]})",
        )
    return StepResult(
        name="git_push_with_rebase",
        success=False,
        duration=time.time() - t0,
        error=f"push 失败, rebase 后重试仍失败: {push_step2.error[:200]}",
    )


def git_add(repo_dir: str) -> StepResult:
    """git add 只跟踪必要的文件（不污染其他）

    注意：不要直接 add auto_sync/（会把 status.db 等运行时数据加进去）
    注意：raw/ 在 .gitignore 排除，加它会 git exit 1 → 整个 trigger 失败（2026-08-04 bug）
    """
    # 1) 数据文件
    # 2) 源码文件（只看 *.py，不含 data/ 子目录里的运行数据）
    # 3) 启动脚本
    return _run(
        ["git", "add",
         "dashboard_data.json", "monthly/", "targets.json",
         "gen_dashboard_data.py",
         "auto_sync/*.py", "auto_sync/__init__.py",
         "auto_sync/__main__.py", "auto_sync/examples/",
         "start_auto_sync.bat", "requirements.txt"],
        cwd=repo_dir,
    )


def git_commit(repo_dir: str, message: str) -> StepResult:
    """git commit -m {message}"""
    return _run(["git", "commit", "-m", message], cwd=repo_dir)


def git_push(repo_dir: str, remote: str, branch: str) -> StepResult:
    """git push {remote} {branch}"""
    return _run(["git", "push", remote, branch], cwd=repo_dir, timeout=300)


def git_has_changes(repo_dir: str) -> bool:
    """检查 git 是否有未 commit 的变更"""
    result = _run(["git", "status", "--porcelain"], cwd=repo_dir, timeout=30)
    return result.success and bool(result.output.strip())


def sync_html_commit(repo_dir: str, git_remote: str, git_branch: str) -> StepResult:
    """2026-08-05 新增: 数据 commit + push 后自动同步 dashboard_v5.html 的 COMMIT 字段

    流程:
      1. git rev-parse --short HEAD 拿最新 commit short hash（就是刚才 commit 的数据 commit）
      2. 替换 dashboard_v5.html 里的 `const COMMIT = "..."` 为新 hash
      3. git add + commit + push（chore commit）

    为何必要: dashboard_v5.html 里的 const COMMIT 决定前端从哪个 jsDelivr URL 拉数据
              数据 commit 后必须同步 COMMIT 字段 + 再 commit，前端刷新才能拉到新数据
              否则前端还在拉旧 COMMIT 指向的旧 data

    避免循环: chore commit 本身不修改 COMMIT 字段（下次 trigger 才改）
    """
    import re

    t0 = time.time()
    html_path = os.path.join(repo_dir, "dashboard_v5.html")
    if not os.path.exists(html_path):
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error=f"找不到 dashboard_v5.html: {html_path}",
        )

    # 1) 拿最新 commit short hash
    hash_step = _run(["git", "rev-parse", "--short", "HEAD"], cwd=repo_dir, timeout=10)
    if not hash_step.success:
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error=f"git rev-parse HEAD 失败: {hash_step.error[:200]}",
        )
    new_commit = hash_step.output.strip()
    if not re.match(r"^[a-f0-9]{7,12}$", new_commit):
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error=f"commit hash 格式异常: {new_commit!r}",
        )

    # 2) 读 dashboard_v5.html，替换 COMMIT 字段
    with open(html_path, "r", encoding="utf-8") as f:
        html = f.read()
    new_html, n = re.subn(
        r'const\s+COMMIT\s*=\s*"[a-f0-9]+"\s*;',
        f'const COMMIT = "{new_commit}";',
        html,
        count=1,
    )
    if n == 0:
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error="dashboard_v5.html 里找不到 'const COMMIT = \"...\";' 字段",
        )
    if new_html == html:
        # 已经匹配但内容相同（如已经同步过），跳过 commit
        return StepResult(
            name="sync_html_commit",
            success=True,
            duration=time.time() - t0,
            output=f"COMMIT 已是最新 ({new_commit})，跳过",
        )
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(new_html)

    # 3) git add + commit + push
    add_step = _run(["git", "add", "dashboard_v5.html"], cwd=repo_dir, timeout=30)
    if not add_step.success:
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error=f"git add dashboard_v5.html 失败: {add_step.error[:200]}",
        )
    msg = f"chore: 同步 HTML COMMIT 到 {new_commit} (auto_sync 触发)"
    commit_step = _run(["git", "commit", "-m", msg], cwd=repo_dir, timeout=30)
    if not commit_step.success:
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error=f"git commit 失败: {commit_step.error[:200]}",
        )
    # 2026-10-14 修复：push 超时 60s→300s + 失败重试一次。
    # 背景：直连 GitHub 的 SSH 握手偶发超时（10/7、10/14 早上均发生），
    # 数据 commit 的 push 有 300s 都成功了，唯独锚点这步 60s 超时；
    # 且锚点失败后次日任务走"无变更→跳过"分支不会自愈，看板会一直停在旧数据。
    # 2026-11-03 升级：git_push_with_rebase（push 被拒 → pull --rebase → 重试）
    push_step = git_push_with_rebase(repo_dir, git_remote, git_branch)
    if not push_step.success:
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error=f"git push 失败（含 rebase 重试）: {push_step.error[:200]}",
        )
    return StepResult(
        name="sync_html_commit",
        success=True,
        duration=time.time() - t0,
        output=f"chore commit {new_commit} 已 push",
    )


def execute_trigger(
    file_path: str,
    file_size: int,
    script_dir: str,
    gen_script: str,
    git_remote: str,
    git_branch: str,
    commit_message: str,
    push_enabled: bool = True,
) -> TriggerResult:
    """执行一次完整触发：gen + git add + commit + push

    Returns:
        TriggerResult 包含每个步骤的成功/失败/输出
    """
    from datetime import datetime, timezone, timedelta
    bj = timezone(timedelta(hours=8))
    started_at = datetime.now(bj).isoformat(timespec="seconds")

    t0 = time.time()
    steps = []
    overall_error = None

    # Step 1: 跑 gen_dashboard_data.py
    gen_step = run_gen(gen_script, cwd=script_dir)
    steps.append(gen_step)
    if not gen_step.success:
        return TriggerResult(
            success=False,
            file_path=file_path,
            file_size=file_size,
            started_at=started_at,
            duration=time.time() - t0,
            steps=steps,
            error=f"gen_dashboard_data.py 失败: {gen_step.error[:200]}",
        )

    # Step 2: 检查是否有变更（无变更跳过 commit）
    if not git_has_changes(script_dir):
        return TriggerResult(
            success=True,
            file_path=file_path,
            file_size=file_size,
            started_at=started_at,
            duration=time.time() - t0,
            steps=steps + [StepResult(name="git_skip_no_changes", success=True, duration=0, output="无变更")],
            error=None,
        )

    # Step 3: git add
    add_step = git_add(script_dir)
    steps.append(add_step)
    if not add_step.success:
        return TriggerResult(
            success=False,
            file_path=file_path,
            file_size=file_size,
            started_at=started_at,
            duration=time.time() - t0,
            steps=steps,
            error=f"git add 失败: {add_step.error[:200]}",
        )

    # Step 4: git commit
    commit_step = git_commit(script_dir, commit_message)
    steps.append(commit_step)
    if not commit_step.success:
        return TriggerResult(
            success=False,
            file_path=file_path,
            file_size=file_size,
            started_at=started_at,
            duration=time.time() - t0,
            steps=steps,
            error=f"git commit 失败: {commit_step.error[:200]}",
        )

    # Step 5: git push（可选，失败自动 rebase 重试）
    if push_enabled:
        push_step = git_push_with_rebase(script_dir, git_remote, git_branch)
        steps.append(push_step)
        if not push_step.success:
            return TriggerResult(
                success=False,
                file_path=file_path,
                file_size=file_size,
                started_at=started_at,
                duration=time.time() - t0,
                steps=steps,
                error=f"git push 失败（commit 已保存到本地）: {push_step.error[:200]}",
            )

    # Step 6 (2026-08-05 新增): 同步 dashboard_v5.html COMMIT 字段
    # 原因: dashboard_v5.html 内的 `const COMMIT = "..."` 决定前端从哪个 jsDelivr 路径拉数据
    #       数据 commit 后必须同步 COMMIT 字段 + 再 commit 一次，前端才能拉到新数据
    # 关键: chore commit 本身不修改 COMMIT 字段（避免循环）
    sync_step = sync_html_commit(script_dir, git_remote, git_branch)
    steps.append(sync_step)
    if not sync_step.success:
        # 非致命: 同步失败不影响 data 同步成功
        log.warning(f"sync_html_commit 失败（不影响本次 trigger 状态）: {sync_step.error[:200]}")

    return TriggerResult(
        success=True,
        file_path=file_path,
        file_size=file_size,
        started_at=started_at,
        duration=time.time() - t0,
        steps=steps,
    )