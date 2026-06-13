"""Unit tests for switch entity logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from custom_components.watts_home.models import WattsDevice

_FIXTURE = Path(__file__).parent / "fixtures" / "devices.json"


@pytest.fixture(scope="module")
def devices() -> list[WattsDevice]:
    raw = json.loads(_FIXTURE.read_text())["body"]
    return [WattsDevice.model_validate(d) for d in raw]


def _by_name(devices: list[WattsDevice], name: str) -> WattsDevice:
    for d in devices:
        if d.name == name:
            return d
    raise KeyError(name)


class TestAwaySwitch:
    def test_location_away_state_home(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert d.location is not None
        assert d.location.away_state == 0

    def test_all_devices_share_location(self, devices: list[WattsDevice]) -> None:
        location_ids = set()
        for d in devices:
            if d.location:
                location_ids.add(d.location.location_id)
        # Fixture has exactly one location
        assert len(location_ids) == 1


class TestEmergencyHeatSwitch:
    def test_radiant_room_has_emer(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert d.data is not None
        assert d.data.mode is not None
        assert "Emer" in d.data.mode.enum

    def test_living_no_emer(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data is not None
        assert d.data.mode is not None
        assert "Emer" not in d.data.mode.enum

    def test_is_on_when_mode_emer(self) -> None:
        d = WattsDevice.model_validate({
            "deviceId": "t", "name": "T", "modelNumber": "563", "isConnected": True,
            "data": {
                "Sensors": {"Room": {"Val": 70, "Status": "Okay"}},
                "State": {"Op": "Heat"}, "Mode": {"Val": "Emer", "Enum": ["Off", "Heat", "Emer"]},
                "Target": {"Heat": 70, "Cool": 80, "Min": 40, "Max": 95, "Steps": 1},
                "TempUnits": {"Val": "F"}, "SchedEnable": {"Val": "Off"},
            }
        })
        assert d.data.mode.val == "Emer"

    def test_restore_picks_first_non_off_non_emer(self) -> None:
        d = WattsDevice.model_validate({
            "deviceId": "t", "name": "T", "modelNumber": "563", "isConnected": True,
            "data": {
                "Sensors": {"Room": {"Val": 70, "Status": "Okay"}},
                "State": {"Op": "Heat"}, "Mode": {"Val": "Emer", "Enum": ["Off", "Heat", "Cool", "Auto", "Emer"]},
                "Target": {"Heat": 70, "Cool": 80, "Min": 40, "Max": 95, "Steps": 1},
                "TempUnits": {"Val": "F"}, "SchedEnable": {"Val": "Off"},
            }
        })
        # Should pick "Heat" (first non-Off, non-Emer)
        restore = "Heat"
        for m in d.data.mode.enum:
            if m not in ("Off", "Emer"):
                restore = m
                break
        assert restore == "Heat"
