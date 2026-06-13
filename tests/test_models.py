"""Tests for Pydantic models in models.py."""

from __future__ import annotations

import json
from pathlib import Path

from custom_components.watts_home.models import WattsDevice

_FIXTURE = Path(__file__).parent / "fixtures" / "devices.json"


def _raw_devices() -> list[dict]:
    return json.loads(_FIXTURE.read_text())["body"]


def test_model_validate_all_devices() -> None:
    raw = _raw_devices()
    devices = [WattsDevice.model_validate(d) for d in raw]
    assert len(devices) == len(raw)
    for device in devices:
        assert isinstance(device.device_id, str)
        assert isinstance(device.name, str)
        assert isinstance(device.model_number, str)
        assert isinstance(device.is_connected, bool)


def test_extra_fields_are_ignored() -> None:
    WattsDevice.model_validate(
        {
            "deviceId": "test-id",
            "name": "Test",
            "modelNumber": "561",
            "isConnected": True,
            "data": None,
            "unknownFutureField": "some_value",
            "imageUrl": "https://example.com/img.png",
        }
    )


def test_null_data_parses_without_error() -> None:
    device = WattsDevice.model_validate(
        {
            "deviceId": "test-id",
            "name": "Test",
            "modelNumber": "561",
            "isConnected": False,
            "data": None,
        }
    )
    assert device.data is None


def test_null_data_subfields_parse_without_error() -> None:
    device = WattsDevice.model_validate(
        {
            "deviceId": "test-id",
            "name": "Test",
            "modelNumber": "561",
            "isConnected": False,
            "data": {
                "Mode": None,
                "State": None,
                "Sensors": None,
                "Target": None,
                "TempUnits": None,
                "SchedEnable": None,
                "Fan": None,
            },
        }
    )
    assert device.data is not None
    assert device.data.mode is None
    assert device.data.sensors is None
    assert device.data.state is None
    assert device.data.target is None


def test_target_without_range_fields_parses() -> None:
    """SnowMelt controls (e.g. Tekmar 671) return Target without Min/Max/Steps."""
    device = WattsDevice.model_validate(
        {
            "deviceId": "snowmelt-1",
            "name": "Driveway",
            "modelNumber": "671",
            "isConnected": True,
            "data": {
                "Target": {"Heat": 38.0},
            },
        }
    )
    assert device.data is not None
    assert device.data.target is not None
    assert device.data.target.heat == 38.0
    assert device.data.target.min is None
    assert device.data.target.max is None
    assert device.data.target.steps is None


def test_full_device_fields_round_trip() -> None:
    """A device with every sub-field present parses to the right values."""
    device = WattsDevice.model_validate(
        {
            "deviceId": "abc-123",
            "name": "Hallway",
            "modelNumber": "562",
            "isConnected": True,
            "data": {
                "Mode": {"Val": "Heat", "Enum": ["Heat", "Cool", "Auto", "Off"]},
                "State": {"Op": "Heat"},
                "Sensors": {
                    "Room": {"Val": 71.5, "Status": "Okay"},
                    "Floor": {"Val": 0.0, "Status": "NotInstalled"},
                    "Outdoor": {"Val": 45.0, "Status": "Okay"},
                    "RH": {"Val": 42.0, "Status": "Okay"},
                },
                "Target": {
                    "Heat": 70.0,
                    "Cool": 78.0,
                    "Min": 40.0,
                    "Max": 95.0,
                    "Steps": 1.0,
                },
                "TempUnits": {"Val": "F"},
                "SchedEnable": {"Val": "Off"},
                "Fan": {"Val": "Auto", "Enum": ["Auto", "On"]},
            },
        }
    )
    assert device.device_id == "abc-123"
    assert device.data is not None
    assert device.data.mode is not None
    assert device.data.mode.val == "Heat"
    assert device.data.mode.enum == ["Heat", "Cool", "Auto", "Off"]
    assert device.data.state is not None
    assert device.data.state.op == "Heat"
    assert device.data.sensors is not None
    assert device.data.sensors.room is not None
    assert device.data.sensors.room.val == 71.5
    assert device.data.sensors.room.status == "Okay"
    assert device.data.sensors.outdoor is not None
    assert device.data.sensors.outdoor.status == "Okay"
    assert device.data.sensors.rh is not None
    assert device.data.sensors.rh.val == 42.0
    assert device.data.target is not None
    assert device.data.target.heat == 70.0
    assert device.data.target.cool == 78.0
    assert device.data.target.min == 40.0
    assert device.data.target.max == 95.0
    assert device.data.target.steps == 1.0
    assert device.data.temp_units is not None
    assert device.data.temp_units.val == "F"
    assert device.data.fan is not None
    assert device.data.fan.val == "Auto"
    assert device.data.fan.enum == ["Auto", "On"]
    assert device.data.sched_enable is not None
    assert device.data.sched_enable.val == "Off"
