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

    关键：把 "python" 替换为 sys.executable（避免 subprocess 找到系统 Python 而不是当前 venv）
    """
    cmd = list(cmd)  # 拷贝，避免修改原 list
    if cmd[0] == "python":
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
    """
    # 1) 数据文件
    # 2) 源码文件（只看 *.py，不含 data/ 子目录里的运行数据）
    # 3) 启动脚本
    return _run(
        ["git", "add",
         "dashboard_data.json", "monthly/", "raw/",
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

    return TriggerResult(
        success=True,
        file_path=file_path,
        file_size=file_size,
        started_at=started_at,
        duration=time.time() - t0,
        steps=steps,
    )