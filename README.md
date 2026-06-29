# 自动出票数据看板

> 每天 30 秒更新数据，无需懂任何技术。

## 🚀 新人上手（5 分钟）

### 1. 放数据文件
把今天的 xlsx 放到：
```
C:\Users\admin\Desktop\出票总订单数据\
```
文件名必须是 `YYYY-MM-DD.xlsx`（如 `2026-06-30.xlsx`）。

### 2. 跑更新
双击桌面上的 **"更新数据.bat"**。

### 3. 看结果
会弹出一个窗口：
- ✅ **更新成功** → 关闭即可，刷新 https://xu-zhe-pool.streamlit.app 看新数据
- ⚠️ **已是最新** → 没新数据，正常
- ❌ **失败** → 看错误信息，按下面"故障排查"处理

---

## 📋 日常操作清单

| 操作 | 步骤 | 耗时 |
|---|---|---|
| 每天更新数据 | 放 xlsx → 双击 bat | 30 秒 |
| 看新数据 | 刷新 https://xu-zhe-pool.streamlit.app | 0 |
| 查某天异常 | dashboard 选月份+日 → 看 fail_reasons | 0 |

---

## 🏗️ 架构说明（v10.13 分层存储）

```
桌面/出票总订单数据/*.xlsx        ← 不可变原始数据
        ↓
raw/*.parquet                       ← 不可变 parquet 副本（10x 压缩）
        ↓
monthly/YYYY-MM.json                ← 按月聚合（可重建）
        ↓
dashboard_data.json                 ← KB 级索引 + 兼容字段
        ↓
https://xu-zhe-pool.streamlit.app   ← Streamlit Cloud 自动重新部署
```

**3 层存储的好处：**
- 新增 1 天只动 2 个文件（1 parquet + 1 monthly json），**3-5 秒**完成
- 旧数据不会被覆盖（parquet mtime 校验）
- 业务规则改了只重算当月（不重读全部）

---

## 🔧 故障排查

### ❌ "Python 未安装"
**解决：** 安装 Python 3.10+，勾选 "Add Python to PATH"
- 下载：https://www.python.org/downloads/

### ❌ "pyarrow 未安装"
**解决：** 在 cmd 跑 `pip install pyarrow`

