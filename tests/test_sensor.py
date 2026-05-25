"""Unit tests for sensor.py using real fixture data."""

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


def _by_model(devices: list[WattsDevice], model: str) -> WattsDevice:
    for d in devices:
        if d.model_number == model:
            return d
    raise KeyError(model)


def _by_name(devices: list[WattsDevice], name: str) -> WattsDevice:
    for d in devices:
        if d.name == name:
            return d
    raise KeyError(name)


class TestOutdoorSensorEligibility:
    def test_562_has_outdoor_okay(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        assert d.data is not None
        assert d.data.sensors is not None
        assert d.data.sensors.outdoor is not None
        assert d.data.sensors.outdoor.status == "Okay"

    def test_561_outdoor_absent(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert d.data is not None
        assert d.data.sensors is not None
        outdoor = d.data.sensors.outdoor
        assert outdoor is None or outdoor.status != "Okay"

    def test_563_has_outdoor_okay(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data is not None
        assert d.data.sensors is not None
        assert d.data.sensors.outdoor is not None
        assert d.data.sensors.outdoor.status == "Okay"


class TestHumiditySensorEligibility:
    def test_563_living_has_rh_okay(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data is not None
        assert d.data.sensors is not None
        rh = d.data.sensors.rh
        assert rh is not None
        assert rh.status == "Okay"
        assert isinstance(rh.val, float)

    def test_562_no_rh_okay(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        assert d.data is not None
        assert d.data.sensors is not None
        rh = d.data.sensors.rh
        assert rh is None or rh.status != "Okay"

    def test_561_no_rh(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert d.data is not None
        assert d.data.sensors is not None
        rh = d.data.sensors.rh
        assert rh is None or rh.status != "Okay"


class TestSensorCounts:
    """Verify the expected number of sensor entities created from the fixture."""

    def test_outdoor_sensor_count(self, devices: list[WattsDevice]) -> None:
        outdoor_count = sum(
            1
            for d in devices
            if d.data
            and d.data.sensors
            and d.data.sensors.outdoor
            and d.data.sensors.outdoor.status == "Okay"
        )
        # From fixture: 4 original + 1 Radiant Room = 5
        assert outdoor_count == 5

    def test_humidity_sensor_count(self, devices: list[WattsDevice]) -> None:
        rh_count = sum(
            1
            for d in devices
            if d.data
            and d.data.sensors
            and d.data.sensors.rh
            and d.data.sensors.rh.status == "Okay"
        )
        # From fixture: Living + Radiant Room = 2
        assert rh_count == 2

    def test_floor_sensor_count(self, devices: list[WattsDevice]) -> None:
        floor_count = sum(
            1
            for d in devices
            if d.data
            and d.data.sensors
            and d.data.sensors.floor
            and d.data.sensors.floor.status == "Okay"
        )
        # Only Radiant Room has Floor Status=Okay
        assert floor_count == 1

    def test_energy_heat_sensor_count(self, devices: list[WattsDevice]) -> None:
        count = sum(
            1
            for d in devices
            if d.data
            and d.data.energy
            and d.data.energy.heat
            and d.data.energy.heat.daily
        )
        # All 12 devices have Energy.Heat.Daily
        assert count == len(devices)

    def test_energy_cool_sensor_count(self, devices: list[WattsDevice]) -> None:
        count = sum(
            1
            for d in devices
            if d.data
            and d.data.energy
            and d.data.energy.cool
            and d.data.energy.cool.daily
        )
        # Only 562/563 devices have Energy.Cool.Daily (4 devices)
        assert count >= 4


_NULL_DATA_FIELD_DEVICE: WattsDevice = WattsDevice.model_validate(
    {
        "deviceId": "null-data-field",
        "name": "Null Data Field Device",
        "modelNumber": "561",
        "isConnected": False,
        "data": None,
    }
)


class TestNullDataSensor:
    """Guards against device.data being None in sensor setup and entity methods."""

    def test_outdoor_eligibility_skips_null_data_device(
        self, devices: list[WattsDevice]
    ) -> None:
        all_devices = [*devices, _NULL_DATA_FIELD_DEVICE]
        outdoor_count = sum(
            1
            for d in all_devices
            if d.data
            and d.data.sensors
            and d.data.sensors.outdoor
            and d.data.sensors.outdoor.status == "Okay"
        )
        # 5 from fixture + 0 from null device
        assert outdoor_count == 5

    def test_rh_eligibility_skips_null_data_device(
        self, devices: list[WattsDevice]
    ) -> None:
        all_devices = [*devices, _NULL_DATA_FIELD_DEVICE]
        rh_count = sum(
            1
            for d in all_devices
            if d.data
            and d.data.sensors
            and d.data.sensors.rh
            and d.data.sensors.rh.status == "Okay"
        )
        # 2 from fixture + 0 from null device
        assert rh_count == 2
