from __future__ import annotations

import base64
import gzip
import json
import zlib

import httpx
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from super_crypto.data.coinglass_client import CoinGlassClient
from super_crypto.data.coinglass_crypto import decrypt_response_data, seed_for_v
from super_crypto.data.normalize_external import normalize_records


def _pad(data: bytes) -> bytes:
    pad_len = 16 - (len(data) % 16)
    return data + bytes([pad_len]) * pad_len


def _encrypt_payload(value, key: str, *, gzip_payload: bool = False) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode()
    compressed = gzip.compress(text) if gzip_payload else zlib.compress(text)
    cipher = Cipher(algorithms.AES(key.encode()), modes.ECB())
    encryptor = cipher.encryptor()
    encrypted = encryptor.update(_pad(compressed)) + encryptor.finalize()
    return base64.b64encode(encrypted).decode()


def test_coinglass_seed_variants():
    assert seed_for_v("0", "https://x.test/api/coin/tickers", "123", "") == "123"
    assert (
        seed_for_v("1", "https://capi.coinglass.com/api/coin/tickers?symbol=SYN", "", "")
        == "/api/coin/tickers"
    )
    assert seed_for_v("2", "https://x.test/api/a", "", "456") == "456"
    assert seed_for_v("55", "https://x.test/api/a", "", "") == "170b070da9654622"


def test_decrypt_response_data_roundtrip():
    url = "https://capi.coinglass.com/api/coin/tickers?symbol=SYN"
    cache_ts = "1710000000000"
    key0 = base64.b64encode(cache_ts.encode()).decode("ascii")[:16]
    real_key = "1234567890abcdef"
    user_header = _encrypt_payload(real_key, key0)
    data_cipher = _encrypt_payload([{"exchangeName": "Binance", "openInterest": 12.5}], real_key)

    assert decrypt_response_data(
        data_cipher=data_cipher,
        user_header=user_header,
        v_header="0",
        url=url,
        cache_ts_v2=cache_ts,
    ) == [{"exchangeName": "Binance", "openInterest": 12.5}]


def test_coinglass_client_fetch_decrypts_encrypted_response(monkeypatch):
    cache_ts = "1710000000000"
    real_key = "1234567890abcdef"
    key0 = base64.b64encode(cache_ts.encode()).decode("ascii")[:16]
    user_header = _encrypt_payload(real_key, key0)
    data_cipher = _encrypt_payload({"marketCap": 1000}, real_key, gzip_payload=True)
    captured = {}

    def fake_get(self, url, *, params=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return httpx.Response(
            200,
            json={"data": data_cipher},
            headers={"encryption": "true", "user": user_header, "v": "0"},
            request=httpx.Request("GET", url, params=params),
        )

    monkeypatch.setattr("time.time", lambda: 1710000000.0)
    monkeypatch.setattr(httpx.Client, "get", fake_get)

    with CoinGlassClient() as client:
        payload = client.fetch("coin_info", "syn")

    assert payload == {"marketCap": 1000}
    assert captured["url"] == "https://fapi.coinglass.com/api/coin/v2/info"
    assert captured["params"] == {"symbol": "SYN"}
    assert captured["headers"]["encryption"] == "true"
    assert captured["headers"]["cache-ts-v2"] == cache_ts


def test_coinglass_client_rejects_unknown_endpoint():
    with CoinGlassClient() as client, pytest.raises(ValueError):
        client.fetch("unknown", "BTC")


def test_normalize_coinglass_core_fields():
    tickers = normalize_records(
        "SYN",
        "tickers",
        [
            {
                "exchangeName": "Binance",
                "symbol": "SYNUSDT",
                "openInterest": "1200",
                "volumeUsd": "3000",
                "longShortRatio": "1.2",
            }
        ],
    )
    assert tickers["exchange"][0] == "Binance"
    assert tickers["open_interest"][0] == 1200
    assert tickers["long_short_ratio"][0] == 1.2

    flow = normalize_records(
        "SYN",
        "futures_flow",
        {"h4InflowUsd": 10, "h4OutflowUsd": 4},
    )
    assert flow["futures_inflow_4h"][0] == 10
    assert flow["futures_netflow_4h"][0] == 6
