"""Unit tests for climate.py mapping helpers using real fixture data."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import UnitOfTemperature

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
_climate = _load("custom_components.watts_home.climate", _ROOT / "climate.py")

device_hvac_modes = _climate.device_hvac_modes  # type: ignore[attr-defined]
device_hvac_mode = _climate.device_hvac_mode  # type: ignore[attr-defined]
device_hvac_action = _climate.device_hvac_action  # type: ignore[attr-defined]
device_current_temperature = _climate.device_current_temperature  # type: ignore[attr-defined]
device_current_humidity = _climate.device_current_humidity  # type: ignore[attr-defined]
device_target_temperature = _climate.device_target_temperature  # type: ignore[attr-defined]
device_target_temp_high = _climate.device_target_temp_high  # type: ignore[attr-defined]
device_target_temp_low = _climate.device_target_temp_low  # type: ignore[attr-defined]
device_temperature_unit = _climate.device_temperature_unit  # type: ignore[attr-defined]
device_supported_features = _climate.device_supported_features  # type: ignore[attr-defined]
device_schedule_active = _climate.device_schedule_active  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def devices() -> list[dict[str, Any]]:
    raw = json.loads(_FIXTURE.read_text())
    return list(raw["body"])  # type: ignore[return-value]


def _by_model(devices: list[dict[str, Any]], model: str) -> dict[str, Any]:
    for d in devices:
        if d["modelNumber"] == model:
            return d
    raise KeyError(model)


# ---------------------------------------------------------------------------
# Model 561 — heat-only, no fan, Cool = null
# ---------------------------------------------------------------------------


class TestModel561:
    def test_hvac_modes(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        modes = device_hvac_modes(d)
        assert HVACMode.HEAT in modes
        assert HVACMode.OFF in modes
        assert HVACMode.COOL not in modes
        assert HVACMode.HEAT_COOL not in modes

    def test_hvac_mode(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        assert device_hvac_mode(d) == HVACMode.HEAT

    def test_hvac_action_heating(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        assert device_hvac_action(d) == HVACAction.HEATING

    def test_current_temperature(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        temp = device_current_temperature(d)
        assert temp is not None
        assert 40.0 <= temp <= 100.0

    def test_no_humidity(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        assert device_current_humidity(d) is None

    def test_target_temperature(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        temp = device_target_temperature(d)
        assert temp is not None

    def test_temperature_unit_fahrenheit(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        assert device_temperature_unit(d) == UnitOfTemperature.FAHRENHEIT

    def test_supported_features_no_fan_no_range(
        self, devices: list[dict[str, Any]]
    ) -> None:
        d = _by_model(devices, "561")
        feats = device_supported_features(d)
        assert feats & ClimateEntityFeature.TARGET_TEMPERATURE
        assert feats & ClimateEntityFeature.TURN_ON
        assert feats & ClimateEntityFeature.TURN_OFF
        assert not (feats & ClimateEntityFeature.FAN_MODE)
        assert not (feats & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE)

    def test_schedule_inactive(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "561")
        assert device_schedule_active(d) is False


# ---------------------------------------------------------------------------
# Model 562 — heat/cool/auto, fan, Cool = 95 (sentinel)
# ---------------------------------------------------------------------------


class TestModel562:
    def test_hvac_modes_includes_auto(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "562")
        modes = device_hvac_modes(d)
        assert HVACMode.HEAT in modes
        assert HVACMode.COOL in modes
        assert HVACMode.HEAT_COOL in modes
        assert HVACMode.OFF in modes

    def test_supported_features_has_fan_and_range(
        self, devices: list[dict[str, Any]]
    ) -> None:
        d = _by_model(devices, "562")
        feats = device_supported_features(d)
        assert feats & ClimateEntityFeature.FAN_MODE
        assert feats & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

    def test_target_temp_high_cool_sentinel(
        self, devices: list[dict[str, Any]]
    ) -> None:
        d = _by_model(devices, "562")
        # API returns 95 as "not configured" — we expose it as-is
        high = device_target_temp_high(d)
        assert high == 95.0

    def test_target_temp_low_heat(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "562")
        low = device_target_temp_low(d)
        assert low is not None

    def test_hvac_action_off_or_idle(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "562")
        action = device_hvac_action(d)
        assert action in (
            HVACAction.OFF,
            HVACAction.IDLE,
            HVACAction.HEATING,
            HVACAction.COOLING,
        )


# ---------------------------------------------------------------------------
# Model 563 — same capabilities as 562
# ---------------------------------------------------------------------------


class TestModelNames:
    def test_561_model_name(self, devices: list[dict[str, Any]]) -> None:
        from custom_components.watts_home.const import MODEL_NAMES  # type: ignore[import]

        assert MODEL_NAMES["561"] == "Tekmar WiFi Thermostat 561"

    def test_562_model_name(self, devices: list[dict[str, Any]]) -> None:
        from custom_components.watts_home.const import MODEL_NAMES  # type: ignore[import]

        assert MODEL_NAMES["562"] == "Tekmar WiFi Thermostat 562"

    def test_unknown_model_fallback(self, devices: list[dict[str, Any]]) -> None:
        from custom_components.watts_home.const import MODEL_NAMES  # type: ignore[import]

        model_num = "999"
        name = MODEL_NAMES.get(model_num, f"Tekmar WiFi Thermostat {model_num}")
        assert name == "Tekmar WiFi Thermostat 999"


class TestModel563:
    def test_hvac_modes_includes_auto(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "563")
        modes = device_hvac_modes(d)
        assert HVACMode.HEAT_COOL in modes

    def test_supported_features_has_fan(self, devices: list[dict[str, Any]]) -> None:
        d = _by_model(devices, "563")
        feats = device_supported_features(d)
        assert feats & ClimateEntityFeature.FAN_MODE


# ---------------------------------------------------------------------------
# Null-data robustness — all nullable top-level fields set to None
# ---------------------------------------------------------------------------

_NULL_DEVICE: dict[str, Any] = {
    "deviceId": "null-test",
    "name": "Null Device",
    "modelNumber": "561",
    "isConnected": False,
    "data": {
        "Mode": None,
        "State": None,
        "Sensors": None,
        "Target": None,
        "TempUnits": None,
        "SchedEnable": None,
    },
}


class TestNullData:
    def test_hvac_modes_returns_off(self) -> None:
        assert device_hvac_modes(_NULL_DEVICE) == [HVACMode.OFF]

    def test_hvac_mode_returns_off(self) -> None:
        assert device_hvac_mode(_NULL_DEVICE) == HVACMode.OFF

    def test_hvac_action_returns_none(self) -> None:
        assert device_hvac_action(_NULL_DEVICE) is None

    def test_current_temperature_returns_none(self) -> None:
        assert device_current_temperature(_NULL_DEVICE) is None

    def test_current_humidity_returns_none(self) -> None:
        assert device_current_humidity(_NULL_DEVICE) is None

    def test_target_temperature_returns_none(self) -> None:
        assert device_target_temperature(_NULL_DEVICE) is None

    def test_target_temp_high_returns_none(self) -> None:
        assert device_target_temp_high(_NULL_DEVICE) is None

    def test_target_temp_low_returns_none(self) -> None:
        assert device_target_temp_low(_NULL_DEVICE) is None

    def test_temperature_unit_returns_celsius_default(self) -> None:
        from homeassistant.const import UnitOfTemperature

        assert device_temperature_unit(_NULL_DEVICE) == UnitOfTemperature.CELSIUS

    def test_supported_features_does_not_raise(self) -> None:
        feats = device_supported_features(_NULL_DEVICE)
        assert feats & ClimateEntityFeature.TURN_ON
        assert feats & ClimateEntityFeature.TURN_OFF

    def test_schedule_active_returns_false(self) -> None:
        assert device_schedule_active(_NULL_DEVICE) is False
