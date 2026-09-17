"""elephant token 保活与提前预警

针对 token 频繁失效（服务端有效期短、Chrome localStorage 恢复依赖有人
最近登录过浏览器）的低风险加固，不做登录自动化（风控风险，已有决策）：

1. 定期探活：token 有效时的轻量请求本身就是一次活动，若服务端是滑动
   过期，可顺带续期；即使不是滑动过期也无副作用。
2. 提前发现 + 可操作告警：失效时立刻走 Chrome localStorage 恢复；恢复
   失败才推送钉钉，告警附操作指引（"请在 Chrome 登录一次 elephant"），
   把"早上 8:30 拉数失败才发现"提前到"前一天就处理"。
3. 防刷屏：只有状态翻转（好 → 坏）才推送；恢复成功后清除标记。
"""
import time
from pathlib import Path

from .elephant_api import (
    BASE_URL,
    _is_xlsx_response,
    _read_creds,
    _refresh_creds_from_chrome,
)

NOTIFY_YAML = r'E:\Work\Documents\凭据\elephant_notify.yaml'
MARKER = Path(__file__).resolve().parent / 'data' / 'token_alert.marker'
PROBE_INTERVAL_HOURS = 4.0


def _log(msg: str):
    from .manager import log
    log.info('[token] ' + msg)


def probe() -> tuple:
    """用当前凭据发一次轻量请求，判活。

    Returns:
        (state, detail)：state ∈ 'ok' | 'NO_ACCESS' | 'net' | 'other'
    """
    import requests
    headers = _read_creds()
    url = f'{BASE_URL}?orderTime=2026-01-01+00:00:00,2026-01-01+23:59:59&page=1&size=1&derive=true'
    try:
        r = requests.get(url, headers=headers, timeout=20)
    except Exception as e:
        return 'net', f'{type(e).__name__}: {str(e)[:120]}'
    if r.status_code != 200:
        return 'other', f'HTTP {r.status_code}'
    if _is_xlsx_response(r.content, r.headers.get('Content-Type', '')):
        return 'ok', ''
    try:
        msg = str(r.json().get('msg', ''))
    except Exception:
        msg = r.content[:120]
    if msg == 'NO_ACCESS':
        return 'NO_ACCESS', 'token 已失效'
    return 'other', f'msg={msg}'


def _send_alert(detail: str) -> bool:
    try:
        from .notify import load_config_from_yaml, send
        cfg = load_config_from_yaml(NOTIFY_YAML)
        report = {
            'title': '⚠️ elephant token 失效且自动恢复失败',
            'markdown': (
                '### ⚠️ elephant token 失效\n\n'
                f'- 详情：{detail}\n'
                '- 自动恢复（Chrome localStorage）未成功\n\n'
                '**处理方式（今晚做，明早数据不断档）**：\n\n'
                '1. 在本机 Chrome 打开 elephant.xiangshangsl.com\n'
                '2. 重新登录一次（刷新页面里的 token）\n'
                '3. 无需其他操作，下一次探活会自动捡起新凭据\n'
            ),
        }
        r = send(report, cfg)
        return r.success
    except Exception as e:
        _log(f'告警发送失败: {e}')
        return False


def check_and_recover(alert: bool = True) -> tuple:
    """探活 → 失效则尝试恢复 → 仍失效且首次翻转才告警。

    Returns:
        (state, detail)
    """
    state, detail = probe()
    if state == 'ok':
        if MARKER.exists():
            MARKER.unlink()
            _log('token 已恢复有效（清除告警标记）')
        return state, detail

    if state == 'NO_ACCESS':
        _log(f'探活失效（{detail}）→ 尝试 Chrome localStorage 恢复')
        url = f'{BASE_URL}?orderTime=2026-01-01+00:00:00,2026-01-01+23:59:59&page=1&size=1&derive=true'
        if _refresh_creds_from_chrome(url, timeout=20):
            state2, detail2 = probe()
            if state2 == 'ok':
                if MARKER.exists():
                    MARKER.unlink()
                _log('token 已通过 Chrome localStorage 自动恢复')
                return 'ok', '已自动恢复'
            state, detail = state2, detail2
        else:
            detail = 'Chrome localStorage 恢复未成功（浏览器可能未登录 elephant）'
        if alert and not MARKER.exists():
            if _send_alert(detail):
                MARKER.parent.mkdir(parents=True, exist_ok=True)
                MARKER.write_text(detail, encoding='utf-8')
                _log('已推送 token 失效告警（带登录指引）')
        return state, detail

    # net / other：瞬时异常不告警，只记日志
    _log(f'探活异常（不告警）：{state} {detail}')
    return state, detail


def run_loop(interval_hours: float = PROBE_INTERVAL_HOURS):
    """daemon 内的保活循环：每 interval_hours 探活一次。"""
    _log(f'保活循环启动，间隔 {interval_hours}h')
    while True:
        try:
            check_and_recover()
        except Exception as e:
            _log(f'check_and_recover 异常: {e}')
        time.sleep(interval_hours * 3600)
