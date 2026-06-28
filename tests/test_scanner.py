from __future__ import annotations

import httpx

from super_crypto.realtime.scanner import _send_webhook


def test_invalid_webhook_url_is_ignored(monkeypatch):
    called = False

    def fake_post(self, url, json):  # pragma: no cover - should never be reached
        nonlocal called
        called = True

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    _send_webhook("${DISCORD_WEBHOOK_URL}", {"ok": True})
    assert called is False
