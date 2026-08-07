"""Unit tests for transient-failure retry in the auth layer.

These use a stub session and never touch the network.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
from curl_cffi.requests.exceptions import ConnectionError as CurlConnectionError


def _load_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_ROOT = Path(__file__).parent.parent / "custom_components" / "watts_home"
_load_module("custom_components.watts_home.const", _ROOT / "const.py")
_auth = _load_module("custom_components.watts_home.auth", _ROOT / "auth.py")

WattsAuth = _auth.WattsAuth
WattsServerError = _auth.WattsServerError
WattsTokenExpiredError = _auth.WattsTokenExpiredError


class _Resp:
    def __init__(self, status_code: int, payload: dict[str, Any] | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "body"

    def json(self) -> dict[str, Any]:
        return self._payload


class _StubSession:
    """Returns each queued item in turn; raises it if it is an exception."""

    def __init__(self, queue: list[Any]) -> None:
        self._queue = list(queue)
        self.calls = 0

    async def request(self, method: str, url: str, **kwargs: Any) -> _Resp:
        self.calls += 1
        item = self._queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make backoff instant so tests do not wait on real delays."""

    async def _instant(_delay: float) -> None:
        return None

    monkeypatch.setattr(_auth.asyncio, "sleep", _instant)


async def test_retries_502_then_succeeds() -> None:
    session = _StubSession([_Resp(502), _Resp(502), _Resp(200)])
    resp = await _auth._request(session, "GET", "https://x", label="Authorize GET")
    assert resp.status_code == 200
    assert session.calls == 3


async def test_raises_server_error_when_attempts_exhausted() -> None:
    session = _StubSession([_Resp(502)] * _auth.AUTH_MAX_ATTEMPTS)
    with pytest.raises(WattsServerError, match="HTTP 502"):
        await _auth._request(session, "GET", "https://x", label="Authorize GET")
    assert session.calls == _auth.AUTH_MAX_ATTEMPTS


async def test_transport_error_is_retried() -> None:
    session = _StubSession([CurlConnectionError("reset"), _Resp(200)])
    resp = await _auth._request(session, "GET", "https://x", label="Authorize GET")
    assert resp.status_code == 200
    assert session.calls == 2


async def test_client_error_is_not_retried() -> None:
    """A 400 is a real answer — returning it lets the caller classify it."""
    session = _StubSession([_Resp(400)])
    resp = await _auth._request(session, "POST", "https://x", label="Token refresh")
    assert resp.status_code == 400
    assert session.calls == 1


async def test_login_surfaces_server_error_not_auth_error() -> None:
    """A wedged gateway must not be reported as a credential problem."""
    session = _StubSession([_Resp(502)] * _auth.AUTH_MAX_ATTEMPTS)
    with pytest.raises(WattsServerError):
        await WattsAuth.login(session, "user@example.com", "pw")


async def test_refresh_502_is_server_error_not_token_expired() -> None:
    """Otherwise a gateway blip forces a needless full re-login."""
    session = _StubSession([_Resp(502)] * _auth.AUTH_MAX_ATTEMPTS)
    with pytest.raises(WattsServerError):
        await WattsAuth.refresh(session, "refresh-token")


async def test_refresh_400_is_token_expired() -> None:
    session = _StubSession([_Resp(400)])
    with pytest.raises(WattsTokenExpiredError):
        await WattsAuth.refresh(session, "refresh-token")


async def test_refresh_succeeds_after_retry() -> None:
    session = _StubSession([_Resp(503), _Resp(200, {"access_token": "abc"})])
    tokens = await WattsAuth.refresh(session, "refresh-token")
    assert tokens["access_token"] == "abc"
