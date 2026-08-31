# auto-ticket-dashboard 项目交接文档

> **项目**: 出票自动化监控平台
> **业务方**: 机票代理公司（几十人团队）
> **接手方**: 另一个 AI 编码助手
> **最后更新**: 2026-08-30
> **当前分支**: `main`
> **当前 COMMIT**: `3093946`（dashboard_v5.html 内的 `const COMMIT` 字段）
> **Git remote**: `git@github.com:yikedashua-create/auto-ticket-dashboard.git`

---

## 1. 项目概况

### 1.1 做什么

把每天几千张机票订单的 xlsx 数据 → 自动聚合并按 4 路径 + 9 大环节拆解 → 生成可钻取 dashboard → 部署到云端（Streamlit Cloud + jsDelivr CDN）让业务员每天 9:00 看到当天自动出票的失败归因。

### 1.2 给谁用

- **业务员**（几十人）：每天看"今天哪些订单自动失败 + 失败原因" → 知道今天要救哪些单
- **业务负责人/管理层**：看月度/日度自动成功率趋势 + 4 路径占比 + 9 环节分布 → 决策哪些环节要优化
- **AI 组副组长**（开发者本人）：维护规则、加新功能

### 1.3 当前完成度

- **核心闭环完成**（85%）：
  - 数据拉取（手动 xlsx + 自动 API）✅
  - 数据生成（按月聚合 + 按日钻取）✅
  - 部署（jsDelivr + Streamlit Cloud）✅
  - 失败告警（钉钉 @所有人）✅
  - 每日日报推送（钉钉 + 飞书）✅
  - 8 大环节归因 + 4 路径分类 ✅
  - 交互钻取（族→原始→5 维度下钻）✅
- **未做（15%）**：
  - Dashboard 失败分析页"27 条"标题加备注（明确"27 条=27 条救场成功"）
  - 失败分析页加「订单最终状态」列
  - 失败根因 vs 失败分析 职责拆分
  - 自动续 token（风控风险，暂不做）
  - 评奖申报材料（README 重写 + 录屏 + 飞书多维表格）

---

## 2. 技术栈与架构

### 2.1 技术栈

| 类别 | 技术 | 版本/备注 |
|------|------|----------|
| **数据处理** | Python | 3.10+（项目用 3.12） |
| **数据处理库** | pandas | ≥2.0 |
| **Excel 读写** | openpyxl | ≥3.1 |
| **Parquet** | pyarrow | ≥10.0 |
| **HTTP** | requests | 内置 |
| **前端** | Alpine.js | v3（CDN） |
| **图表** | ECharts | v5（CDN） |
| **Web 框架** | Streamlit | 1.58.0（仅做 HTML iframe 容器） |
| **部署** | Streamlit Cloud + jsDelivr CDN | 双部署 |
| **推送** | 钉钉机器人（加签） + 飞书机器人（无加签） | 各自 webbook |
| **调度** | Windows 任务计划（schtasks） | 3 个任务 |
| **Git** | SSH key `id_ed25519` (yikedashua-create) | 配 yikedashua-create@local |

### 2.2 目录结构

```
E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard\   ← 项目根（注意嵌套）
│
├── .streamlit/                         # Streamlit 部署配置
│   └── config.toml                     # 暗色 theme + 关闭 file watcher
│
├── auto_sync/                          # 后台守护 + 数据同步（v1.0 - v2.3）
│   ├── __init__.py
│   ├── __main__.py                     # CLI 入口（start/trigger/daily-report/fetch/...）
│   ├── config.py                       # AutoSyncConfig dataclass
│   ├── manager.py                      # 守护进程主循环
│   ├── watcher.py                      # 监听新 xlsx 落盘
│   ├── trigger.py                      # gen + git add + commit + push + sync_html_commit
│   ├── notify.py                       # 钉钉/飞书/console 推送通道
│   ├── daily_report.py                 # v8 日报模板（4 路径 + 9 环节 + 案例订单号）
│   ├── elephant_api.py                 # [2026-08-27] elephant.xiangshangsl.com API 客户端
│   ├── status.py                       # 状态查询
│   ├── tests.py                        # 单元测试
│   └── examples/
│       ├── dora_workbench_integration.py
│       └── ticket_order_analyzer_integration.py
│
├── raw/                                # 不可变 parquet 副本（gitignore, 不入库）
│   └── 2026-08-28.parquet
│
├── monthly/                            # 按月聚合 json（git tracked）
│   ├── 2026-05.json                    # 4.4MB
│   ├── 2026-06.json                    # 3.5MB
│   ├── 2026-07.json                    # 4.6MB
│   └── 2026-08.json                    # 3.5MB
│
├── dashboard_data.json                 # 顶层 KB 级索引（git tracked, 19MB）
├── dashboard_v5.html                   # 主页面（git tracked, 226KB / 4977 行）
│
├── gen_dashboard_data.py               # 数据生成主脚本（126KB）★ 业务规则改这里
├── update_data.py                      # 旧版 cron 入口（基本被 auto_sync 替代）
├── app.py                              # Streamlit 入口（只渲染 HTML 框架，不注入数据）
│
├── README.md                           # 旧文档（v10.13, 2026-06-29，**严重过时**需重写）
├── AGENTS.md                           # 项目级规范（路径 / 启动方式 / 协作约定）
├── HANDOFF.md                          # ← 本文档
│
├── requirements.txt                    # 依赖清单
├── .gitignore                          # 排除 raw/ / auto_sync/data/ / 临时 _*.py
│
├── start_auto_sync.bat                 # 启动守护进程（手动）
├── stop_auto_sync.bat                  # 停止守护
├── register_startup_admin.bat          # 注册开机自启（需 admin）
│
├── _*.py / _*.log / _*.png            # 临时调试文件（gitignore）
├── 更新数据.bat                          # 桌面快捷方式用的入口（已弃用，README 里仍提到）
```

