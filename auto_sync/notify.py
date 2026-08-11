# -*- coding: utf-8 -*-
"""
notify.py — 钉钉/飞书/控制台 推送通道

设计原则：
  1. 三种 channel 抽象成同一接口 send(report, config) -> SendResult
  2. dingtalk / feishu / console 三个实现，调用方根据 config 选
  3. 报告 payload 由 caller 构造（一般来自 daily_report.py），本模块只负责渲染 + 发送
  4. 测试模式：console channel 永远不抛异常，便于本地调试

钉钉机器人（自定义 Webhook）：
  - 5 分钟接入，开群 → 群设置 → 智能群助手 → 添加机器人 → 自定义
  - 安全模式：加签名（SEC 加签），用 timestamp + sign 拼到 URL
  - 消息类型：text / markdown / link / actionCard / feedCard
  - 文档：https://open.dingtalk.com/document/orgapp/custom-robot-access

飞书机器人（自定义 Webhook）：
  - 群设置 → 群机器人 → 添加机器人 → 自定义机器人
  - 消息类型：text / post / interactive（消息卡片）
  - 文档：https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
"""
import json
import logging
import time
import hmac
import hashlib
import base64
import urllib.parse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# 2026-08-11: PowerShell 5.1 + 中文 Windows 默认 GBK 编码
# 控制台 print emoji 触发 UnicodeEncodeError
# 强制 stdout utf-8
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logger = logging.getLogger(__name__)


@dataclass
class NotifyConfig:
    """推送配置（由 YAML 加载或命令行传入）"""
    # 通道选择
    channel: str = "console"  # console / dingtalk / feishu

    # 钉钉
    dingtalk_webhook: str = ""
    dingtalk_secret: str = ""  # 安全模式的加签密钥（空 = 不加签）

    # 飞书
    feishu_webhook: str = ""
    feishu_secret: str = ""

    # @ 人
    at_mobiles: List[str] = field(default_factory=list)  # 手机号
    at_userids: List[str] = field(default_factory=list)   # 工号
    at_all: bool = False  # @所有人（仅紧急用）

    # 通用
    timeout_sec: float = 10.0
    retry: int = 2  # 失败重试次数


@dataclass
class SendResult:
    """推送结果"""
    success: bool
    channel: str
    error: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0


def _dingtalk_sign(secret: str) -> tuple:
    """钉钉加签：返回 (timestamp, sign)"""
    timestamp = str(round(time.time() * 1000))
    secret_enc = secret.encode("utf-8")
    string_to_sign = f"{timestamp}\n{secret}"
    string_to_sign_enc = string_to_sign.encode("utf-8")
    hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    return timestamp, sign


def render_dingtalk_markdown(title: str, markdown_text: str, at: NotifyConfig) -> Dict:
    """渲染成钉钉 markdown 消息体"""
    body = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": markdown_text,
        },
        "at": {
            "atMobiles": at.at_mobiles,
            "atUserIds": at.at_userids,
            "isAtAll": at.at_all,
        },
    }
    return body


def render_dingtalk_actioncard(title: str, markdown_text: str, at: NotifyConfig,
                                single_title: str = "查看详情",
                                single_url: str = "") -> Dict:
    """渲染成钉钉 ActionCard 消息体（带跳转链接的卡片）"""
    body = {
        "msgtype": "actionCard",
        "actionCard": {
            "title": title,
            "text": markdown_text,
            "singleTitle": single_title,
            "singleURL": single_url,
        },
        "at": {
            "atMobiles": at.at_mobiles,
            "atUserIds": at.at_userids,
            "isAtAll": at.at_all,
        },
    }
    return body


def render_feishu_interactive(card: Dict, at: NotifyConfig) -> Dict:
    """渲染成飞书 interactive 消息卡片

    card 结构（由 caller 构造）：
      {
        "header": {"title": {"tag": "plain_text", "content": "..."}},
        "elements": [
          {"tag": "div", "text": {"tag": "lark_md", "content": "..."}},
          ...
        ]
      }
    """
    body = {
        "msg_type": "interactive",
        "card": card,
    }
    if at.at_all:
        body["chat_id"] = ""  # @所有人需要 chat_id（暂留空，由调用方补）
    return body


def send_console(report: Dict, cfg: NotifyConfig) -> SendResult:
    """控制台模式：打印 markdown 渲染结果 + JSON payload 到 stdout"""
    t0 = time.time()
    print("\n" + "=" * 70)
    print(f"[CONSOLE MODE] 推送内容预览")
    print("=" * 70)

    title = report.get("title", "失败订单归因分析日报")
    md = report.get("markdown", "")
    print(f"\n>>> 标题: {title}\n")
    print(md)
    print()

    if report.get("dingtalk_card"):
        print(">>> 钉钉消息体 (actionCard):")
        print(json.dumps(report["dingtalk_card"], ensure_ascii=False, indent=2))
        print()

    if report.get("feishu_card"):
        print(">>> 飞书消息体 (interactive card):")
        print(json.dumps(report["feishu_card"], ensure_ascii=False, indent=2))
        print()

    print("=" * 70)
    print(f"[CONSOLE] 仅打印，不真实发送（不依赖 webhook）")
    print("=" * 70 + "\n")

    return SendResult(
        success=True,
        channel="console",
        raw={"mode": "console", "title": title},
        duration_ms=int((time.time() - t0) * 1000),
    )


