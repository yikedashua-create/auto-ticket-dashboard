# -*- coding: utf-8 -*-
"""
elephant 网关请求签名客户端（v1，2026-09-25）

背景：2026-09 下旬 elephant 网关新增风控层，对 /gateway/* 业务接口强制要求
请求签名（缺失时返回 HTTP 400 {"code":"SIGNATURE_REQUIRED"}）。静态 header
方案（Token/Vcode/Cookie）从此不再够用，必须按前端 JS 的
createRequestSignatureClient 逻辑复刻：

  1. GET  {ORIGIN}/gateway/_gateway/signature/status      → {"enabled":true}
  2. 生成 ECDSA P-256 密钥对（浏览器存 IndexedDB，这里存 JSON 文件）
  3. POST {ORIGIN}/gateway/_gateway/signature/challenge   {publicKey:{kty,crv,x,y}}
       → {challengeId, salt, publicKeyThumbprint, difficulty, expiresAt, challengeToken}
  4. 解 PoW：找十进制计数器 n 使 SHA256("challengeId\nsalt\nthumbprint\nn")
       前导 0 位 ≥ difficulty
  5. POST {ORIGIN}/gateway/_gateway/signature/register    {publicKey, workNonce, challengeToken}
       → {clientId, expiresAt}
  6. 每个业务请求附头：
       X-Signature-Version: v1
       X-Client-Id / X-Request-Timestamp(ms) / X-Request-Nonce(b64url 16B)
       X-Request-Body-SHA256 / X-Request-Signature(b64url, raw r||s 64B)
     签名规范串（\n 连接 9 段）：
       v1, clientId, METHOD, gateway-prod.xiangshangsl.com,
       canonicalPathAndQuery(去掉 /gateway 前缀, query 按 (k,v) 排序后 RFC3986 重编码),
       sha256hex(body), sha256hex(Authorization)||"", timestamp, nonce

canonicalHost 硬编码 gateway-prod.xiangshangsl.com 来自前端 bundle
（浏览器模式 baseUrl="/gateway"，Electron 模式才是 https://gateway-prod...）。
"""
import base64
import hashlib
import json
import os
import time
from urllib.parse import urlsplit, parse_qsl, quote

import requests

ORIGIN = 'https://elephant.xiangshangsl.com'
STATUS_URL = ORIGIN + '/gateway/_gateway/signature/status'
CHALLENGE_URL = ORIGIN + '/gateway/_gateway/signature/challenge'
REGISTER_URL = ORIGIN + '/gateway/_gateway/signature/register'
CANONICAL_HOST = 'gateway-prod.xiangshangsl.com'
PATH_PREFIX = '/gateway'

STATE_PATH = r'E:\Work\Documents\凭据\elephant_sig_client.json'
POW_MAX_ATTEMPTS = 5_000_000
POW_MAX_SECONDS = 120.0
TIMEOUT = 20


def _b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')


def _percent_encode(s: str) -> str:
    # 等价 JS: encodeURIComponent(s).replace(/[!'()*]/g, %XX 大写)
    return quote(s, safe='-_.~')


def _canonical_path_and_query(path: str, query: str) -> str:
    if path == PATH_PREFIX or path.startswith(PATH_PREFIX + '/'):
        path = path[len(PATH_PREFIX):] or '/'
    pairs = sorted(parse_qsl(query, keep_blank_values=True))
    if not pairs:
        return path
    return path + '?' + '&'.join(
        f'{_percent_encode(k)}={_percent_encode(v)}' for k, v in pairs)


def _leading_zero_bits(digest: bytes) -> int:
    n = 0
    for b in digest:
        if b == 0:
            n += 8
            continue
        n += 8 - b.bit_length()
        break
    return n


def _solve_pow(ch: dict) -> str:
    prefix = f"{ch['challengeId']}\n{ch['salt']}\n{ch['publicKeyThumbprint']}\n"
    difficulty = int(ch['difficulty'])
    t0 = time.time()
    for n in range(POW_MAX_ATTEMPTS):
        if n % 65536 == 0 and time.time() - t0 > POW_MAX_SECONDS:
            break
        s = prefix + str(n)
        if _leading_zero_bits(hashlib.sha256(s.encode()).digest()) >= difficulty:
            return str(n)
    raise RuntimeError(f'PoW 超限 (difficulty={difficulty})')


def _load_state() -> dict:
    if os.path.exists(STATE_PATH):
        try:
            return json.load(open(STATE_PATH, encoding='utf-8'))
        except Exception:
            pass
    return {}


def _save_state(st: dict):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(st, f, ensure_ascii=False, indent=2)


