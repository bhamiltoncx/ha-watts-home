"""Integration tests for WattsApiClient — hit the real Watts API.

Skip when WAHA_USER / WAHA_PASS environment variables are not set.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest
from curl_cffi.requests import AsyncSession

_ROOT = Path(__file__).parent.parent / "custom_components" / "watts_home"


def _load(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_const = _load("custom_components.watts_home.const", _ROOT / "const.py")
_auth_mod = _load("custom_components.watts_home.auth", _ROOT / "auth.py")
_api_mod = _load("custom_components.watts_home.api", _ROOT / "api.py")

WattsAuth = _auth_mod.WattsAuth  # type: ignore[attr-defined]
WattsApiClient = _api_mod.WattsApiClient  # type: ignore[attr-defined]

pytestmark = pytest.mark.skipif(
    not os.environ.get("WAHA_USER") or not os.environ.get("WAHA_PASS"),
    reason="WAHA_USER/WAHA_PASS not set",
)

USERNAME = os.environ.get("WAHA_USER", "")
PASSWORD = os.environ.get("WAHA_PASS", "")


@pytest.fixture()
async def client() -> WattsApiClient:  # type: ignore[valid-type]
    async with AsyncSession(impersonate="chrome110") as session:
        tokens = await WattsAuth.login(session, USERNAME, PASSWORD)
        yield WattsApiClient(session, tokens["access_token"])


async def test_get_locations(client: WattsApiClient) -> None:  # type: ignore[valid-type]
    locations = await client.get_locations()
    assert isinstance(locations, list)
    assert len(locations) > 0
    loc = locations[0]
    assert "locationId" in loc or "id" in loc or "LocationId" in loc


async def test_find_default_location(client: WattsApiClient) -> None:  # type: ignore[valid-type]
    locations = await client.get_locations()
    loc = WattsApiClient.find_default_location(locations)
    assert loc is not None


async def test_get_devices(client: WattsApiClient) -> None:  # type: ignore[valid-type]
    locations = await client.get_locations()
    loc = WattsApiClient.find_default_location(locations)
    # Location ID key may vary — check both known shapes
    loc_id: str = loc.get("locationId") or loc.get("LocationId") or loc.get("id", "")
    assert loc_id, f"Could not find location ID in {loc.keys()}"

    devices = await client.get_devices(loc_id)
    assert isinstance(devices, list)
    assert len(devices) > 0

    device = devices[0]
    assert "data" in device
    assert "Mode" in device["data"]
    assert "Target" in device["data"]