### 2.3 数据流向

```
[1] elephant.xiangshangsl.com API (v2.0+)
   或 手动 xlsx 拖到 E:\Work\Data\订单\出票总订单数据\
   ↓
[2] xlsx → parquet (auto_sync 内 sync_raw 函数，10x 压缩)
   → raw/2026-08-28.parquet
   ↓
[3] parquet → 月聚合 (gen_dashboard_data.py)
   → monthly/2026-08.json (4 路径 + 9 环节 + 5 维度下钻)
   ↓
[4] monthly/* + 元信息 → 顶层索引
   → dashboard_data.json (19MB, monthly_index + months + 当前月 summary)
   ↓
[5] git commit + push → origin main
   ↓
[6] jsDelivr CDN (https://cdn.jsdelivr.net/gh/yikedashua-create/auto-ticket-dashboard@COMMIT/)
   → dashboard_data.json (浏览器自动 gzip 拉)
   → dashboard_v5.html (const COMMIT 字段决定数据 URL)
   ↓
[7] Streamlit Cloud (auto-ticket-dashboard.streamlit.app)
   → 渲染 dashboard_v5.html (通过 iframe, 不注入数据)
   → 浏览器从 jsDelivr 拉数据
```

**关键设计**：
- dashboard_data.json 通过 `const COMMIT` 字段锁定到具体 commit，避免 jsDelivr 缓存问题
- 每次 push 后 auto_sync 自动加一个 chore commit 更新 `const COMMIT` 字段
- Streamlit Cloud 只渲染 107KB HTML 骨架，不注入 12MB+ 数据（避免 srcdoc hang）

---

## 3. 运行方式

### 3.1 安装依赖

```bash
# 系统 Python 即可（需要 3.10+）
pip install -r requirements.txt
```

依赖清单（`requirements.txt`）：
```
streamlit==1.58.0
pandas>=2.0
openpyxl>=3.1
pyarrow>=10.0
watchdog>=4.0
```

**注意**: 项目实际跑用 **`D:\pycharm3\.venv\Scripts\python.exe`**（pycharm venv，带 requests），不是系统 Python。任务计划/.bat 全部硬编码这个路径。

### 3.2 启动方式

#### 3.2.1 开发模式（手动跑）

```bash
# 1. 拉数据（替代手动下载 xlsx）
cd E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard
"D:\pycharm3\.venv\Scripts\python.exe" -m auto_sync fetch --days 1

# 2. 强制重跑 + 自动触发 gen + git + push
"D:\pycharm3\.venv\Scripts\python.exe" -m auto_sync fetch --days 7 --force --trigger

# 3. 仅触发 gen（不拉数据）
"D:\pycharm3\.venv\Scripts\python.exe" -m auto_sync trigger

# 4. 看 dashboard 本地版（开发调试用）
"D:\pycharm3\.venv\Scripts\python.exe" -m http.server 8000
# 浏览器: http://localhost:8000/dashboard_v5.html
```

#### 3.2.2 生产部署

- **Streamlit Cloud**（自动部署）：
  - 连 GitHub 仓库 `yikedashua-create/auto-ticket-dashboard`
  - main 分支 push 即重新部署
  - URL: `https://auto-ticket-dashboard.streamlit.app`（**注意**: 之前是 `xu-zhe-pool.streamlit.app`，已废弃）
  - 入口文件: `app.py`
- **jsDelivr CDN**（数据）：
  - 数据走 `https://cdn.jsdelivr.net/gh/yikedashua-create/auto-ticket-dashboard@COMMIT/dashboard_data.json`
  - COMMIT 由 `dashboard_v5.html` line 1075 `const COMMIT` 字段决定
  - auto_sync trigger.py 的 `sync_html_commit` 步骤会自动更新这个字段

### 3.3 环境配置 / 凭据

