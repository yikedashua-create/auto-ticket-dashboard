# 部署说明（DEPLOYMENT）

> 看完这篇你就知道：协作者 push 了代码，线上看板要怎么更新。
> **答案：什么都不用做，自动部署。**

---

## 一、部署是全自动的

线上看板 `https://auto-ticket-dashboard.streamlit.app/` 跑在 **Streamlit Community Cloud** 上，工作方式：

```
协作者 push 代码 → GitHub 仓库 main 分支更新
                  ↓ （Streamlit Cloud 监听 main 分支）
        Streamlit Cloud 自动拉新代码 → 重新部署
                  ↓
        线上看板刷新即看到新版本
```

**触发条件**：任何指向 `main` 分支的 push（无论是 owner、协作者直推，还是 PR 合并）都会触发重新部署。

**所以**：协作者把代码合并到 main 后，等 1-3 分钟 Streamlit Cloud 完成重新部署，刷新看板就能看到新版本。你不用做任何操作。

---

## 二、代码改动 vs 数据改动（容易混淆的点）

线上看板由**两部分**组成，更新机制不同：

| 部分 | 内容 | 怎么更新线上 |
|------|------|-------------|
| **HTML 骨架** | `dashboard_v5.html` + `app.py` | push main → Streamlit Cloud 自动重新部署 |
| **数据** | `dashboard_data.json` + `monthly/*.json` | 前端从 jsDelivr CDN 拉，由 `const COMMIT` 锚点决定版本 |

### 场景对照

| 协作者改了 | push main 后线上会怎样 |
|-----------|----------------------|
| 前端代码（`dashboard_v5.html`） | ✅ 自动重新部署，刷新看到新代码 |
| Streamlit 入口（`app.py`） | ✅ 自动重新部署 |
| 业务规则代码（`gen_dashboard_data.py`） | ⚠️ app 重新部署了，**但线上数据不会变**——线上数据是生产机跑管道 gen + push + 更新 `const COMMIT` 后 jsDelivr 那份。要等生产机下次跑管道才生效 |
| 文档（`.md`） | ✅ 重新部署（但不影响展示） |
| 数据文件（`dashboard_data.json` 等） | ❌ **协作者不应碰**——由生产机独占生成提交 |

---

## 三、怎么验证部署成功

1. **看线上看板**：打开 `https://auto-ticket-dashboard.streamlit.app/`，刷新看页面是否正常加载
2. **看部署日志**：访问 `https://share.streamlit.io/`（需要 GitHub 登录）→ 找到 `auto-ticket-dashboard` 应用 → 看 "Latest app activity"
   - 绿色 ✅ = 部署成功
   - 红色 ❌ = 部署失败，点进去看错误日志
3. **看数据新鲜度**：看板的"生成时间"和最新数据日期对了就说明链路通

---

## 四、什么时候需要手动干预

### 部署失败（红色 ❌）
常见原因 + 处理：
- **依赖装不上** → 检查 `requirements.txt` 是否漏库或版本冲突
- **app.py 启动报错** → 看日志，一般是代码 bug，修了重新 push
- **超时** → Streamlit Cloud 免费版有冷启动，重试一次

### 线上看板白屏 / 数据加载不出
- 先确认 `dashboard_v5.html` 里的 `const COMMIT` 指向的 commit 在 GitHub 上真实存在
- 用 `https://cdn.jsdelivr.net/gh/yikedashua-create/auto-ticket-dashboard@<COMMIT>/dashboard_data.json` 直接访问，能下载说明数据链路 OK
- 99% 的"数据卡旧"问题都是 `const COMMIT` 锚点没更新（生产机 `auto_sync/trigger.py` 的 `sync_html_commit()` 负责自动更新）

---

## 五、怎么手动触发重新部署

如果协作者改了代码但 Streamlit Cloud 没自动触发（极少见），手动强制：

```bash
cd D:/自动出票数据分析项目
git commit --allow-empty -m "chore: trigger redeploy"
git push origin main
```

或者在 Streamlit Cloud 管理页 `https://share.streamlit.io/` 找到应用，点 **"Reboot app"** 重启实例。

---

## 六、协作者注意事项

1. **只改代码，不碰数据**：`dashboard_data.json` / `monthly/*.json` / `raw/` / `targets.json` / `const COMMIT` 一律不动
2. **不跑数据管道**：开发机绝不开 `auto_sync` / `更新数据.bat`
3. **走分支 + PR**：不要直推 main，避免和生产机自动 commit 互踩（详见 `CONTRIBUTING.md`）
4. **改完 `gen_dashboard_data.py` 后**：push 代码 → 提 PR → 合并 → **通知生产机跑一次数据管道**（否则线上数据还是旧的）

---

## 七、部署架构图

```
GitHub 仓库 main 分支
       │
       ├──→ Streamlit Cloud（渲染 HTML 骨架 + app.py）
       │       auto-ticket-dashboard.streamlit.app
       │
       └──→ jsDelivr CDN（托管数据文件）
               cdn.jsdelivr.net/gh/.../auto-ticket-dashboard@<COMMIT>/
                  ├── dashboard_data.json
                  ├── monthly/*.json
                  └── targets.json
       
       浏览器打开看板 → Streamlit 发 HTML 骨架 → 浏览器再从 jsDelivr 拉数据
```

**为什么这样拆**：Streamlit Cloud 通过 WebSocket 推大文件会 hang（实测推 12MB 数据直接卡死），所以拆成"Streamlit 只发 107KB HTML 骨架 + 浏览器自己从 jsDelivr 拉数据"。

---

## 八、关键配置文件

| 文件 | 作用 | 谁改 |
|------|------|------|
| `.streamlit/config.toml` | Streamlit 暗色主题 + 关 file watcher | 改主题时 |
| `app.py` | Streamlit 入口（渲染 HTML + CSS 注入） | 改布局约束时 |
| `dashboard_v5.html` line ~1120 `const COMMIT` | 数据锚点 | **只由 auto_sync 自动改，人不要动** |

---

**最后更新**：2026-10-17
**部署状态**：Streamlit Cloud 自动部署运行中，main 分支即线上即最新