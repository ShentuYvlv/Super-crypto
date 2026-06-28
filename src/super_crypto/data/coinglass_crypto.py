from __future__ import annotations

import base64
import gzip
import json
import zlib
from typing import Any
from urllib.parse import urlparse

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

STATIC_SEEDS = {
    "55": "170b070da9654622",
    "66": "d6537d845a964081",
    "77": "863f08689c97435b",
}


def pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        raise ValueError("empty decrypted payload")
    pad_len = data[-1]
    if pad_len < 1 or pad_len > 16:
        raise ValueError(f"invalid PKCS7 padding length: {pad_len}")
    if data[-pad_len:] != bytes([pad_len]) * pad_len:
        raise ValueError("invalid PKCS7 padding bytes")
    return data[:-pad_len]


def aes_ecb_decrypt(cipher_text: str, key: str) -> bytes:
    key_bytes = key.encode("utf-8")
    if len(key_bytes) not in (16, 24, 32):
        raise ValueError(f"AES key must be 16/24/32 bytes, got {len(key_bytes)}")

    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB())
    decryptor = cipher.decryptor()
    encrypted = base64.b64decode(cipher_text)
    return pkcs7_unpad(decryptor.update(encrypted) + decryptor.finalize())


def decompress_payload(data: bytes) -> bytes:
    if data.startswith(b"\x1f\x8b"):
        return gzip.decompress(data)
    return zlib.decompress(data)


def decrypt_payload(cipher_text: str, key: str) -> str:
    decrypted = aes_ecb_decrypt(cipher_text, key)
    text = decompress_payload(decrypted).decode("utf-8")
    if text.startswith('"'):
        text = text[1:]
    if text.endswith('"'):
        text = text[:-1]
    return text


def api_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or url
    api_index = path.find("/api")
    if api_index >= 0:
        return path[api_index:]
    return path.split("?", 1)[0]


def seed_for_v(v_header: str, url: str, cache_ts_v2: str, time_header: str) -> str:
    if v_header == "0":
        if not cache_ts_v2:
            raise ValueError("v=0 requires cache-ts-v2")
        return cache_ts_v2
    if v_header == "1":
        return api_path(url)
    if v_header == "2":
        if not time_header:
            raise ValueError("v=2 requires response time header")
        return time_header
    if v_header in STATIC_SEEDS:
        return STATIC_SEEDS[v_header]
    raise ValueError(f"unsupported CoinGlass v header: {v_header}")


def maybe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def decrypt_response_data(
    *,
    data_cipher: str,
    user_header: str,
    v_header: str,
    url: str,
    cache_ts_v2: str,
    time_header: str = "",
) -> Any:
    seed = seed_for_v(v_header, url, cache_ts_v2, time_header)
    key0 = base64.b64encode(seed.encode("utf-8")).decode("ascii")[:16]
    real_key = decrypt_payload(user_header, key0)
    plain_text = decrypt_payload(data_cipher, real_key)
    return maybe_json(plain_text)