**所有凭据文件统一在 `E:\Work\Documents\凭据\`（不进 git）**：

| 文件 | 用途 | 内容示例（脱敏） |
|------|------|----------------|
| `elephant_api.yaml` | elephant API 抓 xlsx 用 | Token/Vcode/Cookie/Referer/Regiontype + 12 个其它 header（两行一组格式） |
| `elephant_notify.yaml` | fetch 失败告警推送 | channel/dingtalk_webhook/dingtalk_secret/at_mobiles/at_all/timeout_sec/retry |
| `dingtalk_notify.yaml` | 日报推送（钉钉） | 同上字段结构 |
| `feishu_notify.yaml` | （飞书）日报推送 | feishu_webhook + secret |

**注意**：
- ⚠️ 凭据文件**绝不要提交到 git**
- ⚠️ 不要把真实 token/webhook 贴到对话/issue/wiki
- ⚠️ 凭据失效时**只改本地文件**，不动代码

**elephant_api.yaml 格式特殊**：是**两行一组**（field 名为行 N，值在行 N+1）。不是标准 YAML。`auto_sync/elephant_api.py:_read_creds()` 已适配这种格式。

### 3.4 外部服务

| 服务 | 用途 | 接入方式 |
|------|------|---------|
| **elephant.xiangshangsl.com** | 拉订单 xlsx | 浏览器登录 → F12 抓 Token/Vcode/Cookie → 存 elephant_api.yaml |
| **jsDelivr CDN** | dashboard_data.json 静态托管 | GitHub 仓库（自动同步） |
| **GitHub** | 代码 + 数据仓库 | SSH key `id_ed25519`（yikedashua-create） |
| **Streamlit Cloud** | dashboard_v5.html 渲染容器 | 绑 GitHub 仓库，main 分支自动部署 |
| **钉钉机器人** | 告警 + 日报推送 | 群机器人 webbook + 加签 |
| **飞书机器人** | 备用推送 | 群机器人 webbook |
| **Windows 任务计划** | 3 个调度任务 | schtasks（见 §5.2） |

---

## 4. 已完成功能

### 4.1 数据接入层

| 功能 | 代码位置 | 说明 |
|------|---------|------|
| **手动 xlsx 检测** | `gen_dashboard_data.py:962-995` `sync_raw` | 监听 `E:\Work\Data\订单\出票总订单数据\`，新 xlsx → parquet |
| **API 自动拉 xlsx** | `auto_sync/elephant_api.py` + `auto_sync/__main__.py:cmd_fetch` | 调 elephant API，存到 DATA_DIR |
| **API 拉取告警** | `auto_sync/__main__.py:_maybe_alert` | 失败 NO_ACCESS/5xx/网络 → 钉钉 @所有人 |
| **数据分层存储** | `gen_dashboard_data.py:962-1100` | raw parquet (immutable) + monthly json (rebuildable) + 顶层索引 |

### 4.2 数据处理层

| 功能 | 代码位置 | 说明 |
|------|---------|------|
| **4 路径分类** | `gen_dashboard_data.py:classify()` line ~1056 | A 全自动成功 / B 全自动失败 / C 政策转人工 / D 处理中 |
| **第一次失败原因** | `gen_dashboard_data.py:get_root_reason()` line 309-321 | 根因归因（区别于"当前卡点"） |
| **9 大环节聚合** | `gen_dashboard_data.py:family_reason()` line 328+ | 预定/支付/取票/验真/回填/平台/系统/人工/其他 |
| **族内归一** | `gen_dashboard_data.py:family_sub_normalize()` line 1871 | "验真异常 Read timed out" → "验真异常" |
| **5 维度下钻** | `gen_dashboard_data.py:build_drilldown()` line 1930+ | 平台/航司/采购渠道/热力图/案例订单 |
| **全展开（airline 不归并）** | `gen_dashboard_data.py:1718-1722` (v10.15) | 月度/单日都全展开，不归并"其他(N个长尾)" |
| **订单分析（5 维度）** | `gen_dashboard_data.py:compute_order_analysis()` | 拆分/重复/往返/中转/多人 |

### 4.3 dashboard 前端

| 功能 | 代码位置 | 说明 |
|------|---------|------|
| **页面骨架** | `dashboard_v5.html:1-50` | Alpine.js + ECharts + 暗色主题 |
| **KPI 卡 + 4 路径** | `dashboard_v5.html:2080-2150` | hero stats + 4 路径分布饼图 |
| **航司排名（全展开）** | `dashboard_v5.html:2097-2170` `renderAirline()` | 每月 40+ 航司柱状图 |
| **航司气泡矩阵** | `dashboard_v5.html:2112-2170` | X=自动化率 / Y=单均利润 / 大小=订单量 |
| **订单分析（5 维度）** | `dashboard_v5.html:3000-3300` | 拆分/重复/往返/中转/多人 + 热力图 |
| **辅营行李订单** | `dashboard_v5.html:3880-3950` | 行李订单明细 + 平台×航司热力图 |
| **失败根因（9 环节）** | `dashboard_v5.html:3096-3330` `renderFail()` | 9 大环节族级表 + 环节汇总条 |
| **失败分析 v12** | `dashboard_v5.html:3344-3790` `renderFailureAnalysis()` | 纯失败根因，删掉流程归因（避免重复） |
| **失败钻取面板** | `dashboard_v5.html:3798-3920` `toggleDrill()` / `toggleFamilyDrill()` | 族→原始→5 维度图表 |
| **V3 自动化率预测** | `dashboard_v5.html:3600-3700` | B 路径勾选列表 + 4 数字 bump 动效 |
| **月度切换** | `dashboard_v5.html:1019-1100` | top-level month-switcher（玻璃化） |
| **失败告警 → 钉钉** | `auto_sync/notify.py:185-294` | 复用日报机器人 |

### 4.4 推送层

| 功能 | 代码位置 | 说明 |
|------|---------|------|
| **钉钉推送** | `auto_sync/notify.py:185-240` | markdown + 加签 + @手机号 |
| **飞书推送** | `auto_sync/notify.py:240-294` | 降级用纯 div + markdown 列表（自定义机器人限制） |
| **日报 v8 模板** | `auto_sync/daily_report.py` | 4 路径 + 9 环节 + 案例订单号 + 环比 |
| **日报推送入口** | `auto_sync/__main__.py:cmd_daily_report` | `python -m auto_sync daily-report --channel dingtalk` |
| **失败告警** | `auto_sync/__main__.py:_maybe_alert` | 4 类失败分类（no_access/http_5xx/network/unknown） |

### 4.5 自动化调度

| 任务 | 触发时间 | 干什么 | 任务名 |
|------|---------|--------|--------|
| 1. 开机自启 | 电脑开机 | 启动 auto_sync 守护进程 | `auto_ticket_dashboard_sync` |
| 2. 30 分钟兜底 | 每 30 分钟 | trigger 一次（补救网络/意外） | `auto_ticket_dashboard_sync_30min` |
| 3. 每日拉取 | 每天 08:30 | 调 API 拉 xlsx + gen + push | `AutoTicketFetchElephant` |
| 4. 每日日报 | 每天 09:00 | 生成日报推送到钉钉+飞书 | `AutoTicketDailyReport` |

**v2.3 时间点说明**：fetch 任务从 8:00 改到 8:30（用户保证 8:30 一定开电脑）。日报保持 9:00。

---

## 5. 未完成 / 进行中

### 5.1 待优化（小迭代，优先级 P2）

| # | 功能 | 现状 | 计划 |
|---|------|------|------|
| 1 | 失败分析页"27 条"标题加备注 | 当前显示"27 单"易误解为"27 单失败" | 加备注："含 22 单救场成功 · 5 单还在 B 路径" |
| 2 | 失败分析页加「订单最终状态」列 | 原始根因子表无"最终状态"字段 | 加一列：已出票/仍在 B/重新下单/取消等 |
| 3 | 失败根因 vs 失败分析 拆分 | 两个页职责重叠 | 失败根因=全局概览（日报用），失败分析=钻取明细 |
| 4 | README.md 重写 | 严重过时（v10.13, 2026-06-29） | 写到 v10.15 + 含 auto_sync + API 接入 + 部署流程 |
| 5 | 5 个 mockup 后续按需取用 | dashboard 已有 4 个 mockup 落地 | 1 个还没用上（页面背景/视觉风格） |

### 5.2 待评估（可能不做的）

| # | 功能 | 原因 |
|---|------|------|
| 1 | 自动续 token | 风控风险，可能触发账号锁定。**建议不做** |
| 2 | 多重备份（API 失败时回退手动 xlsx） | v2.1 告警已经覆盖，实际意义不大 |
| 3 | Vcode 算法破解 | Vcode 已经是静态（用户验证过两次一样），没必要 |

### 5.3 评奖申报（外部 KPI，不在代码内）

- 录 3 分钟演示视频
- 填飞书多维表格申报材料
- 候选评优："AI 先锋奖"

---

## 6. 已知问题 / 技术债

### 6.1 数据准确性

- **5-8 月数据严查全对**（v10.15 之前的 5-8 月 4 个月 parity vs json 全等）。0 差。
- **8/26 那 1 单多航司订单**："AQ, 9C" 在 xlsx 里是单行，dashboard 多航司订单各算 1 次（合理拆法）。总订单数差 -1 是这单的解释。

### 6.2 性能 / 体积

- `dashboard_data.json` 19.4MB（v5 字段全量），jsDelivr 限制 50MB + 20MB single file — 当前 19MB OK，但**单文件上限 20MB 是硬约束**
- 优化方向（如果接近 20MB）：
  - `monthly/*.json` 已拆分（每月 3-5MB）
  - `daily_detail` 可选拆出（最大头，每天几 MB）
  - 字段去重 / 压缩
- `gen_dashboard_data.py` 跑 4 个月 12-15 分钟，跑单月 3 分钟

### 6.3 临时 hack / 绕过

| # | 问题 | 绕过方式 | 原因 |
|---|------|---------|------|
| 1 | Streamlit 1.58 `srcdoc` 推 12MB hang | 改用 iframe + 浏览器自己从 jsDelivr 拉 | 不改 streamlit 版本（要锁版本） |
| 2 | PowerShell 5.1 GBK 编码破坏 .bat | .bat 用 GBK 保存（cmd 默认）+ `chcp 65001 >nul` | Windows 默认 cp936，改不了 |
| 3 | dashboard_data.json 接近 20MB 时 jsDelivr 慢 | monthly/ 拆 + 未来按需 lazy load | 还没到 20MB 阈值 |
| 4 | _commit_msg.txt 等临时文件散落根目录 | .gitignore 已排除，但视觉上乱 | 项目根清理 / 重写 README 时一起处理 |
| 5 | 钉钉 markdown 单换行 `\n` 忽略 | 用 `\n\n` 强制换段 | 钉钉客户端 bug |
| 6 | 飞书自定义机器人 webhook 不支持 table/collapsible | 降级用纯 div + markdown 列表 | 飞书 API 限制 |
| 7 | `is_cloudflare_challenge` 之前误判 | 加严判定（只判 title="Just a moment" / URL 含 cdn-cgi） | 见 commit history |
| 8 | dashboard_v5.html 4977 行（含 .py 在内算大） | 没拆模块，**故意**保持单文件方便部署 | 部署约束（jsDelivr 单文件） |

### 6.4 不要动的地方

| 位置 | 原因 |
|------|------|
| `dashboard_v5.html` line 1075 `const COMMIT` | 改了这个 commit 就走错路径拉数据 |
| `auto_sync/data/` 目录 | 运行时数据库（SQLite），不能入库 |
| `raw/*.parquet` | 不可变数据，append-only，gitignore |
| `E:\Work\Documents\凭据\` 全部文件 | 凭据，绝不入 git |
| `gen_dashboard_data.py:962-1100` `sync_raw` | 改了可能漏读/重读 xlsx |
| `gen_dashboard_data.py:1718-1722` (v10.15 全展开) | 用户拍板"月顶层也全展开"，**别再加归并** |
| `auto_sync/elephant_api.py:_read_creds` 解析两行一组 | elephant_api.yaml 格式已定，**别改成标准 YAML** |
| `gen_dashboard_data.py:family_sub_normalize` line 1871 | 族内归一核心，fail_reasons_B 的 `full` 字段来源 |
| `auto_sync/trigger.py:sync_html_commit` | 自动更新 `const COMMIT` 字段，不能删 |

---

## 7. 重要决策与约定

### 7.1 架构决策

| 决策 | 原因 |
|------|------|
| **数据 vs HTML 分部署**（jsDelivr 数据 + Streamlit HTML） | 避免 streamlit srcdoc 推大文件 hang |
| **分层存储**（raw/monthly/index） | 改业务规则只重算当月（3 分钟 vs 全量 15 分钟） |
| **API 返回 xlsx 不用 JSON** | elephant 后端直接给 xlsx，前端零改造（dashboard 已经吃 xlsx 格式） |
| **dashboard_v5.html 单文件不拆模块** | 部署约束，streamlit cloud 只能吃单文件入口 |
| **Vcode 静态不破解** | 32 字符长度固定，可能就是 session 标识 + md5 组合，没必要 hack |
| **告警 @所有人**（不只是 @自己） | 严重失败（token 过期）需要快速响应，所有人 @ 才能保证看到 |

### 7.2 命名 / 代码风格约定

- **函数命名**：snake_case（`build_month_data`, `sync_html_commit`）
- **常量命名**：UPPER_SNAKE（`SUCCESS_STATUSES`, `BJ_TZ`）
- **类命名**：PascalCase（`AutoSyncConfig`, `NotifyConfig`）
- **Python 路径**：硬编码 `D:\pycharm3\.venv\Scripts\python.exe`（任务计划/.bat 一致）
- **中文 vs 英文 key**：DataFrame 用中文列名，API 输出 dict 用英文字段（`auto_sync/daily_report.py` 等多处）
- **路径分隔符**：用 `\\` 或 raw string `r'...'`
- **业务族 9 环节固定**（不要改顺序）：预定 / 支付 / 取票 / 验真 / 回填 / 平台 / 系统 / 人工 / 其他
- **commit message**：
  - `feat:` 新功能
  - `fix:` 修 bug
  - `data:` auto_sync 自动同步 xlsx
  - `chore:` HTML COMMIT 同步（auto_sync 触发）
  - `vX.Y:` 版本号（业务规则改时）

### 7.3 业务规则（不要轻易改）

- **4 路径定义**：`gen_dashboard_data.py:1056-1068`，**用户拍板**：
  - A = `is_succ & (~lock_empty) & not_c`（全自动成功）
  - B = `is_succ & (~lock_empty) & not_c & (lock 有人)`（自动失败被人工救场）
  - C = `订单状态 == "留单订单"` 或 `采购类型 == "手工政策转人工"`（政策强制人工）
  - D = 兜底
- **成功状态白名单**：`SUCCESS_STATUSES = {"已出票", "TICKET_OK", "已完成", "出票完成", "ISSUE_FINISH", "VALID_TICKET_FAIL", "ticket"}` —— 注意 `VALID_TICKET_FAIL` 名字带"FAIL"但实际是"出票完成"（**用户指正过**，别改成只有正向词）
- **族规则**：`REASON_FAMILY_RULES` 数组在 `gen_dashboard_data.py` line 322+，新增 reason 时记得加映射
- **全展开**（v10.15）：月顶层 airline 数组**不归并**"其他"桶，所有航司都展示（用户拍板，避免"dashboard 数字 vs Excel 数字"对不上）

---

## 8. 数据模型 / API

### 8.1 数据模型（dashboard_data.json 结构）

```typescript
{
  "generated_at": "2026-08-30T15:43:...",     // ISO 8601
  "available_months": ["2026-05", "2026-06", "2026-07", "2026-08"],
  "current_month": "2026-08",                  // 字符串，不是数字
  "monthly_index": {                            // 每月 4-5MB json 的元信息
    "2026-05": { "size": 4377118, "orders": 86721, "last_updated": "..." },
    ...
  },
  "months": {
    "2026-08": {
      "month": "2026-08",
      "summary": { "total_orders": 42045, "A": ..., "B": ..., "C": ..., "D": ...,
                   "auto_coverage_rate": 92.83, "auto_succ_rate": 80.5, ... },
      "daily": [ { "date": "2026-08-01", "total": 2893, "A": ..., ... }, ... ],
      "airline": [ { "airline": "9C", "name": "春秋", "total": 13260, "A": ..., "B": ...,
                     "tier": "core", "is_other": false }, ... ],  // 全展开无归并
      "platform": [ ... ],                                       // 平台分布
      "channel": [ ... ],                                        // 采购渠道
      "staff": [ ... ],                                          // 员工救场
      "fail_reasons_B": [ { "reason": "..." /* 短 */, "full": "..." /* 长 */,
                            "count": 27, "family": "...", "orders": [...],
                            "prev_count": 22, "prev_month": "2026-08-04" }, ... ],
      "fail_reasons_D": [ ... ],
      "fail_families_B": [ { "family": "预定环节", "count": 492, "full_count": 510 }, ... ],
      "fail_families_D": [ ... ],
      "fail_drill_B": [ { "reason": "...", "total": 27, "rescued_count": 22,
                          "rescue_rate": 81.5, "platform_dist": [...],
                          "airline_dist": [...], "channel_dist": [...],
                          "orders": [...] }, ... ],
      "fail_drill_D": [ ... ],
      "stage_distribution": [ { "stage": "预定", "count": 492 }, ... ],
      "daily_stage": [ ... ],
      "plat_status_D": [ ... ],
      "path_profit": [ ... ],
      "insights": { "...": "..." },
      "daily_detail": {                                            // 每天完整数据
        "2026-08-15": { /* 同顶层 months 结构 */, "_period_type": "day", ... },
        ...
      }
    }
  }
}
```

### 8.2 elephant API 端点

| 端点 | 方法 | 用途 | 凭据 |
|------|------|------|------|
| `https://elephant.xiangshangsl.com/gateway/internation-ticket/order/page` | GET | 拉指定日期 xlsx | Token + Vcode + Cookie (32 字符静态) |

