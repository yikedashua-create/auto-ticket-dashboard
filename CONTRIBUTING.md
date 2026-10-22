# 给协作者的上手指南

> 本项目是 **生产机 + 开发机** 双人协作模式。读完本文你就能开始改代码。
> 完整规范见 [`AGENTS.md`](AGENTS.md)，技术交接见 [`HANDOFF.md`](HANDOFF.md)。

---

## 🚫 铁律（违反会搞挂线上看板）

1. **绝不**在自己机器跑数据管道。以下命令在开发机上**一律禁止**：
   - `更新数据.bat`
   - `python -m auto_sync daemon` / `start` / `fetch` / `trigger`
   - 注册任何 Windows 计划任务

   **原因**：两条管道并行会抢拉数、双份生成数据、`const COMMIT` 锚点互踩。
   历史上两份副本同时 push 把线上数据卡在 9/11 长达 **5 天**，就是同类事故。
   数据管道**只由生产机（D 盘那台）独占运行**。

2. **绝不**手改数据文件。这些全是生产机自动生成提交的，你改了会被下一次自动提交覆盖，还可能引发冲突：
   - `dashboard_data.json`（主数据）
   - `monthly/*.json`（月度明细）
   - `raw/*.parquet`（按日中间数据）
   - `targets.json`（月度目标值）
   - `dashboard_v5.html` 里的 `const COMMIT = "..."`（数据锚点，约 1100 行）

3. **绝不**把凭据贴进代码、issue、PR、对话：
   - `E:\Work\Documents\凭据\` 下的 token / webhook / cookie
   - 本仓库是**公开仓库**（jsDelivr 数据链路依赖公开性），任何敏感信息进仓库 = 直接泄露。

4. **改代码走分支 + PR，不直推 `main`**。生产机会持续往 `main` 自动推数据 commit，你直推 main 容易 `non-fast-forward` 互踩。

---

## 🛠️ 环境准备

### 1. 装 git 和 Python

```bash
winget install Git.Git
# Python 3.12+，安装时勾选 "Add Python to PATH"
```

### 2. 配 SSH key（推荐，免每次输密码）

```bash
ssh-keygen -t ed25519 -C "你的邮箱@example.com"
# 一路回车，然后把 ~/.ssh/id_ed25519.pub 的内容
# 贴到 GitHub → Settings → SSH and GPG keys → New SSH key
```

### 3. clone 仓库

```bash
git clone git@github.com:yikedashua-create/auto-ticket-dashboard.git
cd auto-ticket-dashboard
```

### 4. 建独立 venv（**不要**共用生产机的 `D:\pycharm3\.venv`）

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## 👀 本地预览

```bash
.venv\Scripts\python.exe -m streamlit run app.py --server.port=8501
# 浏览器打开 http://localhost:8501
```

**注意**：本地预览时数据会从 jsDelivr CDN 拉（和生产环境一样），所以**不需要本地有 xlsx 数据文件**也能看到完整 dashboard。

---

## 🔁 改代码 → 提交流程

```bash
# 1. 拉最新（生产机会持续往 main 推数据 commit）
git checkout main && git pull

# 2. 建特性分支
git checkout -b feat/你改的功能

# 3. 改代码...

# 4. 本地验证（streamlit 跑起来看效果）

# 5. 提交（用规范前缀）
git add -A
git commit -m "feat: 简述改动"

# 6. 推分支 + 提 PR
git push -u origin feat/你改的功能
# 然后在 GitHub 网页点 "Compare & pull request"
```

### 提交前缀约定

| 前缀 | 用途 | 谁用 |
|------|------|------|
| `feat:` | 新功能 | 人工 |
| `fix:` | 修 bug | 人工 |
| `docs:` | 文档改动 | 人工 |
| `refactor:` | 重构（不改行为） | 人工 |
| `data:` | 自动同步 xlsx 数据 | **仅生产机管道** |
| `chore: 同步 HTML COMMIT` | 更新数据锚点 | **仅生产机管道** |

---

## 📚 必读文档（按顺序）

1. **本文**（铁律 + 上手流程）
2. [`AGENTS.md`](AGENTS.md)（项目位置 + 协作规范 + 业务背景 + 数据流向）
3. [`HANDOFF.md`](HANDOFF.md)（技术架构 + 数据流 + 数据模型 + 已知坑）

---

## 📊 改动入口速查

| 你要改 | 去哪里 |
|--------|--------|
| 业务规则（4 路径分类） | `gen_dashboard_data.py` 的 `classify()` 函数 |
| 失败原因归族 | `gen_dashboard_data.py` 的 `REASON_FAMILY_RULES`（line ~322） |
| 族内归一 | `gen_dashboard_data.py` 的 `family_sub_normalize()` |
| 前端页面 | `dashboard_v5.html`（**不要动** `const COMMIT` 那一行） |
| 数据结构字段含义 | `HANDOFF.md §8` |

---

## ❓ 卡住了

- `git push` 被拒（`non-fast-forward`）→ 先 `git pull --rebase origin main` 再推
- `pip install` 失败 → 检查 venv 是否激活、Python 版本是否 3.10+
- streamlit 报错 → 确认 `requirements.txt` 装齐（streamlit/pandas/openpyxl/pyarrow）
- 看数据对不上 → 数据结构和字段含义在 `HANDOFF.md §8`，别凭字段名猜

---

**最后**：你是来做开发的，不是来跑数据管道的。数据的事交给生产机，你只管代码。改之前先 `git pull`，改完走 PR，基本不会出事。