### ❌ "xlsx 源目录不存在"
**解决：** 确认 `C:\Users\admin\Desktop\出票总订单数据\` 存在
- 如果桌面文件夹名是中文，路径要完全一致
- 如果位置换了，编辑 `update_data.py` line 17 的 `DATA_DIR`

### ❌ "git status 失败" 或 "git push 失败"
**网络问题，** 按以下步骤：
1. 打开 cmd，跑 `git status` 看是否正常
2. 跑 `ping github.com` 看网络
3. 重启网络/代理
4. 重新双击 bat

**好消息：本地数据已生成，** 失败时数据在 `C:\Users\admin\Desktop\auto-ticket-dashboard\dashboard_data.json` 不丢，等网络恢复手动跑：
```cmd
cd C:\Users\admin\Desktop\auto-ticket-dashboard
git add -A
git commit -m "manual push"
git push origin main
```

### ❌ "gen_dashboard_data.py 失败"
**业务逻辑错误，** 看错误信息：
- 截图发给 [你的微信/邮箱]
- 错误信息里有 Python traceback 能定位

### ❌ 弹窗空白/无反应
**PowerShell 编码问题，** 试试：
1. 用 cmd 跑而不是 PowerShell
2. 或者直接 cmd 跑 `python update_data.py`

---

## 📁 关键文件

| 文件 | 作用 | 谁改 |
|---|---|---|
| `gen_dashboard_data.py` | 数据生成主脚本 | 业务规则改动时（族规则、清洗逻辑） |
| `update_data.py` | 一键更新入口 | 不改 |
| `dashboard_v5.html` | 前端 | UI 改动时 |
| `app.py` | Streamlit 入口 | 不改 |
| `requirements.txt` | 依赖（streamlit/pandas/openpyxl/pyarrow） | 加库时 |
| `raw/*.parquet` | 不可变数据副本 | 不改（自动生成） |
| `monthly/*.json` | 按月聚合 | 改族规则时重算 |
| `dashboard_data.json` | 顶层索引 | 自动生成 |
| `README.md` | 本文档 | 流程/排错改动时 |

---

## 🎯 业务定义（4 路径）

| 路径 | 含义 | 优先级 |
|---|---|---|
| **A 全自动成功** | 平台状态成功 + 没人接手 | 最高 |
| **B 转人工救场** | 自动失败被员工救回来 | 中 |
| **C 政策强制人工** | 手工政策转人工派单 | 绝对优先（不算自动化） |
| **D 票未出完异常** | 兜底（以上都不满足） | 最低 |

**详细规则：** 看 `gen_dashboard_data.py` 的 `classify()` 函数（line ~871）

---

## 📊 失败根因族（8 大环节 + 兜底）

| 环节 | 子类示例 |
|---|---|
| 预定失败 | 预定异常 / 亏损过大 / 未匹配规则 / 渠道账号为空 / 价格不符 / 利润过大 / 订单已完结 |
| 取票失败 | 取票异常 |
| 支付失败 | 支付异常 / 订单校验失败 |
| 验真失败 | 验真异常 / 验真失败 |
| 回填失败 | 主动回填 |
| 平台失败 | 状态监测 / 出票费审核 |
| 人工环节 | 辅营订单 / 重复订单 / 订单取消 / 补抓单转人工 |
| 系统环节 | 订单处理超时 / Token 失败 / 定时维护 / 卡余额不足 / 接口异常 |
| 其他失败 | 兜底 / 空原因 |

**详细规则：** `gen_dashboard_data.py` 的 `REASON_FAMILY_RULES`（line ~322）

---

## 🔄 日常 SOP

### 早班（你/新人）
```
08:30 检查 桌面/出票总订单数据/ 是否有昨天 xlsx
  - 有 → 双击"更新数据.bat"
  - 没有 → 问上游/查邮件/补要
```

### 看 dashboard
```
https://xu-zhe-pool.streamlit.app
  - 默认显示最近 1 天
  - 左侧切月份/日
  - 异常看"D路径异常"族（已合并到 失败根因 表）
```

### 改业务规则（你/业务方）
```
1. 打开 gen_dashboard_data.py
2. 改 REASON_FAMILY_RULES（族规则）/ SKELETON_NORMALIZE_RULES（清洗）/ clean_reason_text（特殊字符）
3. 双击"更新数据.bat" 重跑验证
4. git push 推送
```

---

## 📞 联系方式

**遇到问题先看上面的"故障排查"，** 80% 的问题能自助解决。

**剩下 20% 截图发给 [你的微信]**，附上：
1. 弹窗的完整错误信息
2. xlsx 文件名（是不是命名错了）
3. 跑的时间（哪个时间点）

---

## 📜 版本历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v10.13 | 2026-06-29 | 分层存储架构（raw parquet + monthly json + KB 索引） |
| v10.12 | 2026-06-29 | 加源文件数校验防漏读 |
| v10.11 | 2026-06-23 | 合并"预定失败"族内异常子类 |
| v10.10 | 2026-06-23 | 删除"D 路径异常"页面 |
| v10.9 | 2026-06-23 | 4 路径对比表（订单数 + 对比） |
| v10.8 | 2026-06-23 | 修复日表 fail_reasons 截断 bug |
| v10.7 | 2026-06-23 | 修复 drilldown 索引错位 |
| v10.6 | 2026-06-23 | 修复"亏损大于"占位符 bug |
| v10.5 | 2026-06-23 | 禁用族内二级归一 |
| ... | ... | ... |

---

**最后更新：2026-06-29 by Mavis**

**📌 核心目标：让任何新人 5 分钟上手 + 30 秒日常更新。**