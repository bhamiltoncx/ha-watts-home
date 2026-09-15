"""Tests for how the coordinator classifies auth failures.

A transient server error must stay recoverable: Home Assistant stops
scheduling refreshes entirely once a coordinator raises ConfigEntryAuthFailed,
so misclassifying a 502 leaves every entity unavailable until a reload.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

# Bind through the coordinator's own namespace: sibling test modules load a
# second copy of auth.py into sys.modules, so importing these directly can
# yield classes the coordinator's except clauses will not match.
from custom_components.watts_home import coordinator as coord_mod

WattsAuth = coord_mod.WattsAuth
WattsAuthError = coord_mod.WattsAuthError
WattsServerError = coord_mod.WattsServerError
WattsTokenExpiredError = coord_mod.WattsTokenExpiredError


def _coordinator(entry_data: dict[str, Any]) -> coord_mod.WattsDataUpdateCoordinator:
    """Build a coordinator without running HA's DataUpdateCoordinator setup."""
    coord = object.__new__(coord_mod.WattsDataUpdateCoordinator)
    coord._entry = SimpleNamespace(data=entry_data)
    coord._session = object()
    coord.hass = SimpleNamespace(
        config_entries=SimpleNamespace(async_update_entry=lambda *a, **k: None)
    )
    return coord


_CREDS = {"username": "user@example.com", "password": "pw", "expires_on": 0}


async def test_server_error_during_login_is_update_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise WattsServerError("Authorize GET failed after 4 attempts: HTTP 502")

    monkeypatch.setattr(WattsAuth, "login", staticmethod(_boom))
    coord = _coordinator(dict(_CREDS))

    with pytest.raises(UpdateFailed) as excinfo:
        await coord._async_update_data()
    assert "502" in str(excinfo.value)


async def test_server_error_during_refresh_is_update_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _boom(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise WattsServerError("Token refresh failed after 4 attempts: HTTP 502")

    async def _login_not_called(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise AssertionError("full re-login must not run on a transient failure")

    monkeypatch.setattr(WattsAuth, "refresh", staticmethod(_boom))
    monkeypatch.setattr(WattsAuth, "login", staticmethod(_login_not_called))
    coord = _coordinator({**_CREDS, "refresh_token": "rt"})

    with pytest.raises(UpdateFailed):
        await coord._async_update_data()


async def test_expired_refresh_token_falls_back_to_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _expired(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise WattsTokenExpiredError("HTTP 400")

    async def _login(*_a: Any, **_k: Any) -> dict[str, Any]:
        return {"access_token": "fresh", "expires_on": 9999999999}

    monkeypatch.setattr(WattsAuth, "refresh", staticmethod(_expired))
    monkeypatch.setattr(WattsAuth, "login", staticmethod(_login))
    coord = _coordinator({**_CREDS, "refresh_token": "rt"})

    assert await coord._ensure_token() == "fresh"


async def test_bad_credentials_still_raise_auth_failed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _rejected(*_a: Any, **_k: Any) -> dict[str, Any]:
        raise WattsAuthError("Credentials rejected")

    monkeypatch.setattr(WattsAuth, "login", staticmethod(_rejected))
    coord = _coordinator(dict(_CREDS))

    with pytest.raises(ConfigEntryAuthFailed):
        await coord._async_update_data()


async def test_polls_every_location_with_devices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    locations = [
        {"locationId": "cottage", "isDefault": False, "devicesCount": 1},
        {"locationId": "empty", "isDefault": False, "devicesCount": 0},
        {"locationId": "home", "isDefault": True, "devicesCount": 2},
    ]
    devices_by_location = {"cottage": ["c1"], "home": ["h1", "h2"]}
    polled: list[str] = []

    async def _get_locations(_self: Any) -> list[dict[str, Any]]:
        return locations

    async def _get_devices(_self: Any, location_id: str) -> list[Any]:
        polled.append(location_id)
        return [SimpleNamespace(device_id=d) for d in devices_by_location[location_id]]

    monkeypatch.setattr(coord_mod.WattsApiClient, "get_locations", _get_locations)
    monkeypatch.setattr(coord_mod.WattsApiClient, "get_devices", _get_devices)
    coord = _coordinator({"access_token": "t", "expires_on": 9999999999})

    data = await coord._async_update_data()

    assert polled == ["cottage", "home"]
    assert set(data) == {"c1", "h1", "h2"}