def _generate_keypair() -> dict:
    from cryptography.hazmat.primitives.asymmetric import ec
    priv = ec.generate_private_key(ec.SECP256R1())
    pub = priv.public_key().public_numbers()
    d = priv.private_numbers().private_value
    return {
        'priv_jwk': {
            'kty': 'EC', 'crv': 'P-256',
            'x': _b64u(pub.x.to_bytes(32, 'big')),
            'y': _b64u(pub.y.to_bytes(32, 'big')),
            'd': _b64u(d.to_bytes(32, 'big')),
        },
        'clientId': None,
        'expiresAt': 0,
    }


def _pub_jwk(priv_jwk: dict) -> dict:
    return {k: priv_jwk[k] for k in ('kty', 'crv', 'x', 'y')}


def _sign_canonical(priv_jwk: dict, canonical: str) -> str:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
    key = _load_ec_key(priv_jwk)
    der = key.sign(canonical.encode('utf-8'), ec.ECDSA(hashes.SHA256()))
    r, s = decode_dss_signature(der)
    return _b64u(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))


def _load_ec_key(priv_jwk: dict):
    from cryptography.hazmat.primitives.asymmetric import ec
    b64u_to_int = lambda s: int.from_bytes(
        base64.urlsafe_b64decode(s + '=' * (-len(s) % 4)), 'big')
    return ec.derive_private_key(b64u_to_int(priv_jwk['d']), ec.SECP256R1())


def ensure_registered(force: bool = False) -> dict:
    """确保有未过期的 clientId（浏览器逻辑：expiresAt > now+30s 才复用）"""
    st = _load_state()
    if not force:
        cid = st.get('clientId')
        if isinstance(cid, str) and '.' in cid and st.get('expiresAt', 0) > time.time() * 1000 + 30_000:
            return st
    if 'priv_jwk' not in st:
        st = _generate_keypair()
    return _register_flow(st)


def _register_flow(st: dict) -> dict:
    status = requests.get(STATUS_URL, headers={'Accept': 'application/json'}, timeout=TIMEOUT).json()
    if status.get('enabled') is False:
        st['clientId'] = None
        st['enabled'] = False
        _save_state(st)
        return st

    pub = _pub_jwk(st['priv_jwk'])
    ch = requests.post(CHALLENGE_URL, json={'publicKey': pub}, timeout=TIMEOUT).json()
    if ch.get('enabled') is False:
        return st
    work_nonce = _solve_pow(ch)
    reg = requests.post(REGISTER_URL, json={
        'publicKey': pub, 'workNonce': work_nonce,
        'challengeToken': ch['challengeToken'],
    }, timeout=TIMEOUT).json()
    st['clientId'] = reg['clientId']
    st['expiresAt'] = reg['expiresAt']
    st.pop('enabled', None)
    _save_state(st)
    return st


def signed_headers(url: str, method: str = 'GET', body: bytes = b'') -> dict:
    """对业务 URL 计算签名头（需要时自动注册 clientId）"""
    st = ensure_registered()
    if st.get('enabled') is False:
        return {}
    if not st.get('clientId'):
        raise RuntimeError('网关签名 clientId 注册失败')
    u = urlsplit(url)
    path_and_query = _canonical_path_and_query(u.path or '/', u.query or '')
    body_sha = hashlib.sha256(body or b'').hexdigest()
    ts = str(int(time.time() * 1000))
    nonce = _b64u(os.urandom(16))
    canonical = '\n'.join([
        'v1', st['clientId'], method.upper(), CANONICAL_HOST,
        path_and_query, body_sha, '', ts, nonce,
    ])
    sig = _sign_canonical(st['priv_jwk'], canonical)
    return {
        'X-Signature-Version': 'v1',
        'X-Client-Id': st['clientId'],
        'X-Request-Timestamp': ts,
        'X-Request-Nonce': nonce,
        'X-Request-Body-SHA256': body_sha,
        'X-Request-Signature': sig,
    }


def is_signature_required(resp) -> bool:
    if resp.status_code != 400:
        return False
    try:
        return resp.json().get('code') == 'SIGNATURE_REQUIRED'
    except Exception:
        return False


if __name__ == '__main__':
    # 自测：注册 + 对业务接口签名（不带 token，预期返回 NO_ACCESS 而非 SIGNATURE_REQUIRED）
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    st = ensure_registered(force=True)
    print('clientId:', (st.get('clientId') or 'None')[:20], '...')
    print('expiresAt:', st.get('expiresAt'))
    url = (ORIGIN + PATH_PREFIX + '/internation-ticket/order/page'
           '?orderTime=2026-01-01+00:00:00,2026-01-01+23:59:59&page=1&size=1&derive=true')
    h = signed_headers(url)
    print('sig headers:', sorted(h))
    r = requests.get(url, headers=h, timeout=TIMEOUT)
    print('HTTP', r.status_code, r.content[:200])