请求示例：
```
GET /gateway/internation-ticket/order/page?orderTime=2026-08-27+00:00:00,2026-08-27+23:59:59&page=1&size=16&derive=true
Headers:
  Token: <32 字符>
  Vcode: <32 字符>
  Cookie: token=<32 字符>
  Referer: https://elephant.xiangshangsl.com/intl/deal/InternationTicketOrder
  Regiontype: %E5%9B%BD%E9%99%85  (国际)
  Regiontype_id: 1
  User-Agent: Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) ...
```

响应：`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`（xlsx 二进制流）

### 8.3 auto_sync CLI 子命令

```bash
# 启动守护进程
python -m auto_sync start [--foreground]
python -m auto_sync daemon
python -m auto_sync stop

# 触发
python -m auto_sync trigger [--file PATH] [--no-push]
python -m auto_sync fetch [--days N | --date YYYY-MM-DD] [--force] [--trigger]

# 查询
python -m auto_sync status
python -m auto_sync history [--limit N]
python -m auto_sync reset

# 服务
python -m auto_sync serve [--host 127.0.0.1] [--port 8765]

# 推送
python -m auto_sync daily-report [--date YYYY-MM-DD] [--channel dingtalk|feishu|console]
                              [--period daily|weekly|monthly] [--config YAML] [--output JSON]
```