def send_dingtalk(report: Dict, cfg: NotifyConfig) -> SendResult:
    """钉钉模式：POST 到自定义 webhook"""
    import requests

    t0 = time.time()
    if not cfg.dingtalk_webhook:
        return SendResult(success=False, channel="dingtalk", error="webhook 未配置")

    # 构造消息体
    title = report.get("title", "失败订单归因分析日报")
    md = report.get("markdown", "")
    action_url = report.get("action_url", "")
    if action_url:
        body = render_dingtalk_actioncard(title, md, cfg, single_title="查看 Dashboard", single_url=action_url)
    else:
        body = render_dingtalk_markdown(title, md, cfg)

    # 加签
    url = cfg.dingtalk_webhook
    if cfg.dingtalk_secret:
        ts, sign = _dingtalk_sign(cfg.dingtalk_secret)
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}timestamp={ts}&sign={sign}"

    # POST（带重试）
    last_err = ""
    for attempt in range(cfg.retry + 1):
        try:
            resp = requests.post(
                url,
                json=body,
                timeout=cfg.timeout_sec,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            data = resp.json() if resp.text else {}
            if resp.status_code == 200 and data.get("errcode", 0) == 0:
                return SendResult(
                    success=True,
                    channel="dingtalk",
                    raw=data,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            last_err = f"HTTP {resp.status_code}: {data}"
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)

    return SendResult(
        success=False,
        channel="dingtalk",
        error=last_err,
        duration_ms=int((time.time() - t0) * 1000),
    )


def send_feishu(report: Dict, cfg: NotifyConfig) -> SendResult:
    """飞书模式：POST 到自定义 webhook"""
    import requests

    t0 = time.time()
    if not cfg.feishu_webhook:
        return SendResult(success=False, channel="feishu", error="webhook 未配置")

    card = report.get("feishu_card")
    if not card:
        return SendResult(success=False, channel="feishu", error="报告未含 feishu_card")
    body = render_feishu_interactive(card, cfg)

    # 加签（飞书用 HMAC-SHA256 + timestamp）
    url = cfg.feishu_webhook
    if cfg.feishu_secret:
        ts = str(int(time.time()))
        string_to_sign = f"{ts}\n{cfg.feishu_secret}"
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        b64 = base64.b64encode(hmac_code).decode("utf-8")
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}timestamp={ts}&sign={b64}"

    last_err = ""
    for attempt in range(cfg.retry + 1):
        try:
            resp = requests.post(
                url,
                json=body,
                timeout=cfg.timeout_sec,
                headers={"Content-Type": "application/json; charset=utf-8"},
            )
            data = resp.json() if resp.text else {}
            # 飞书 Status: "success" / {"code": 0, "msg": "success"}
            if resp.status_code == 200 and (data.get("StatusCode") == 0 or data.get("code") == 0 or data.get("Status") == "success"):
                return SendResult(
                    success=True,
                    channel="feishu",
                    raw=data,
                    duration_ms=int((time.time() - t0) * 1000),
                )
            last_err = f"HTTP {resp.status_code}: {data}"
        except Exception as e:
            last_err = str(e)
        time.sleep(0.5)

    return SendResult(
        success=False,
        channel="feishu",
        error=last_err,
        duration_ms=int((time.time() - t0) * 1000),
    )


def send(report: Dict, cfg: NotifyConfig) -> SendResult:
    """统一入口：根据 cfg.channel 选 channel"""
    ch = cfg.channel.lower()
    if ch == "console":
        return send_console(report, cfg)
    elif ch == "dingtalk":
        return send_dingtalk(report, cfg)
    elif ch == "feishu":
        return send_feishu(report, cfg)
    else:
        return SendResult(success=False, channel=ch, error=f"未知 channel: {ch}")


def load_config_from_yaml(path: Union[str, Path]) -> NotifyConfig:
    """从 YAML 加载推送配置（简化版，不依赖 pyyaml）"""
    p = Path(path)
    if not p.exists():
        logger.warning(f"配置文件不存在: {p}，用默认 console 模式")
        return NotifyConfig()

    # 极简 YAML parser（key: value 形式，# 注释）
    cfg = NotifyConfig()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key == "channel":
            cfg.channel = val
        elif key == "dingtalk_webhook":
            cfg.dingtalk_webhook = val
        elif key == "dingtalk_secret":
            cfg.dingtalk_secret = val
        elif key == "feishu_webhook":
            cfg.feishu_webhook = val
        elif key == "feishu_secret":
            cfg.feishu_secret = val
        elif key == "at_all":
            cfg.at_all = val.lower() in ("true", "1", "yes")
        elif key == "at_mobiles":
            cfg.at_mobiles = [x.strip() for x in val.split(",") if x.strip()]
        elif key == "at_userids":
            cfg.at_userids = [x.strip() for x in val.split(",") if x.strip()]
        elif key == "timeout_sec":
            cfg.timeout_sec = float(val)
        elif key == "retry":
            cfg.retry = int(val)
    return cfg
