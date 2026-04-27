"""Integration tests for WattsAuth — hit the real Watts API.

Skip when WAHA_USER / WAHA_PASS environment variables are not set.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from curl_cffi.requests import AsyncSession


def _load_module(name: str, path: Path) -> object:
    """Load a single .py file as a module without executing its package __init__."""
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_ROOT = Path(__file__).parent.parent / "custom_components" / "watts_home"

# Load const first (no HA dependency), then auth (depends on const).
_const = _load_module("custom_components.watts_home.const", _ROOT / "const.py")
_auth_mod = _load_module("custom_components.watts_home.auth", _ROOT / "auth.py")

WattsAuth = _auth_mod.WattsAuth  # type: ignore[attr-defined]

pytestmark = pytest.mark.skipif(
    not os.environ.get("WAHA_USER") or not os.environ.get("WAHA_PASS"),
    reason="WAHA_USER/WAHA_PASS not set",
)

USERNAME = os.environ.get("WAHA_USER", "")
PASSWORD = os.environ.get("WAHA_PASS", "")


async def test_login_returns_tokens() -> None:
    """login() must return a dict with access_token, refresh_token, expires_on."""
    async with AsyncSession() as session:
        tokens = await WattsAuth.login(session, USERNAME, PASSWORD)

    assert tokens.get("access_token"), "access_token missing or empty"
    assert tokens.get("refresh_token"), "refresh_token missing or empty"
    assert tokens.get("expires_on"), "expires_on missing or empty"


async def test_refresh_returns_new_tokens() -> None:
    """refresh() must exchange a refresh_token for a new access_token."""
    async with AsyncSession() as session:
        tokens = await WattsAuth.login(session, USERNAME, PASSWORD)
        refresh_token = tokens["refresh_token"]

        new_tokens = await WattsAuth.refresh(session, refresh_token)

    assert new_tokens.get("access_token"), "new access_token missing or empty"
