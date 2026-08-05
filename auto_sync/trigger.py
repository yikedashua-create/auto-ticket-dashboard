"""auto_sync 触发器模块

触发后做什么：
  1. 跑 gen_dashboard_data.py 生成新 dashboard_data.json
  2. git add + commit
  3. git push 到 GitHub（streamlit cloud 自动重新部署）

设计：每个步骤独立函数，可单独调用（方便测试和扩展）。
"""
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional, List


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
        # 取 sys.executable 所在目录的 python.exe（不是 pythonw.exe）
        py_dir = os.path.dirname(sys.executable)
        candidate = os.path.join(py_dir, "python.exe")
        if os.path.exists(candidate):
            cmd[0] = candidate
        else:
            # fallback：用 sys.executable 本身（venv 没 python.exe 时）
            cmd[0] = sys.executable
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


def run_gen(gen_script: str, cwd: str) -> StepResult:
    """跑 gen_dashboard_data.py"""
    return _run(["python", gen_script, "--month", "all"], cwd=cwd, timeout=900)


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
         "dashboard_data.json", "monthly/",
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
    push_step = _run(["git", "push", git_remote, git_branch], cwd=repo_dir, timeout=60)
    if not push_step.success:
        return StepResult(
            name="sync_html_commit",
            success=False,
            duration=time.time() - t0,
            error=f"git push 失败: {push_step.error[:200]}",
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

    # Step 5: git push（可选）
    if push_enabled:
        push_step = git_push(script_dir, git_remote, git_branch)
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