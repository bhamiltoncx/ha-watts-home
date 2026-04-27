"""Unit tests for sensor.py using real fixture data."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).parent.parent / "custom_components" / "watts_home"
_FIXTURE = Path(__file__).parent / "fixtures" / "devices.json"


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_const = _load("custom_components.watts_home.const", _ROOT / "const.py")
_sensor_mod = _load("custom_components.watts_home.sensor", _ROOT / "sensor.py")


@pytest.fixture(scope="module")
def devices() -> list[dict[str, Any]]:
    raw = json.loads(_FIXTURE.read_text())
    return list(raw["body"])  # type: ignore[return-value]


def _by_model(devices: list[dict[str, Any]], model: str) -> dict[str, Any]:
    for d in devices:
        if d["modelNumber"] == model:
            return d
    raise KeyError(model)


def _by_name(devices: list[dict[str, Any]], name: str) -> dict[str, Any]:
    for d in devices:
        if d["name"] == name:
            return d
    raise KeyError(name)


class TestOutdoorSensorEligibility:
    def test_562_has_outdoor_okay(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "562")
        outdoor = d["data"]["Sensors"]["Outdoor"]
        assert outdoor["Status"] == "Okay"

    def test_561_outdoor_absent(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        outdoor = d["data"]["Sensors"]["Outdoor"]
        assert outdoor["Status"] != "Okay"

    def test_563_has_outdoor_okay(self, devices: list[dict[str, Any]]) -> None:
        d = _by_name(devices, "Living")
        outdoor = d["data"]["Sensors"]["Outdoor"]
        assert outdoor["Status"] == "Okay"


class TestHumiditySensorEligibility:
    def test_563_living_has_rh_okay(self, devices: list[dict[str, Any]]) -> None:
        d = _by_name(devices, "Living")
        rh = d["data"]["Sensors"]["RH"]
        assert rh["Status"] == "Okay"
        assert isinstance(rh["Val"], (int, float))

    def test_562_no_rh_okay(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "562")
        rh = d["data"]["Sensors"].get("RH", {})
        # Either absent or not Okay
        assert rh.get("Status") != "Okay"

    def test_561_no_rh(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        rh = d["data"]["Sensors"].get("RH", {})
        assert rh.get("Status") != "Okay"


class TestSensorCounts:
    """Verify the expected number of sensor entities created from the fixture."""

    def test_outdoor_sensor_count(self, devices: list[dict[str, Any]]) -> None:
        outdoor_count = sum(
            1
            for d in devices
            if d["data"]["Sensors"].get("Outdoor", {}).get("Status") == "Okay"
        )
        # From fixture: 4 devices (3x562, 1x563) have Outdoor Status=Okay
        assert outdoor_count == 4

    def test_humidity_sensor_count(self, devices: list[dict[str, Any]]) -> None:
        rh_count = sum(
            1
            for d in devices
            if d["data"]["Sensors"].get("RH", {}).get("Status") == "Okay"
        )
        # From fixture: only "Living" (563) has RH Status=Okay
        assert rh_count == 1
