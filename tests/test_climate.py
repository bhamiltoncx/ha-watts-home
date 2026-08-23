"""Unit tests for climate.py mapping helpers using real fixture data."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from homeassistant.components.climate import ClimateEntityFeature, HVACAction, HVACMode
from homeassistant.const import UnitOfTemperature

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
device_min_temp = _climate.device_min_temp  # type: ignore[attr-defined]
device_max_temp = _climate.device_max_temp  # type: ignore[attr-defined]
device_target_temp_step = _climate.device_target_temp_step  # type: ignore[attr-defined]
WattsClimateEntity = _climate.WattsClimateEntity  # type: ignore[attr-defined]


@pytest.fixture(scope="module")
def devices() -> list[WattsDevice]:
    raw = json.loads(_FIXTURE.read_text())["body"]
    return [WattsDevice.model_validate(d) for d in raw]


def _by_model(devices: list[WattsDevice], model: str) -> WattsDevice:
    for d in devices:
        if d.model_number == model:
            return d
    raise KeyError(model)


# ---------------------------------------------------------------------------
# Model 561 — heat-only, no fan, Cool = null
# ---------------------------------------------------------------------------


class TestModel561:
    def test_hvac_modes(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        modes = device_hvac_modes(d)
        assert HVACMode.HEAT in modes
        assert HVACMode.OFF in modes
        assert HVACMode.COOL not in modes
        assert HVACMode.HEAT_COOL not in modes

    def test_hvac_mode(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_hvac_mode(d) == HVACMode.HEAT

    def test_hvac_action_heating(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_hvac_action(d) == HVACAction.HEATING

    def test_current_temperature(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        temp = device_current_temperature(d)
        assert temp is not None
        assert 40.0 <= temp <= 100.0

    def test_no_humidity(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_current_humidity(d) is None

    def test_target_temperature(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        temp = device_target_temperature(d)
        assert temp is not None

    def test_temperature_unit_fahrenheit(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_temperature_unit(d) == UnitOfTemperature.FAHRENHEIT

    def test_supported_features_no_fan_no_range(
        self, devices: list[WattsDevice]
    ) -> None:
        d = _by_model(devices, "561")
        feats = device_supported_features(d)
        assert feats & ClimateEntityFeature.TARGET_TEMPERATURE
        assert feats & ClimateEntityFeature.TURN_ON
        assert feats & ClimateEntityFeature.TURN_OFF
        assert not (feats & ClimateEntityFeature.FAN_MODE)
        assert not (feats & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE)

    def test_schedule_inactive(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "561")
        assert device_schedule_active(d) is False


# ---------------------------------------------------------------------------
# Model 562 — heat/cool/auto, fan, Cool = 95 (sentinel)
# ---------------------------------------------------------------------------


class TestModel562:
    def test_hvac_modes_includes_auto(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        modes = device_hvac_modes(d)
        assert HVACMode.HEAT in modes
        assert HVACMode.COOL in modes
        assert HVACMode.HEAT_COOL in modes
        assert HVACMode.OFF in modes

    def test_supported_features_has_fan_and_range(
        self, devices: list[WattsDevice]
    ) -> None:
        d = _by_model(devices, "562")
        feats = device_supported_features(d)
        assert feats & ClimateEntityFeature.FAN_MODE
        assert feats & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE

    def test_target_temp_high_cool_sentinel(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        # API returns 95 as "not configured" — we expose it as-is
        high = device_target_temp_high(d)
        assert high == 95.0

    def test_target_temp_low_heat(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        low = device_target_temp_low(d)
        assert low is not None

    def test_hvac_action_off_or_idle(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "562")
        action = device_hvac_action(d)
        assert action in (
            HVACAction.OFF,
            HVACAction.IDLE,
            HVACAction.HEATING,
            HVACAction.COOLING,
        )


# ---------------------------------------------------------------------------
# Model names
# ---------------------------------------------------------------------------


class TestModelNames:
    def test_561_model_name(self, devices: list[WattsDevice]) -> None:
        from custom_components.watts_home.const import MODEL_NAMES  # type: ignore[import]

        assert MODEL_NAMES["561"] == "Tekmar WiFi Thermostat 561"

    def test_562_model_name(self, devices: list[WattsDevice]) -> None:
        from custom_components.watts_home.const import MODEL_NAMES  # type: ignore[import]

        assert MODEL_NAMES["562"] == "Tekmar WiFi Thermostat 562"

    def test_unknown_model_fallback(self, devices: list[WattsDevice]) -> None:
        from custom_components.watts_home.const import MODEL_NAMES  # type: ignore[import]

        model_num = "999"
        name = MODEL_NAMES.get(model_num, f"Tekmar WiFi Thermostat {model_num}")
        assert name == "Tekmar WiFi Thermostat 999"


# ---------------------------------------------------------------------------
# Model 563
# ---------------------------------------------------------------------------


class TestModel563:
    def test_hvac_modes_includes_auto(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "563")
        modes = device_hvac_modes(d)
        assert HVACMode.HEAT_COOL in modes

    def test_supported_features_has_fan(self, devices: list[WattsDevice]) -> None:
        d = _by_model(devices, "563")
        feats = device_supported_features(d)
        assert feats & ClimateEntityFeature.FAN_MODE


class TestEmergencyHeat:
    """Emer mode is not a valid HVACMode — it should be filtered from modes
    but not crash device_hvac_mode() when the device is in Emer."""

    def test_emer_filtered_from_modes_list(self) -> None:
        d = WattsDevice.model_validate(
            {
                "deviceId": "t",
                "name": "T",
                "modelNumber": "563",
                "isConnected": True,
                "data": {
                    "Sensors": {"Room": {"Val": 70, "Status": "Okay"}},
                    "State": {"Op": "Heat"},
                    "Mode": {
                        "Val": "Heat",
                        "Enum": ["Off", "Heat", "Cool", "Auto", "Emer"],
                    },
                    "Target": {
                        "Heat": 70,
                        "Cool": 80,
                        "Min": 40,
                        "Max": 95,
                        "Steps": 1,
                    },
                    "TempUnits": {"Val": "F"},
                    "SchedEnable": {"Val": "Off"},
                },
            }
        )
        modes = device_hvac_modes(d)
        # "Emer" maps to "emergency_heat" which has no HVACMode → filtered out
        for m in modes:
            assert isinstance(m, HVACMode)

    def test_device_in_emer_mode_falls_back_to_heat(self) -> None:
        d = WattsDevice.model_validate(
            {
                "deviceId": "t",
                "name": "T",
                "modelNumber": "563",
                "isConnected": True,
                "data": {
                    "Sensors": {"Room": {"Val": 70, "Status": "Okay"}},
                    "State": {"Op": "Heat"},
                    "Mode": {"Val": "Emer", "Enum": ["Off", "Heat", "Emer"]},
                    "Target": {
                        "Heat": 70,
                        "Cool": 80,
                        "Min": 40,
                        "Max": 95,
                        "Steps": 1,
                    },
                    "TempUnits": {"Val": "F"},
                    "SchedEnable": {"Val": "Off"},
                },
            }
        )
        mode = device_hvac_mode(d)
        assert mode == HVACMode.HEAT


# ---------------------------------------------------------------------------
# Null-data robustness
# ---------------------------------------------------------------------------

_NULL_DEVICE: WattsDevice = WattsDevice.model_validate(
    {
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
)

_NULL_DATA_FIELD_DEVICE: WattsDevice = WattsDevice.model_validate(
    {
        "deviceId": "null-data-field-test",
        "name": "Null Data Field Device",
        "modelNumber": "561",
        "isConnected": False,
        "data": None,
    }
)


class TestNullDataField:
    """Guards against device.data itself being None."""

    def test_hvac_modes_returns_off(self) -> None:
        assert device_hvac_modes(_NULL_DATA_FIELD_DEVICE) == [HVACMode.OFF]

    def test_hvac_mode_returns_off(self) -> None:
        assert device_hvac_mode(_NULL_DATA_FIELD_DEVICE) == HVACMode.OFF

    def test_hvac_action_returns_none(self) -> None:
        assert device_hvac_action(_NULL_DATA_FIELD_DEVICE) is None

    def test_current_temperature_returns_none(self) -> None:
        assert device_current_temperature(_NULL_DATA_FIELD_DEVICE) is None

    def test_current_humidity_returns_none(self) -> None:
        assert device_current_humidity(_NULL_DATA_FIELD_DEVICE) is None

    def test_target_temperature_returns_none(self) -> None:
        assert device_target_temperature(_NULL_DATA_FIELD_DEVICE) is None

    def test_target_temp_high_returns_none(self) -> None:
        assert device_target_temp_high(_NULL_DATA_FIELD_DEVICE) is None

    def test_target_temp_low_returns_none(self) -> None:
        assert device_target_temp_low(_NULL_DATA_FIELD_DEVICE) is None

    def test_temperature_unit_returns_celsius(self) -> None:
        assert (
            device_temperature_unit(_NULL_DATA_FIELD_DEVICE)
            == UnitOfTemperature.CELSIUS
        )

    def test_supported_features_does_not_raise(self) -> None:
        feats = device_supported_features(_NULL_DATA_FIELD_DEVICE)
        assert feats & ClimateEntityFeature.TURN_ON
        assert feats & ClimateEntityFeature.TURN_OFF

    def test_schedule_active_returns_false(self) -> None:
        assert device_schedule_active(_NULL_DATA_FIELD_DEVICE) is False


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
        assert device_temperature_unit(_NULL_DEVICE) == UnitOfTemperature.CELSIUS

    def test_supported_features_does_not_raise(self) -> None:
        feats = device_supported_features(_NULL_DEVICE)
        assert feats & ClimateEntityFeature.TURN_ON
        assert feats & ClimateEntityFeature.TURN_OFF

    def test_schedule_active_returns_false(self) -> None:
        assert device_schedule_active(_NULL_DEVICE) is False


# ---------------------------------------------------------------------------
# Setpoint bounds — Target present but without Min/Max/Steps (issue #14)
# ---------------------------------------------------------------------------


def _bounds_device(
    *,
    target: dict[str, float] | None = None,
    schedule: dict[str, float] | None = None,
    mode: str = "Heat",
    units: str = "F",
) -> WattsDevice:
    data: dict[str, object] = {
        "Mode": {"Val": mode, "Enum": ["Off", "Heat", "Cool", "Auto"]},
        "TempUnits": {"Val": units},
    }
    if target is not None:
        data["Target"] = target
    if schedule is not None:
        data["Schedule"] = schedule
    return WattsDevice.model_validate(
        {
            "deviceId": "bounds-1",
            "name": "Bounds",
            "modelNumber": "170",
            "isConnected": True,
            "data": data,
        }
    )


class TestSetpointBounds:
    """A Tekmar 170 returns Target without Min/Max/Steps (issue #14)."""

    def test_target_range_is_used_when_present(self) -> None:
        d = _bounds_device(
            target={"Heat": 68.0, "Min": 40.0, "Max": 95.0, "Steps": 1.0}
        )
        assert device_min_temp(d) == 40.0
        assert device_max_temp(d) == 95.0
        assert device_target_temp_step(d) == 1.0

    def test_heat_mode_falls_back_to_schedule_heat_range(self) -> None:
        d = _bounds_device(
            target={"Heat": 68.0},
            schedule={"HeatMin": 50.0, "HeatMax": 90.0},
        )
        assert device_min_temp(d) == 50.0
        assert device_max_temp(d) == 90.0

    def test_cool_mode_falls_back_to_schedule_cool_range(self) -> None:
        d = _bounds_device(
            target={"Cool": 74.0},
            schedule={"CoolMin": 60.0, "CoolMax": 99.0},
            mode="Cool",
        )
        assert device_min_temp(d) == 60.0
        assert device_max_temp(d) == 99.0

    def test_heat_cool_mode_spans_both_schedule_ranges(self) -> None:
        d = _bounds_device(
            target={"Heat": 68.0, "Cool": 74.0},
            schedule={
                "HeatMin": 50.0,
                "HeatMax": 90.0,
                "CoolMin": 60.0,
                "CoolMax": 99.0,
            },
            mode="Auto",
        )
        assert device_min_temp(d) == 50.0
        assert device_max_temp(d) == 99.0

    def test_fahrenheit_device_without_schedule_uses_converted_ha_defaults(
        self,
    ) -> None:
        d = _bounds_device(target={"Heat": 68.0})
        assert device_min_temp(d) == pytest.approx(44.6)
        assert device_max_temp(d) == pytest.approx(95.0)

    def test_celsius_device_without_schedule_uses_ha_defaults(self) -> None:
        d = _bounds_device(target={"Heat": 20.0}, units="C")
        assert device_min_temp(d) == pytest.approx(7.0)
        assert device_max_temp(d) == pytest.approx(35.0)

    def test_schedule_without_bounds_uses_ha_defaults(self) -> None:
        d = _bounds_device(target={"Heat": 68.0}, schedule={"SchedActive": 1})
        assert device_min_temp(d) == pytest.approx(44.6)
        assert device_max_temp(d) == pytest.approx(95.0)

    def test_step_falls_back_to_one_when_absent(self) -> None:
        d = _bounds_device(target={"Heat": 68.0})
        assert device_target_temp_step(d) == 1.0

    def test_null_data_still_yields_numeric_bounds(self) -> None:
        assert isinstance(device_min_temp(_NULL_DATA_FIELD_DEVICE), float)
        assert isinstance(device_max_temp(_NULL_DATA_FIELD_DEVICE), float)
        assert isinstance(device_target_temp_step(_NULL_DATA_FIELD_DEVICE), float)

    def test_null_target_still_yields_numeric_bounds(self) -> None:
        assert isinstance(device_min_temp(_NULL_DEVICE), float)
        assert isinstance(device_max_temp(_NULL_DEVICE), float)
        assert isinstance(device_target_temp_step(_NULL_DEVICE), float)


class TestEntitySetpointBounds:
    """HA core compares `check_temp < entity.min_temp`, so None is a TypeError."""

    @staticmethod
    def _stub(device: WattsDevice) -> SimpleNamespace:
        return SimpleNamespace(_device=lambda: device)

    def test_min_temp_is_never_none_without_target_range(self) -> None:
        stub = self._stub(_bounds_device(target={"Heat": 68.0}))
        assert isinstance(WattsClimateEntity.min_temp.fget(stub), float)

    def test_max_temp_is_never_none_without_target_range(self) -> None:
        stub = self._stub(_bounds_device(target={"Heat": 68.0}))
        assert isinstance(WattsClimateEntity.max_temp.fget(stub), float)

    def test_target_temperature_step_is_never_none_without_target_range(self) -> None:
        stub = self._stub(_bounds_device(target={"Heat": 68.0}))
        assert isinstance(WattsClimateEntity.target_temperature_step.fget(stub), float)