---

## 9. 测试与部署

### 9.1 测试

**有 `auto_sync/tests.py` 单元测试**（基础覆盖）。

```bash
python -m auto_sync.tests
```

实际验证流程（推荐）：
1. **数据准确性**：parquet vs json 双向对比（`_workbench/audit_5to8.py`，5-8 月已验证全等）
2. **API 拉取**：单日 xlsx 对比手动下载（`compare_826.py`，8/26 已验证 3811/3811 行全等）
3. **告警**：模拟 NO_ACCESS 触发钉钉推送（`test_alert.py`，4 类分类全过）
4. **.bat 编码**：PowerShell 测 ExitCode 0（`fetch_xlsx.bat` + `install_fetch_task.bat` 都 GBK 编码）

**没有正式的 E2E / 集成测试**。每次改动后人工跑：
```bash
python -m auto_sync fetch --days 1 --trigger
# 看 dashboard_data.json mtime 更新 + git log 有新 commit
```

### 9.2 部署

#### 9.2.1 Streamlit Cloud

- 入口文件: `app.py`
- 配置: `.streamlit/config.toml`（暗色 theme + 关闭 file watcher）
- 自动部署: 推 main 分支即触发
- 部署 URL: `https://auto-ticket-dashboard.streamlit.app`
- 注意: 之前是 `xu-zhe-pool.streamlit.app`，已废弃

