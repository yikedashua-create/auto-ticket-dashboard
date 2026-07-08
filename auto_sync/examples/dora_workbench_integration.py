"""
Dora 工作台集成示例

Dora 工作台未来形态（参考姜Dora在此）：
  - 任务卡片式 UI
  - Dora AI chat
  - 时间账本
  - Skills 库（358 个 Skill）

auto_sync 作为 Dora 的一个 Skill：
  - 注册到 Skills 库
  - 在 Dora AI chat 里可以触发（"Dora，把今天的 xlsx 同步一下"）
  - 在任务卡片上显示状态（运行中/已停止 + 上次同步时间）
  - 在时间账本里记录"今天花了 X 分钟同步 dashboard"

具体接入方式（3 种）：

【方案 A】HTTP API 调用（最简单）
  Dora 后端用 HTTP 调用 auto_sync 暴露的 API：

    # 启动 auto_sync API server（一次性，独立进程）
    # python -m auto_sync serve --port 8765

    # Dora 后端代码
    import requests
    r = requests.get("http://127.0.0.1:8765/status")
    status = r.json()

    r = requests.post("http://127.0.0.1:8765/trigger")
    result = r.json()

【方案 B】直接 import（最深度）
  Dora 后端是 Python（FastAPI + SQLite），可以直接 import：

    from auto_sync import AutoSyncManager
    mgr = AutoSyncManager()
    mgr.start_background()  # 启动后台监控

    # 提供 API endpoint
    @app.get("/skills/auto_sync/status")
    def skill_status():
        return mgr.to_workbench_dict()

    @app.post("/skills/auto_sync/trigger")
    def skill_trigger():
        result = mgr.trigger_now()
        return result.to_dict()

【方案 C】Skill 标准化注册（待 Dora 平台支持）
  等 Dora 工作台有正式的 Skill 注册机制时，把 auto_sync 包成标准 Skill：
    - manifest.yaml（Skill 元数据）
    - 入口函数（trigger / status / history）
    - 配置（默认参数）

下面是【方案 B】完整示例代码：
"""
from fastapi import FastAPI
from auto_sync import AutoSyncManager

app = FastAPI(title="Dora 工作台集成示例")
mgr = AutoSyncManager()


@app.on_event("startup")
async def startup():
    """Dora 启动时拉起 auto_sync 后台监控"""
    mgr.start_background()
    print("✅ auto_sync 后台监控已启动")


@app.on_event("shutdown")
async def shutdown():
    """Dora 关闭时停掉 auto_sync"""
    mgr.stop()


# ========== Skill API: auto_sync ==========

@app.get("/api/skills/auto_sync/status")
def skill_status():
    """Dora 任务卡片调用：显示当前状态"""
    return mgr.to_workbench_dict()


@app.post("/api/skills/auto_sync/trigger")
def skill_trigger(file_path: str = None):
    """Dora AI chat 调用：手动触发同步"""
    result = mgr.trigger_now(file_path=file_path)
    return result.to_dict()


@app.get("/api/skills/auto_sync/history")
def skill_history(limit: int = 20):
    """Dora 时间账本调用：历史同步记录"""
    return [h.to_dict() for h in mgr.get_history(limit=limit)]


# ========== Dora AI chat 自然语言接口示例 ==========
# 在 Dora AI chat 里，用户说：
#   "帮我同步一下今天的 xlsx"
#   "查看最近 5 次同步状态"
# Dora AI 后端调用 skill_trigger / skill_history，然后格式化回复给用户

# ========== 时间账本自动记录示例 ==========
# auto_sync 每次触发后，可选写入时间账本：
# 时间账本 schema：
#   timestamp | skill | duration_seconds | result | details
#
# 实现方式：
#   1. 给 AutoSyncManager 传 on_complete 回调
#   2. 回调里写时间账本数据库
#
# 示例代码：
def on_complete_log_to_dora_timebook(result):
    """auto_sync 完成后写入 Dora 时间账本"""
    import sqlite3
    from datetime import datetime, timezone, timedelta

    db = sqlite3.connect(r"C:\Users\admin\Desktop\Dora\timebook.db")  # Dora 时间账本 DB
    bj = timezone(timedelta(hours=8))
    db.execute("""
        INSERT INTO timebook (timestamp, skill, duration_seconds, result, details)
        VALUES (?, ?, ?, ?, ?)
    """, (
        datetime.now(bj).isoformat(timespec="seconds"),
        "auto_sync_xlsx",
        result.duration,
        "success" if result.success else "failed",
        str(result.to_dict()),
    ))
    db.commit()
    db.close()


# 启动时绑定回调：
# mgr = AutoSyncManager(on_complete=on_complete_log_to_dora_timebook)