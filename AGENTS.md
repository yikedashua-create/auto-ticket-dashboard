# auto-ticket-dashboard 项目

> AI / 协作者进入本目录时**先读本文**。
> 2026-09-16 起本项目**只在本目录（D 盘）维护**。

## 项目位置

**项目根目录（唯一主副本）**：`D:\自动出票数据分析项目\`

```bash
# 数据更新（一键）
更新数据.bat
# 或直接：
D:\pycharm3\.venv\Scripts\python.exe update_data.py
```

```bash
# 启动 Streamlit 本地预览
D:\pycharm3\.venv\Scripts\python.exe -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

⚠️ **历史遗留副本（已废弃，不要再在那里提交/推送）**：
`E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard\`
（原为嵌套结构 `E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard\`，
外层只有 generate_report.py / openapi.json / _v10.5_archive.zip 等散件。）

**血的教训（2026-09-11 ~ 09-16）**：两份副本同时对同一个 GitHub 仓库 push，
D 盘那一侧抢先推成功、占据远程历史，E 盘自此每次 push 都被
`non-fast-forward` 拒绝，线上看板数据卡在 9/11 长达 5 天。
**以后只在一处提交和推送。**

- 远程仓库：`git@github.com:yikedashua-create/auto-ticket-dashboard.git`，分支 `main`
- 线上看板：`https://auto-ticket-dashboard.streamlit.app/`

## 关键文件

| 文件 | 用途 |
|------|------|
| `app.py` | Streamlit 入口（只渲染 HTML 骨架，数据由前端自取） |
| `dashboard_v5.html` | 主页面（Alpine.js），内含 `const COMMIT` 数据锚点 |
| `gen_dashboard_data.py` | 数据生成（xlsx/parquet → dashboard_data.json） |
| `update_data.py` | 手工一键更新（gen + git commit + push） |
| `dashboard_data.json` | 主数据（约 4MB，已剥离 daily_detail） |
| `auto_sync/` | 自动同步（监控目录 / 守护进程 / 触发 / 状态库） |
| `raw/*.parquet` | 按日中间数据（gitignore，不提交） |
| `monthly/*.json` | 月度明细（提交） |
| `targets.json` | 月度目标值（提交） |
| `register_startup_admin.bat` | 注册/迁移计划任务（**需右键以管理员运行**） |
| `start_auto_sync.bat` / `stop_auto_sync.bat` | 手动启停守护进程 |
| `更新数据.bat` | 手工更新入口 |

## 数据流向

```
E:\Work\Data\订单\出票总订单数据\YYYY-MM-DD.xlsx   ← 源数据，每天 08:30 落新文件
  （v2.3 起只拉**昨天及更早**，不拉当天——8:30 时当天订单未发生完，
   当天文件只有部分数据；手动补当天用 `--today` 或 `--date`）
  → auto_sync（监控目录 + 30 分钟兜底任务）
  → gen_dashboard_data.py --month all
       ├─ raw/YYYY-MM-DD.parquet   （按日中间数据）
       ├─ monthly/YYYY-MM.json     （月度明细）
       └─ dashboard_data.json      （聚合结果）
  → git commit + push
  → Streamlit Cloud 自动重新部署
  → 前端 dashboard_v5.html 从 jsDelivr 拉数据
```

**关键坑（必须记住）**：`dashboard_v5.html` 里的

```js
const COMMIT = "xxxxxxx";   // 约 1120 行
```

是**硬编码的 commit 锚点**，前端据此拼
`https://cdn.jsdelivr.net/gh/.../auto-ticket-dashboard@${COMMIT}/dashboard_data.json`。
**数据 commit 之后必须把 COMMIT 改成新 commit 并再 commit+push**，否则前端还在拉旧数据。
`auto_sync/trigger.py` 的 `sync_html_commit()` 负责自动做这件事（在 push 成功之后才执行）。

## auto_sync 运行机制

- 守护进程：`python -m auto_sync daemon`（DETACHED_PROCESS 独立进程）
  - 监控 `E:\Work\Data\订单\出票总订单数据`
  - 状态：`python -m auto_sync status`，日志 `auto_sync/data/auto_sync.log`
- 计划任务（由 `register_startup_admin.bat` 注册，**SYSTEM 级**）：
  - `auto_ticket_dashboard_sync`：开机自启 daemon
  - `auto_ticket_dashboard_sync_fetch`：每日 08:35 主拉数 `fetch --days 2 --trigger`（2026-09-24 新增）
  - `auto_ticket_dashboard_sync_30min`：每 30 分钟兜底 `fetch --yesterday`（存在即跳过、不 force；
    新文件落地由 daemon watcher 触发 gen，避免空跑）
  - ⚠️ **历史教训（2026-09-17~09-24 断更根因）**：9/16 迁移 D 盘时 30 分钟任务被注册成裸 `trigger`
    （从不 fetch），watcher 等不到新文件 → 数据停在 9/16；9/22 重装电脑又把任务/凭据/Chrome 全清了。
    任何重新注册都必须包含 fetch 路径。
- 停止守护进程需要**管理员权限**（任务以 SYSTEM 身份运行）：
  用 `stop_auto_sync.bat`（右键以管理员运行），并先 `schtasks /Delete` 掉任务，否则下次开机又起来。
