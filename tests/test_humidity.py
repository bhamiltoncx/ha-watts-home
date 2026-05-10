"""Tests for humidity control features (humidifier setpoint on climate, dehumidifier setpoint number)."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from homeassistant.components.climate import ClimateEntityFeature

from custom_components.watts_home.models import WattsDevice

_ROOT = Path(__file__).parent.parent / "custom_components" / "watts_home"
_FIXTURE = Path(__file__).parent / "fixtures" / "devices.json"


def _load(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_const = _load("custom_components.watts_home.const", _ROOT / "const.py")
_climate = _load("custom_components.watts_home.climate", _ROOT / "climate.py")

device_target_humidity = _climate.device_target_humidity  # type: ignore[attr-defined]
device_min_humidity = _climate.device_min_humidity  # type: ignore[attr-defined]
device_max_humidity = _climate.device_max_humidity  # type: ignore[attr-defined]
device_supported_features = _climate.device_supported_features  # type: ignore[attr-defined]


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


# ---------------------------------------------------------------------------
# 563 — has Hum and Dehum data
# ---------------------------------------------------------------------------


class TestModel563Humidity:
    def test_target_humidity_from_hum_val(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert device_target_humidity(d) == 24.0

    def test_min_humidity_from_hum_min(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert device_min_humidity(d) == 10.0

    def test_max_humidity_from_hum_max(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert device_max_humidity(d) == 80.0

    def test_supported_features_includes_target_humidity(
        self, devices: list[WattsDevice]
    ) -> None:
        d = _by_name(devices, "Living")
        assert device_supported_features(d) & ClimateEntityFeature.TARGET_HUMIDITY

    def test_dehum_val(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data is not None
        assert d.data.dehum is not None
        assert d.data.dehum.val == 60.0

    def test_dehum_range(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data is not None
        assert d.data.dehum is not None
        assert d.data.dehum.min == 20.0
        assert d.data.dehum.max == 90.0
        assert d.data.dehum.steps == 1.0


# ---------------------------------------------------------------------------
# 561 and 562 — no humidity control
# ---------------------------------------------------------------------------


class TestNoHumidityControl:
    def test_561_no_target_humidity(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_target_humidity(d) is None

    def test_562_no_target_humidity(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        assert device_target_humidity(d) is None

    def test_561_no_target_humidity_feature(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert not (device_supported_features(d) & ClimateEntityFeature.TARGET_HUMIDITY)

    def test_562_no_target_humidity_feature(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        assert not (device_supported_features(d) & ClimateEntityFeature.TARGET_HUMIDITY)

    def test_561_min_humidity_default(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_min_humidity(d) == 0.0

    def test_561_max_humidity_default(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_max_humidity(d) == 100.0


# ---------------------------------------------------------------------------
# Null-data robustness
# ---------------------------------------------------------------------------


_NULL_DATA_DEVICE: WattsDevice = WattsDevice.model_validate(
    {
        "deviceId": "null-hum-test",
        "name": "Null Hum Device",
        "modelNumber": "561",
        "isConnected": False,
        "data": None,
    }
)


class TestNullDataHumidity:
    def test_target_humidity_returns_none(self) -> None:
        assert device_target_humidity(_NULL_DATA_DEVICE) is None

    def test_min_humidity_returns_default(self) -> None:
        assert device_min_humidity(_NULL_DATA_DEVICE) == 0.0

    def test_max_humidity_returns_default(self) -> None:
        assert device_max_humidity(_NULL_DATA_DEVICE) == 100.0

    def test_supported_features_no_target_humidity(self) -> None:
        feats = device_supported_features(_NULL_DATA_DEVICE)
        assert not (feats & ClimateEntityFeature.TARGET_HUMIDITY)


# ---------------------------------------------------------------------------
# Model parsing — Hum/Dehum fields round-trip
# ---------------------------------------------------------------------------


class TestHumModelParsing:
    def test_hum_and_dehum_parse_from_fixture(self, devices: list[WattsDevice]) -> None:
        d = _by_name(devices, "Living")
        assert d.data is not None
        assert d.data.hum is not None
        assert d.data.hum.val == 24.0
        assert d.data.hum.min == 10.0
        assert d.data.hum.max == 80.0
        assert d.data.hum.steps == 1.0

    def test_no_hum_for_561(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert d.data is not None
        assert d.data.hum is None
        assert d.data.dehum is None

    def test_no_hum_for_562(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        assert d.data is not None
        assert d.data.hum is None
        assert d.data.dehum is None
