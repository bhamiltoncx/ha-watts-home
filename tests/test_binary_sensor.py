"""Unit tests for binary_sensor.py helper functions."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from custom_components.watts_home.models import WattsDevice

_ROOT = Path(__file__).parent.parent / "custom_components" / "watts_home"
_FIXTURE = Path(__file__).parent / "fixtures" / "devices.json"


def _load(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_const = _load("custom_components.watts_home.const", _ROOT / "const.py")
_bs = _load("custom_components.watts_home.binary_sensor", _ROOT / "binary_sensor.py")

device_fan_running = _bs.device_fan_running
device_radiant_heating = _bs.device_radiant_heating
device_humidifier_running = _bs.device_humidifier_running
device_cold_weather_shutdown = _bs.device_cold_weather_shutdown


@pytest.fixture(scope="module")
def devices() -> list[WattsDevice]:
    raw = json.loads(_FIXTURE.read_text())["body"]
    return [WattsDevice.model_validate(d) for d in raw]


def _by_name(devices: list[WattsDevice], name: str) -> WattsDevice:
    for d in devices:
        if d.name == name:
            return d
    raise KeyError(name)


class TestFanRunning:
    def test_fan_relay_on(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert device_fan_running(d) is True

    def test_fan_relay_off(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert device_fan_running(d) is False

    def test_no_fan_returns_none(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Bart's Room")
        assert device_fan_running(d) is None

    def test_null_data(self) -> None:
        d = WattsDevice.model_validate(
            {"deviceId": "t", "name": "T", "modelNumber": "561", "isConnected": False, "data": None}
        )
        assert device_fan_running(d) is None


class TestRadiantHeating:
    def test_floor_below_setpoint(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        # Floor=66, Schedule.Floor.W=67 → calling heat
        assert device_radiant_heating(d) is True

    def test_no_floor_sensor(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert device_radiant_heating(d) is None

    def test_floor_at_setpoint(self) -> None:
        d = WattsDevice.model_validate({
            "deviceId": "t", "name": "T", "modelNumber": "563", "isConnected": True,
            "data": {
                "Sensors": {"Room": {"Val": 70, "Status": "Okay"}, "Floor": {"Val": 67, "Status": "Okay"}},
                "State": {"Op": "Heat"}, "Mode": {"Val": "Heat", "Enum": ["Heat", "Off"]},
                "Target": {"Heat": 70, "Cool": 80, "Min": 40, "Max": 95, "Steps": 1},
                "TempUnits": {"Val": "F"}, "SchedEnable": {"Val": "Off"},
                "Schedule": {"SchedActive": 0, "HeatActive": 1, "CoolActive": 0, "FloorActive": 1,
                             "Floor": {"W": 67, "A": 60}, "FloorMin": 40, "FloorMax": 85},
            }
        })
        assert device_radiant_heating(d) is False

    def test_floor_setpoint_zero(self) -> None:
        d = WattsDevice.model_validate({
            "deviceId": "t", "name": "T", "modelNumber": "563", "isConnected": True,
            "data": {
                "Sensors": {"Room": {"Val": 70, "Status": "Okay"}, "Floor": {"Val": 66, "Status": "Okay"}},
                "State": {"Op": "Heat"}, "Mode": {"Val": "Heat", "Enum": ["Heat", "Off"]},
                "Target": {"Heat": 70, "Cool": 80, "Min": 40, "Max": 95, "Steps": 1},
                "TempUnits": {"Val": "F"}, "SchedEnable": {"Val": "Off"},
                "Schedule": {"SchedActive": 0, "HeatActive": 1, "CoolActive": 0, "FloorActive": 1,
                             "Floor": {"W": 0, "A": 0}, "FloorMin": 40, "FloorMax": 85},
            }
        })
        assert device_radiant_heating(d) is False


class TestHumidifierRunning:
    def test_fan_on_state_off(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        # Fan.Relay=1, State.Op="Off" → humidifier running
        assert device_humidifier_running(d) is True

    def test_no_humidifier(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Bart's Room")
        assert device_humidifier_running(d) is None

    def test_fan_on_state_heating(self) -> None:
        d = WattsDevice.model_validate({
            "deviceId": "t", "name": "T", "modelNumber": "563", "isConnected": True,
            "data": {
                "Sensors": {"Room": {"Val": 70, "Status": "Okay"}},
                "State": {"Op": "Heat"}, "Mode": {"Val": "Heat", "Enum": ["Heat", "Off"]},
                "Target": {"Heat": 70, "Cool": 80, "Min": 40, "Max": 95, "Steps": 1},
                "TempUnits": {"Val": "F"}, "SchedEnable": {"Val": "Off"},
                "Fan": {"Active": 1, "Val": "Auto", "Enum": ["Auto", "On"], "Relay": 1},
                "Hum": {"Active": 1, "Val": 30, "Min": 10, "Max": 80, "Steps": 1},
            }
        })
        # Fan is on but system is heating — not humidifier
        assert device_humidifier_running(d) is False


class TestColdWeatherShutdown:
    def test_cwsd_active(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Radiant Room")
        assert device_cold_weather_shutdown(d) is True

    def test_cwsd_inactive(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert device_cold_weather_shutdown(d) is False

    def test_null_state(self) -> None:
        d = WattsDevice.model_validate(
            {"deviceId": "t", "name": "T", "modelNumber": "561", "isConnected": False, "data": None}
        )
        assert device_cold_weather_shutdown(d) is None
