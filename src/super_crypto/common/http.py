from __future__ import annotations

import os

TRUE_VALUES = {"1", "true", "yes", "on"}


def env_flag(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def http_trust_env(service: str | None = None) -> bool:
    if service:
        override_name = f"{service.upper()}_TRUST_ENV"
        if override_name in os.environ:
            return env_flag(override_name)
    return env_flag("SUPER_CRYPTO_HTTP_TRUST_ENV", default=False)


def binance_offline_cache_enabled() -> bool:
    return env_flag("BINANCE_OFFLINE_CACHE")