#### 9.2.2 jsDelivr CDN（数据）

- 仓库: `yikedashua-create/auto-ticket-dashboard`
- 数据 URL: `https://cdn.jsdelivr.net/gh/yikedashua-create/auto-ticket-dashboard@COMMIT/dashboard_data.json`
- COMMIT 由 `dashboard_v5.html:1075 const COMMIT` 决定
- auto_sync 每次 trigger 后会再 commit 一次更新 COMMIT 字段（避免 jsDelivr 缓存问题）

#### 9.2.3 Windows 任务计划

3 个任务（管理员权限创建）：

| 任务名 | 触发 | 操作 |
|--------|------|------|
| `auto_ticket_dashboard_sync` | 开机 | 启动守护进程（`start_auto_sync.bat`） |
| `auto_ticket_dashboard_sync_30min` | 每 30 分钟 | 触发一次（`python -m auto_sync trigger`） |
| `AutoTicketFetchElephant` | 每天 08:30 | 调 API 拉 xlsx + trigger（`fetch_xlsx.bat`） |
| `AutoTicketDailyReport` | 每天 09:00 | 生成日报推送（`push_daily_report.bat`） |

注册脚本（均在 `E:\Work\Tools\_workbench\`）：
- `register_startup_admin.bat`（admin 权限）注册 1+2
- `install_fetch_task.bat`（admin 权限）注册 3
- `install_scheduled_task.bat`（admin 权限）注册 4

**重要**：
- `.bat` 文件**必须 GBK 编码保存**（cmd 默认 GBK，UTF-8 无 BOM 会被拆字符）
- `.bat` 头部 3 件套：`set PYTHONIOENCODING=utf-8` + `set PYTHONUTF8=1` + `chcp 65001 >nul`
- 路径用双引号包（不要用 `%PYTHON%` 变量引用）

---

## 10. 接手者建议

### 10.1 优先级排序

**P0**（最该做，1-2 周）：

1. **README.md 重写**（v10.13 严重过时）
   - 当前用户是新人或另一台机器，README 错到误导
   - 路径错（README 说桌面，实际在 E 盘）
   - 部署 URL 错（旧 xu-zhe-pool.streamlit.app）
   - 没提 auto_sync / API 接入

2. **失败分析页打磨**（业务方最近的需求）
   - "27 条"标题加备注
   - 加"订单最终状态"列
   - 失败根因 vs 失败分析 职责拆分

**P1**（重要但不急，1-2 月）：

3. **评奖申报材料**
   - 录 3 分钟演示视频
   - 填飞书多维表格
   - README 配套重写（P0 #1 完成后再做）

4. **dashboard_data.json 接近 20MB 的预案**
   - 当前 19.4MB，jsDelivr 单文件上限 20MB
   - 8 月新增数据时关注体积
   - 预案：拆 `daily_detail` 出来单独 lazy load

**P2**（锦上添花）：

5. **Vcode 算法破解**（如果 token 频繁失效，可能要破解 Vcode 自动计算）
6. **Dashboard 视觉微调**（mockup 还没用上的部分）

### 10.2 接手前必读

- 读 `gen_dashboard_data.py` line 309-321（get_root_reason）+ line 322+（REASON_FAMILY_RULES）
- 读 `auto_sync/__main__.py` 整体（CLI 入口 + cmd_fetch + _maybe_alert）
- 读 `auto_sync/elephant_api.py`（API 客户端 + 凭据读取）
- 跑一次 `python -m auto_sync fetch --days 1` 看输出，理解数据流

### 10.3 调试技巧

- **看 dashboard 不更新**：`git log --oneline -5` 看有没有新 commit；`get-content dashboard_data.json` 看 mtime
- **看 API 拉取失败**：`_workbench/_fetch_log.txt` 有详细日志
- **看告警是否推成功**：`python -c "from auto_sync.notify import *; ..."` 测通道
- **改业务规则不生效**：确认 `monthly/YYYY-MM.json` mtime 更新了（v10.13 分层存储，旧月不会自动重算）

---

## 11. Git 历史（最近 30 个 commit）

```
edc9e76 chore: 同步 HTML COMMIT 到 3093946 (auto_sync 触发)
3093946 data: 自动同步 2026-08-28.xlsx (2026-08-30T15:37:00+08:00)
ea8a2c8 chore: 同步 HTML COMMIT 到 73e6192 (auto_sync 触发)
73e6192 data: 自动同步 2026-08-28.xlsx (2026-08-30T15:07:00+08:00)
d4e9625 chore: 同步 HTML COMMIT 到 f70f9e6 (auto_sync 触发)
f70f9e6 data: 自动同步 2026-08-28.xlsx (2026-08-30T14:37:00+08:00)
feec7d7 chore: 同步 HTML COMMIT 到 3ff3b61 (auto_sync 触发)
3ff3b61 data: 自动同步 2026-08-28.xlsx (2026-08-30T14:07:00+08:00)
2fbf481 chore: 同步 HTML COMMIT 到 78cf1d0 (auto_sync 触发)
78cf1d0 data: 自动同步 2026-08-28.xlsx (2026-08-30T13:37:02+08:00)
9c17177 chore: 同步 HTML COMMIT 到 bb0461a (auto_sync 触发)
bb0461a data: 自动同步 2026-08-28.xlsx (2026-08-30T13:07:01+08:00)
655330f chore: 同步 HTML COMMIT 到 61d5ddb (auto_sync 触发)
61d5ddb data: 自动同步 2026-08-28.xlsx (2026-08-30T12:37:01+08:00)
2f1f611 chore: 同步 HTML COMMIT 到 b466d10 (auto_sync 触发)
b466d10 data: 自动同步 2026-08-28.xlsx (2026-08-30T12:07:01+08:00)
4d1bafc chore: 同步 HTML COMMIT 到 1ee5f6c (auto_sync 触发)
1ee5f6c data: 自动同步 2026-08-28.xlsx (2026-08-30T11:37:01+08:00)
1edc2cc chore: 同步 HTML COMMIT 到 c95dad8 (auto_sync 触发)
c95dad8 data: 自动同步 2026-08-28.xlsx (2026-08-30T11:07:01+08:00)
cd46137 chore: 同步 HTML COMMIT 到 ed237b4 (auto_sync 触发)
ed237b4 data: 自动同步 2026-08-28.xlsx (2026-08-30T10:37:01+08:00)
56b8661 chore: 同步 HTML COMMIT 到 84cae2a (auto_sync 触发)
84cae2a data: 自动同步 2026-08-28.xlsx (2026-08-30T10:07:01+08:00)
51901cb chore: 同步 HTML COMMIT 到 b176b96 (auto_sync 触发)
b176b96 data: 自动同步 2026-08-28.xlsx (2026-08-30T09:37:01+08:00)
b3b16e3 chore: 同步 HTML COMMIT 到 39148f1 (auto_sync 触发)
39148f1 data: 自动同步 2026-08-28.xlsx (2026-08-30T09:07:01+08:00)
ddbd0ec chore: 同步 HTML COMMIT 到 b0fcd35 (auto_sync 触发)
b0fcd35 data: 自动同步 2026-08-28.xlsx (2026-08-30T08:37:01+08:00)
```

**注意**：最近 30 个 commit 全是 `AutoTicketFetchElephant` 任务自动触发的"data + chore"双 commit 模式（每 30 分钟一次）。说明 v2.3 fetch 任务已稳定运行（2026-08-30 08:30 - 15:37，约 7 小时无故障）。

**前序重要 commit**（按时间倒推）：
```
74c9071 feat: auto_sync fetch 加失败告警 (钉钉 @所有人 token过期提醒) v2
6962bdb feat: auto_sync 接入 elephant API 自动拉 xlsx (替代手动下载) v1
... (v10.15 全展开) 87a09ee
... (v10.15 单日全展开) 5eef45b
... (HTML COMMIT 同步) 25600c7
... (数据) 70957f9 / 5a43f8e (8/26)
... 等等
```

---

## 12. 紧急联系 / 排查清单

| 症状 | 检查清单 |
|------|---------|
| **dashboard 不更新** | 1) `_workbench/_fetch_log.txt` 看日志 2) `git log -5` 看 commit 3) `dashboard_data.json` mtime |
| **API 拉不到数据** | 1) elephant 凭据是否过期（重登录拿新 token） 2) `_fetch_log.txt` 找 traceId 给后端 |
| **钉钉没收到告警** | 1) `E:\Work\Documents\凭据\elephant_notify.yaml` 还在 2) 钉钉机器人 webhook 是否被禁用 |
| **任务计划没跑** | 1) `schtasks /Query /TN "AutoTicketFetchElephant"` 看 2) 电脑是否 8:30 时在线 |
| **dashboard 显示 18 航司但 Excel 21 个** | （已修）v10.15 全展开，不会再发生 |
| **Streamlit Cloud 部署失败** | 看 `https://share.streamlit.io/yikedashua-create/auto-ticket-dashboard` 部署日志 |

