"""Climate platform for the Watts Home (Tekmar) integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, HA_TO_WATTS_MODE, MODEL_NAMES, WATTS_TO_HA_ACTION, WATTS_TO_HA_MODE
from .coordinator import WattsDataUpdateCoordinator

# ---------------------------------------------------------------------------
# Pure data-mapping helpers (no HA dependency — fully unit-testable)
# ---------------------------------------------------------------------------

_HA_MODE_MAP: dict[str, HVACMode] = {
    "heat": HVACMode.HEAT,
    "cool": HVACMode.COOL,
    "heat_cool": HVACMode.HEAT_COOL,
    "off": HVACMode.OFF,
    "fan_only": HVACMode.FAN_ONLY,
    "dry": HVACMode.DRY,
}

_HA_ACTION_MAP: dict[str, HVACAction] = {
    "heating": HVACAction.HEATING,
    "cooling": HVACAction.COOLING,
    "off": HVACAction.OFF,
    "idle": HVACAction.IDLE,
}


def device_hvac_modes(device: dict[str, Any]) -> list[HVACMode]:
    watts_enums: list[str] = device["data"]["Mode"]["Enum"]
    return [
        _HA_MODE_MAP[ha]
        for w in watts_enums
        if (ha := WATTS_TO_HA_MODE.get(w)) is not None and ha in _HA_MODE_MAP
    ]


def device_hvac_mode(device: dict[str, Any]) -> HVACMode:
    ha = WATTS_TO_HA_MODE.get(device["data"]["Mode"]["Val"], "off")
    return _HA_MODE_MAP.get(ha, HVACMode.OFF)


def device_hvac_action(device: dict[str, Any]) -> HVACAction | None:
    op: str = device["data"]["State"]["Op"]
    ha = WATTS_TO_HA_ACTION.get(op)
    if ha is None:
        return None
    return _HA_ACTION_MAP.get(ha)


def device_current_temperature(device: dict[str, Any]) -> float | None:
    room = device["data"]["Sensors"]["Room"]
    if room.get("Status") == "Okay":
        return float(room["Val"])
    return None


def device_current_humidity(device: dict[str, Any]) -> float | None:
    rh = device["data"]["Sensors"].get("RH")
    if rh and rh.get("Status") == "Okay":
        return float(rh["Val"])
    return None


def device_target_temperature(device: dict[str, Any]) -> float | None:
    """Single setpoint — used in heat or cool mode."""
    mode = device_hvac_mode(device)
    target = device["data"]["Target"]
    if mode == HVACMode.COOL:
        v = target.get("Cool")
        return float(v) if v is not None else None
    return float(target["Heat"]) if target.get("Heat") is not None else None


def device_target_temp_high(device: dict[str, Any]) -> float | None:
    """Cool setpoint for heat_cool mode."""
    v = device["data"]["Target"].get("Cool")
    return float(v) if v is not None else None


def device_target_temp_low(device: dict[str, Any]) -> float | None:
    """Heat setpoint for heat_cool mode."""
    v = device["data"]["Target"].get("Heat")
    return float(v) if v is not None else None


def device_temperature_unit(device: dict[str, Any]) -> str:
    val = device["data"]["TempUnits"]["Val"]
    return UnitOfTemperature.FAHRENHEIT if val == "F" else UnitOfTemperature.CELSIUS


def device_supported_features(device: dict[str, Any]) -> ClimateEntityFeature:
    features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    modes = device_hvac_modes(device)
    if HVACMode.HEAT_COOL in modes:
        features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    fan = device["data"].get("Fan")
    if fan and fan.get("Enum"):
        features |= ClimateEntityFeature.FAN_MODE
    return features


def device_schedule_active(device: dict[str, Any]) -> bool:
    val: str = device["data"]["SchedEnable"]["Val"]
    return val.lower() in ("on", "enabled")


# ---------------------------------------------------------------------------
# HA platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WattsDataUpdateCoordinator = entry.runtime_data
    async_add_entities(
        WattsClimateEntity(coordinator, device)
        for device in coordinator.data
    )


# ---------------------------------------------------------------------------
# Entity
# ---------------------------------------------------------------------------


class WattsClimateEntity(CoordinatorEntity[WattsDataUpdateCoordinator], ClimateEntity):
    """Thermostat entity for a single Watts/Tekmar device."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(
        self,
        coordinator: WattsDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._device_id: str = device["deviceId"]
        self._attr_unique_id = self._device_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._device_id)},
            name=device["name"],
            model=MODEL_NAMES.get(device["modelNumber"], f"Tekmar WiFi Thermostat {device['modelNumber']}"),
            manufacturer="Watts Home",
        )

    def _device(self) -> dict[str, Any]:
        for d in self.coordinator.data:
            if d["deviceId"] == self._device_id:
                return d
        raise KeyError(self._device_id)

    @property
    def available(self) -> bool:
        try:
            return bool(self._device()["isConnected"])
        except KeyError:
            return False

    @property
    def hvac_modes(self) -> list[HVACMode]:
        return device_hvac_modes(self._device())

    @property
    def hvac_mode(self) -> HVACMode:
        return device_hvac_mode(self._device())

    @property
    def hvac_action(self) -> HVACAction | None:
        return device_hvac_action(self._device())

    @property
    def current_temperature(self) -> float | None:
        return device_current_temperature(self._device())

    @property
    def current_humidity(self) -> float | None:
        return device_current_humidity(self._device())

    @property
    def target_temperature(self) -> float | None:
        if HVACMode.HEAT_COOL in self.hvac_modes:
            return None
        return device_target_temperature(self._device())

    @property
    def target_temperature_high(self) -> float | None:
        if HVACMode.HEAT_COOL not in self.hvac_modes:
            return None
        return device_target_temp_high(self._device())

    @property
    def target_temperature_low(self) -> float | None:
        if HVACMode.HEAT_COOL not in self.hvac_modes:
            return None
        return device_target_temp_low(self._device())

    @property
    def min_temp(self) -> float:
        return float(self._device()["data"]["Target"]["Min"])

    @property
    def max_temp(self) -> float:
        return float(self._device()["data"]["Target"]["Max"])

    @property
    def target_temperature_step(self) -> float:
        return float(self._device()["data"]["Target"]["Steps"])

    @property
    def temperature_unit(self) -> str:
        return device_temperature_unit(self._device())

    @property
    def fan_mode(self) -> str | None:
        fan = self._device()["data"].get("Fan")
        return str(fan["Val"]) if fan else None

    @property
    def fan_modes(self) -> list[str] | None:
        fan = self._device()["data"].get("Fan")
        return list(fan["Enum"]) if fan else None

    @property
    def supported_features(self) -> ClimateEntityFeature:
        return device_supported_features(self._device())

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        watts_mode = HA_TO_WATTS_MODE[hvac_mode]
        client = await self.coordinator.async_get_client()
        await client.set_mode(self._device_id, watts_mode)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self) -> None:
        modes = [m for m in self.hvac_modes if m != HVACMode.OFF]
        if modes:
            await self.async_set_hvac_mode(modes[0])

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        device = self._device()
        sched = device_schedule_active(device)
        client = await self.coordinator.async_get_client()

        if ATTR_TARGET_TEMP_HIGH in kwargs or ATTR_TARGET_TEMP_LOW in kwargs:
            heat = kwargs.get(ATTR_TARGET_TEMP_LOW)
            cool = kwargs.get(ATTR_TARGET_TEMP_HIGH)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
            mode = device_hvac_mode(device)
            heat = temp if mode == HVACMode.HEAT else None
            cool = temp if mode == HVACMode.COOL else None

        await client.set_temperature(self._device_id, sched, heat, cool)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        client = await self.coordinator.async_get_client()
        await client.set_fan_mode(self._device_id, fan_mode)
        await self.coordinator.async_request_refresh()
