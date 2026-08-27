# -*- coding: utf-8 -*-
"""
elephant.xiangshangsl.com API 客户端（v1，2026-08-27）

- 拉取指定日期的 xlsx 文件
- 存到 E:\\Work\\Data\\订单\\出票总订单数据\\2026-XX-XX.xlsx
- Token / Vcode / Cookie 从 E:\\Work\\Documents\\凭据\\elephant_api.yaml 读

后续扩展点：
- token 过期告警（NO_ACCESS 时推送钉钉/飞书）
- 自动续 token（不推荐 - 风控风险）
- 分页（当前 size=16 但实测返回 1 页 = 1 天的全部订单 ~4000 行，不需要翻页）
"""
import re
import os
import sys
import time
import logging
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict

import requests

# 强制 stdout UTF-8 (避免 Windows PowerShell GBK 编码报错)
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

CRED_PATH = r'E:\Work\Documents\凭据\elephant_api.yaml'
DATA_DIR = r'E:\Work\Data\订单\出票总订单数据'
BASE_URL = 'https://elephant.xiangshangsl.com/gateway/internation-ticket/order/page'

BJ_TZ = timezone(timedelta(hours=8))
log = logging.getLogger("auto_sync.elephant_api")


def _print(msg: str):
    """统一 print, 强制 UTF-8 (避免 PowerShell GBK 编码报错)"""
    try:
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
    except UnicodeEncodeError:
        # 降级: 用 replace 错误处理
        sys.stdout.write(msg.encode('ascii', 'replace').decode('ascii') + "\n")
        sys.stdout.flush()


@dataclass
class FetchResult:
    """fetch_day() 返回结构"""
    date: str            # '2026-08-27'
    success: bool
    skipped: bool = False    # 文件已存在且未 force
    xlsx_path: str = ''      # 保存路径
    xlsx_size: int = 0
    http_status: int = 0
    error_code: str = ''     # API 业务码, e.g. '-1'
    error_msg: str = ''      # API msg, e.g. 'NO_ACCESS'
    trace_id: str = ''
    duration_sec: float = 0.0
    error: str = ''          # 异常错误信息

    def to_dict(self) -> dict:
        return asdict(self)


def _read_creds() -> dict:
    """读 elephant_api.yaml 凭据。两行一组格式：field 名为行 N, 值行 N+1。"""
    if not os.path.exists(CRED_PATH):
        raise FileNotFoundError(f"凭据文件不存在: {CRED_PATH}")
    headers = {}
    lines = open(CRED_PATH, 'r', encoding='utf-8').read().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        m = re.match(r'^\s*([A-Za-z][\w-]*)\s*:\s*$', line)
        if m and i + 1 < len(lines):
            key = m.group(1)
            val = lines[i + 1].rstrip()
            headers[key] = val
            i += 2
        else:
            i += 1
    # requests 会自动处理这几个, 去掉避免冲突
    for k in ['Host', 'Connection', 'Accept-Encoding']:
        headers.pop(k, None)
    return headers


def _is_xlsx_response(content: bytes, content_type: str) -> bool:
    """校验响应是 xlsx（OpenXML = ZIP 格式, magic = PK\\x03\\x04）"""
    if content and content[:4] == b'PK\x03\x04':
        return True
    if 'spreadsheetml' in (content_type or '').lower():
        return True
    return False


def fetch_day(date_str: str, *, force: bool = False, timeout: int = 30) -> FetchResult:
    """拉指定日期的 xlsx 到 DATA_DIR.

    Args:
        date_str: 'YYYY-MM-DD' 格式
        force: True 时即使文件已存在也覆盖

    Returns:
        FetchResult
    """
    t0 = time.time()
    target = Path(DATA_DIR) / f'{date_str}.xlsx'

    # 1. 已存在且不 force → 跳过
    if target.exists() and not force:
        return FetchResult(
            date=date_str,
            success=True,
            skipped=True,
            xlsx_path=str(target),
            xlsx_size=target.stat().st_size,
            duration_sec=time.time() - t0,
        )

    # 2. 读凭据
    try:
        headers = _read_creds()
    except Exception as e:
        return FetchResult(date=date_str, success=False, error=f"读凭据失败: {e}",
                           duration_sec=time.time() - t0)

    # 3. 发请求
    url = f'{BASE_URL}?orderTime={date_str}+00:00:00,{date_str}+23:59:59&page=1&size=16&derive=true'
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
    except Exception as e:
        return FetchResult(date=date_str, success=False, error=f"网络失败: {type(e).__name__}: {e}",
                           duration_sec=time.time() - t0)

    # 4. 校验
    if r.status_code != 200:
        return FetchResult(
            date=date_str, success=False, http_status=r.status_code,
            error=f"HTTP {r.status_code}", duration_sec=time.time() - t0,
        )

    content_type = r.headers.get('Content-Type', '')
    if not _is_xlsx_response(r.content, content_type):
        # 可能是 NO_ACCESS 业务响应（JSON 格式）
        try:
            j = r.json()
            return FetchResult(
                date=date_str, success=False, http_status=r.status_code,
                error_code=str(j.get('code', '')),
                error_msg=str(j.get('msg', '')),
                trace_id=str(j.get('traceId', '')),
                error=f"业务码 {j.get('code')}: {j.get('msg')} (traceId={j.get('traceId')})",
                duration_sec=time.time() - t0,
            )
        except Exception:
            return FetchResult(
                date=date_str, success=False, http_status=r.status_code,
                error=f"响应非 xlsx: {r.content[:200]!r}", duration_sec=time.time() - t0,
            )

    # 5. 写文件
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(r.content)
    except Exception as e:
        return FetchResult(date=date_str, success=False,
                           error=f"写文件失败: {e}", duration_sec=time.time() - t0)

    return FetchResult(
        date=date_str, success=True, xlsx_path=str(target),
        xlsx_size=len(r.content), http_status=200,
        duration_sec=time.time() - t0,
    )


def fetch_recent(days: int = 7, *, force: bool = False) -> list:
    """拉最近 N 天（含今天）的 xlsx.

    默认从昨天往前 N-1 天 + 今天 = N 天.
    跳过已存在的文件（除非 force=True）.
    """
    today = datetime.now(BJ_TZ)
    results = []
    for i in range(days):
        # i=0 → 昨天 (N=1 时只拉昨天)
        # i=days-1 → N-1 天前
        # 调整为: i=0 → 今天, i=1 → 昨天, ..., i=days-1 → N-1 天前
        # 业务上, 今天 8:30 拉数据时, 昨天数据已经完整, 今天可能还有遗漏
        d = today - timedelta(days=i)
        r = fetch_day(d.strftime('%Y-%m-%d'), force=force)
        results.append(r)
        _print(f"  {r.date}: {'skip' if r.skipped else 'ok' if r.success else 'FAIL'} "
               f"{r.xlsx_path or r.error}")
    return results


if __name__ == '__main__':
    # 命令行测试: python elephant_api.py 2026-08-26
    import sys
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(name)s] %(message)s')
    if len(sys.argv) > 1:
        # 拉指定日期
        r = fetch_day(sys.argv[1], force='--force' in sys.argv)
    else:
        # 默认拉今天
        r = fetch_day(datetime.now(BJ_TZ).strftime('%Y-%m-%d'), force='--force' in sys.argv)
    print('\n=== FetchResult ===')
    for k, v in r.to_dict().items():
        if k in ('xlsx_path',) and v:
            print(f'  {k}: {v}')
        else:
            print(f'  {k}: {v!r}')