- 凭据文件：`E:\Work\Documents\凭据\elephant_api.yaml`（token 失效时 daemon 会自动恢复并写回）
- **token 保活（2026-09-17 加）**：daemon 内置每 4h 探活线程（`auto_sync/token_keepalive.py`），
  失效→自动走 Chrome localStorage 恢复→仍失败才推钉钉告警（附"在 Chrome 登录一次 elephant"指引，
  状态翻转才推一次防刷屏）。手动检查：`python -m auto_sync token-check`。

**2026-09-24 重装恢复记录**：C/E 盘被重装清空（计划任务、git、SSH 密钥、Chrome profile、
E 盘全部历史 xlsx 和凭据 yaml 全丢；D 盘项目完好但 `D:\pycharm3` venv 没了）。
恢复动作：重建 venv、winget 装 git、重写 elephant_api.yaml 骨架（header 清单见 HANDOFF.md §8.2）、
生成新 SSH 密钥（用户加到 GitHub 后 push 生效）、本地 reset 到线上 afc65ae（线上比本地新，
b256965 已含 9/21 数据）。git 全局代理指向 127.0.0.1:10090 但代理客户端未重装，
本仓库已设 repo 级 `http.proxy=""` 直连。**补数前不要跑 更新数据.bat**——raw 只到 9/16，
直接 gen 会把线上 9/17-9/21 数据冲掉，必须先 `fetch --days 8` 补齐 xlsx。

**已知待改进点**：`manager.trigger_now()` 取监控目录里 **mtime 最新** 的 xlsx，
但"当天文件"常比"前一天的重导出文件"mtime 早几秒，导致 30 分钟兜底任务反复重跑前一天的文件
（每次白烧约 7.5 分钟 CPU）。建议改为"按未处理过的文件"驱动。

## 业务背景

- 4 路径 KPI: A=全自动成功 / B=自动失败被人工救场 / C=政策强制人工 / D=票未出完异常
- 失败环节分类 v10: 8 大环节（人工/预定/支付/取票/验真/回填/平台/系统/其他）
- 关键平台: 携程/飞猪/同程/去哪儿/航旅纵横/航司直连/航班管家/春秋

## 调试/临时文件

- 临时调试脚本、debug 截图、log → **`E:\Work\Tools\_workbench\`**（7 天清）
- **不要**在项目根目录建 test-*.py / debug-*.py / verify-*.py

## D 路径数据局限（2026-07-20 用户提出）

**核心问题**：原始数据是**按日分文件**的快照（`2026-07-15.xlsx` 等）。**同一订单生命周期跨几天**，会在多个文件出现多次、每次归类可能不同（例：7-15 是 D 处理中，7-17 变 A 已出票）。当前 classify() 是**逐行判定**，**不去重**，所以 4 路径统计含历史快照，不是独立订单数。

**D 路径 30 天拆解（81,027 单）**：

| 子分类 | 数量 | 占比 | 含义 | 当前归 D |
|---|---|---|---|---|
| D1 留单订单 | 495 | 26.7% | `订单状态.1 == "留单订单"`，系统还在跑 | ✅ |
| D2 自动失败+未处理 | **0** | 0% | 非留单+未锁定+有失败原因（实际为 0，说明系统失败后都已被人处理） | ✅ |
| D3 其他未处理 | 16 | 0.9% | 非留单+未锁定+无失败原因（特殊情况：拒单/已作废） | ✅ |
| D4 系统已跑+人已锁 | **1344** | 72.5% | 非留单+已锁定（**含同订单历史快照**） | ✅ |

**「自动化覆盖率」算法对比**：
- 旧 `(A+B)/Total` = **90.87%**
- 提议 `(A+B+D4)/Total` = **92.53%**（+1.66pp）
- **但 D4 1344 单含同订单早期快照**，去重后真实数字会下降

**用户决策（2026-07-20）**：**暂时不调整** D 路径覆盖率算法——数据局限性（按日快照不去重）没解决前，+1.66pp 的数字不靠谱。用户还在想怎么办。

**潜在方案**（待用户拍板）：
- A. **去重治本**：按订单号 group，取每单最新日期快照，重算 4 路径 → 数字会回落到更真实水平
- B. **治标不动 KPI**：D 路径子分类里标注"含同订单历史快照"，加文案说明
- C. **结构性改造**：新增第 5 路径"X - 人工处理中"（被锁定+订单未完结），D 只剩真烂尾

**探查脚本**：`E:\Work\Tools\_workbench\_check_d_breakdown.py`（已删）→ 重新探查用 `python -c "import sys; sys.stdout=open('_d.txt','w',encoding='utf-8'); exec(open('_check.py').read())"` 模式（避免 PS 5.1 编码崩码）

## 环境约定

- Python 一律用 venv：`D:\pycharm3\.venv\Scripts\python.exe`
  （裸 `python` 依赖 PATH，可能缺 pyarrow / watchdog）
- git push 被拒时先 `git fetch` 看清 `ahead/behind`，**不要直接 force push**

## 父规范

工作区根规范：`E:\Work\AGENTS.md`（如存在，可参考）
