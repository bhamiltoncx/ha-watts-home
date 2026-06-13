"""Unit tests for humidifier entity properties."""

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


class TestHumidifierEligibility:
    def test_radiant_room_eligible(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert d.data is not None
        assert d.data.hum is not None
        assert d.data.hum.active == 1

    def test_living_not_eligible(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data is not None
        assert d.data.hum is not None
        assert d.data.hum.active == 0

    def test_561_no_hum(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Bart's Room")
        assert d.data is not None
        assert d.data.hum is None


class TestHumidifierProperties:
    def test_target_humidity(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert d.data.hum.val == 34

    def test_min_humidity(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert d.data.hum.min == 10

    def test_max_humidity(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert d.data.hum.max == 80

    def test_current_humidity_from_rh(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert d.data.sensors.rh is not None
        assert d.data.sensors.rh.status == "Okay"
        assert d.data.sensors.rh.val == 29.0


class TestHumidifierAction:
    def test_humidifying_when_fan_on_state_off(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        # Fan.Relay=1, State.Op="Off" → humidifying
        assert d.data.fan.relay == 1
        assert d.data.state.op == "Off"

    def test_idle_when_fan_off(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data.fan.relay == 0