---

**最后更新**: 2026-08-30 by Mavis
**整体状态**: 核心闭环 100% 跑通，每日自动运行稳定；剩余打磨 + 评奖材料。

---

## 13. 2026-08-31 变更记录（ZCode 接手后）

### 13.1 故障修复（当日）

- **数据断档修复**：8/29-8/31 三天数据缺失（根因见下），已全部回补并推送
- **根因① elephant Token 机制变更**：改为**每次登录轮换一对新 Token+Vcode**，手动从 DevTools 复制凭据注定过期——这是 8/27 起自动拉取连续失败的真正原因（不是 token "超时"）
- **根因② 计划任务丢失**：`AutoTicketFetchElephant`（每日 8:30）和开机自启任务曾消失（原因未查明），已重新注册前者
- **数据文件**：8/28 那份是 8/30 手动放入的，掩盖了故障

### 13.2 新功能（v10.16 + auto_sync v2.1/v1.2）

| 功能 | 位置 | 说明 |
|------|------|------|
| **Token 自动恢复** | `auto_sync/elephant_api.py` v2.1 | NO_ACCESS 时自动扫描 Chrome localStorage（明文 LevelDB）取当前 token/vcode，逐对验证，成功后写回凭据文件并重试请求。**浏览器保持登录 → 拉取自愈，不再需要人工抓凭据**。Chrome 路径硬编码在 `CHROME_LDB_GLOB` |
| **daily_detail 懒加载** | `gen_dashboard_data.py` Step B + `dashboard_v5.html` | 顶层 json 剥离 daily_detail：**19.8MB → 3.3MB**（jsDelivr 单文件 20MB 上限风险解除）。日/周下钻时 `ensureMonthDetail()` 从 `monthly/{ym}.json` 按需拉取（相对路径优先 + jsDelivr 兜底），失败自动降级 daily 单行聚合。`switchPeriod` 改 async + 切换竞态保护。`const COMMIT` 已提升到模块顶层（trigger.py 的正则兼容，格式勿改） |
| **watcher 降噪** | `auto_sync/watcher.py` v1.2 + `config.py` | 新配置 `ignore_events_older_than_sec`（默认 24h）：忽略 mtime 过旧的文件事件（索引器/杀软扫描噪声，曾导致以 7 分钟/个串行重处理整个历史目录）。附带修复日志双写（handler 只挂父 logger） |

### 13.3 新的注意事项

- **Token 自动恢复依赖 Chrome 登录态**：Chrome 需保持 elephant 登录（localStorage 里有当前 token）。若 Chrome 退出登录，自动恢复失效 → 回到 NO_ACCESS 告警，需人工重新登录
- **凭据文件可能被 auto_sync 自动改写**（Token/Vcode/Cookie 三行），编辑器里打开的旧副本别直接保存
- **`.gitignore` 已改为整目录排除 `auto_sync/data/`**
- **新页面体积参考**：顶层 3.3MB + monthly 每月 3.3-4.6MB，每月顶层增量约 0.7MB（原本会 +3.5MB），20MB 红线可撑约 2 年
- 本地验证方式：`python -m http.server 8000` → http://localhost:8000/dashboard_v5.html → 切月/切日，Network 面板应看到 `monthly/{ym}.json` 按需加载
