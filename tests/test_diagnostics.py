"""Tests for config entry diagnostics."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from homeassistant.components.diagnostics import REDACTED

from custom_components.watts_home.diagnostics import (
    async_get_config_entry_diagnostics,
)

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeClient:
    def __init__(self, devices_by_location: dict[str, list[dict[str, Any]]]):
        self._devices = devices_by_location

    async def get_locations(self) -> list[dict[str, Any]]:
        return [
            {
                "locationId": loc_id,
                "name": loc_id,
                "devicesCount": len(devices),
                "address": {"city": "Springfield"},
                "ownerId": "owner-uuid",
            }
            for loc_id, devices in self._devices.items()
        ]

    async def get_raw_devices(self, location_id: str) -> list[dict[str, Any]]:
        return self._devices[location_id]


def _entry(client: _FakeClient) -> SimpleNamespace:
    async def _get_client() -> _FakeClient:
        return client

    return SimpleNamespace(
        data={
            "username": "user@example.com",
            "password": "pw",
            "access_token": "at",
            "refresh_token": "rt",
            "id_token": "jwt-with-email-and-name",
            "client_info": "uid",
            "scan_interval": 90,
        },
        runtime_data=SimpleNamespace(async_get_client=_get_client),
    )


def _fixture(name: str) -> list[dict[str, Any]]:
    return json.loads((FIXTURES / name).read_text())["body"]


async def test_includes_raw_payloads_from_every_location() -> None:
    setpoint = _fixture("setpoint_devices.json")
    setpoint[0]["data"]["UnmodelledField"] = {"Val": 1}
    client = _FakeClient(
        {"home": _fixture("devices.json"), "cottage": setpoint, "empty": []}
    )

    diag = await async_get_config_entry_diagnostics(None, _entry(client))

    home, cottage, empty = diag["locations"]
    assert len(home["devices"]) == 12
    assert cottage["devices"][0]["modelNumber"] == "170"
    assert cottage["devices"][0]["data"]["UnmodelledField"] == {"Val": 1}
    assert "devices" not in empty


async def test_redacts_credentials_and_identifiers() -> None:
    client = _FakeClient({"home": _fixture("devices.json")})

    diag = await async_get_config_entry_diagnostics(None, _entry(client))

    assert diag["entry"] == {"scan_interval": 90}

    location = diag["locations"][0]
    assert location["locationId"] == REDACTED
    assert location["name"] == REDACTED
    assert location["address"] == REDACTED
    assert location["ownerId"] == REDACTED
    device = location["devices"][0]
    assert device["deviceId"] == REDACTED
    assert device["name"] == REDACTED
    assert device["requestingUser"] == REDACTED
    assert device["location"]["locationId"] == REDACTED
    assert device["location"]["name"] == REDACTED
    assert device["location"]["address"] == REDACTED
    assert device["modelNumber"] == "561"
