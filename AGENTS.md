# auto-ticket-dashboard 项目

> AI / 协作者进入本目录时**必须先读本文 + 上一级 E:\Work\AGENTS.md**

## 项目位置

**项目根目录**：`E:\Work\Projects\auto-ticket-dashboard\auto-ticket-dashboard\`

⚠️ **嵌套结构说明**：
- 外层 `E:\Work\Projects\auto-ticket-dashboard\` 只有 3 个独立文件（generate_report.py / openapi.json / _v10.5_archive.zip），**不是项目根**
- 真正的项目根是**嵌套子目录** `auto-ticket-dashboard\`（含 .git）
- 历史：搬桌面项目时，外层已有同名空目录 + 文件，导致嵌套
- **本目录才是项目根**

## 关键文件

| 文件 | 用途 |
|------|------|
| `app.py` | Streamlit 入口 |
| `dashboard_v5.html` | 主页面（Alpine.js） |
| `gen_dashboard_data.py` | 数据生成（95KB） |
| `update_data.py` | 数据更新（cron 入口） |
| `dashboard_data.json` | 主数据（14MB） |
| `requirements.txt` | 依赖 |
| `.git/` | 完整 git 历史 |

## 启动方式

```bash
# 数据更新（桌面快捷方式 "更新数据.lnk"）
更新数据.bat
# 或直接：
D:\pycharm3\.venv\Scripts\python.exe update_data.py
```

```bash
# 启动 Streamlit
D:\pycharm3\.venv\Scripts\python.exe -m streamlit run app.py --server.address=0.0.0.0 --server.port=8501
```

## 数据流向

```
raw/*.xlsx (原始数据)
  → gen_dashboard_data.py
  → dashboard_data.json (14MB)
  → Streamlit 加载
  → dashboard_v5.html 渲染
```

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

**探查脚本**：`E:\Work\Tools\_workbench\_check_d_breakdown.py`（删于本次会话后）→ 重新探查用 `python -c "import sys; sys.stdout=open('_d.txt','w',encoding='utf-8'); exec(open('_check.py').read())"` 模式（避免 PS 5.1 编码崩码）

## 父规范

工作区根规范：`E:\Work\AGENTS.md`（**先读那个**）
