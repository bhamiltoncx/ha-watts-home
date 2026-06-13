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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    HA_TO_WATTS_MODE,
    MODEL_NAMES,
    WATTS_TO_HA_ACTION,
    WATTS_TO_HA_MODE,
)
from .coordinator import WattsDataUpdateCoordinator
from .models import WattsDevice

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


def device_hvac_modes(device: WattsDevice) -> list[HVACMode]:
    if device.data is None or device.data.mode is None:
        return [HVACMode.OFF]
    return [
        _HA_MODE_MAP[ha]
        for w in device.data.mode.enum
        if (ha := WATTS_TO_HA_MODE.get(w)) is not None and ha in _HA_MODE_MAP
    ]


def device_hvac_mode(device: WattsDevice) -> HVACMode:
    if device.data is None or device.data.mode is None:
        return HVACMode.OFF
    ha = WATTS_TO_HA_MODE.get(device.data.mode.val, "off")
    # "Emer" maps to "emergency_heat" which has no HVACMode — fall back to HEAT
    return _HA_MODE_MAP.get(ha, HVACMode.HEAT)


def device_hvac_action(device: WattsDevice) -> HVACAction | None:
    if device.data is None or device.data.state is None:
        return None
    ha = WATTS_TO_HA_ACTION.get(device.data.state.op)
    if ha is None:
        return None
    return _HA_ACTION_MAP.get(ha)


def device_current_temperature(device: WattsDevice) -> float | None:
    if device.data is None or device.data.sensors is None:
        return None
    room = device.data.sensors.room
    if room is None:
        return None
    return room.val if room.status == "Okay" else None


def device_current_humidity(device: WattsDevice) -> float | None:
    if device.data is None or device.data.sensors is None:
        return None
    rh = device.data.sensors.rh
    return rh.val if rh and rh.status == "Okay" else None


def device_target_temperature(device: WattsDevice) -> float | None:
    """Single setpoint — used in heat or cool mode."""
    mode = device_hvac_mode(device)
    if device.data is None or device.data.target is None:
        return None
    if mode == HVACMode.COOL:
        return device.data.target.cool
    return device.data.target.heat


def device_target_temp_high(device: WattsDevice) -> float | None:
    """Cool setpoint for heat_cool mode."""
    if device.data is None or device.data.target is None:
        return None
    return device.data.target.cool


def device_target_temp_low(device: WattsDevice) -> float | None:
    """Heat setpoint for heat_cool mode."""
    if device.data is None or device.data.target is None:
        return None
    return device.data.target.heat


def device_temperature_unit(device: WattsDevice) -> str:
    if device.data is None or device.data.temp_units is None:
        return UnitOfTemperature.CELSIUS
    return (
        UnitOfTemperature.FAHRENHEIT
        if device.data.temp_units.val == "F"
        else UnitOfTemperature.CELSIUS
    )


def device_supported_features(device: WattsDevice) -> ClimateEntityFeature:
    features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    if HVACMode.HEAT_COOL in device_hvac_modes(device):
        features |= ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    if device.data and device.data.fan and device.data.fan.enum:
        features |= ClimateEntityFeature.FAN_MODE
    return features


def device_schedule_active(device: WattsDevice) -> bool:
    if device.data is None or device.data.sched_enable is None:
        return False
    return device.data.sched_enable.val.lower() in ("on", "enabled")


# ---------------------------------------------------------------------------
# HA platform setup
# ---------------------------------------------------------------------------


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WattsDataUpdateCoordinator = entry.runtime_data
    known_entity_ids: set[str] = set()

    @callback
    def _async_add_new() -> None:
        new: list[ClimateEntity] = []
        for device_id, device in coordinator.data.items():
            if device_id not in known_entity_ids:
                known_entity_ids.add(device_id)
                new.append(WattsClimateEntity(coordinator, device_id))

            floor_uid = f"{device_id}_floor"
            if floor_uid not in known_entity_ids and _has_floor(device):
                known_entity_ids.add(floor_uid)
                new.append(WattsFloorClimateEntity(coordinator, device_id))

        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
    _async_add_new()


def _has_floor(device: WattsDevice) -> bool:
    return (
        device.data is not None
        and device.data.sensors is not None
        and device.data.sensors.floor is not None
        and device.data.sensors.floor.status == "Okay"
        and device.data.schedule is not None
        and device.data.schedule.floor is not None
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
        device_id: str,
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = device_id
        device = coordinator.data[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            model=MODEL_NAMES.get(
                device.model_number, f"Tekmar WiFi Thermostat {device.model_number}"
            ),
            manufacturer="Watts Home",
        )

    def _device(self) -> WattsDevice:
        return self.coordinator.data[self._device_id]  # KeyError → available=False

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        try:
            return self._device().is_connected
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
        if self.hvac_mode == HVACMode.HEAT_COOL:
            return None
        return device_target_temperature(self._device())

    @property
    def target_temperature_high(self) -> float | None:
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return device_target_temp_high(self._device())

    @property
    def target_temperature_low(self) -> float | None:
        if self.hvac_mode != HVACMode.HEAT_COOL:
            return None
        return device_target_temp_low(self._device())

    @property
    def min_temp(self) -> float:
        d = self._device()
        return d.data.target.min if d.data and d.data.target else 40.0

    @property
    def max_temp(self) -> float:
        d = self._device()
        return d.data.target.max if d.data and d.data.target else 95.0

    @property
    def target_temperature_step(self) -> float:
        d = self._device()
        return d.data.target.steps if d.data and d.data.target else 1.0

    @property
    def temperature_unit(self) -> str:
        return device_temperature_unit(self._device())

    @property
    def fan_mode(self) -> str | None:
        d = self._device()
        return d.data.fan.val if d.data and d.data.fan else None

    @property
    def fan_modes(self) -> list[str] | None:
        d = self._device()
        return d.data.fan.enum if d.data and d.data.fan else None

    @property
    def supported_features(self) -> ClimateEntityFeature:
        return device_supported_features(self._device())

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        watts_mode = HA_TO_WATTS_MODE[hvac_mode]
        client = await self.coordinator.async_get_client()
        await client.set_mode(self._device_id, watts_mode)

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.mode:
                d.data.mode.val = watts_mode

        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
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

        current_heat = device.data.target.heat if device.data and device.data.target and device.data.target.heat is not None else 40.0
        current_cool = device.data.target.cool if device.data and device.data.target and device.data.target.cool is not None else 95.0

        if ATTR_TARGET_TEMP_HIGH in kwargs or ATTR_TARGET_TEMP_LOW in kwargs:
            heat = kwargs.get(ATTR_TARGET_TEMP_LOW, current_heat)
            cool = kwargs.get(ATTR_TARGET_TEMP_HIGH, current_cool)
        else:
            temp = kwargs.get(ATTR_TEMPERATURE)
            mode = device_hvac_mode(device)
            if mode == HVACMode.COOL:
                heat, cool = current_heat, temp
            else:
                heat, cool = temp, current_cool

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.target:
                d.data.target.heat = heat
                d.data.target.cool = cool

        await client.set_temperature(self._device_id, sched, heat, cool)
        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
        await self.coordinator.async_request_refresh()

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        client = await self.coordinator.async_get_client()
        await client.set_fan_mode(self._device_id, fan_mode)

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.fan:
                d.data.fan.val = fan_mode

        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
        await self.coordinator.async_request_refresh()


# ---------------------------------------------------------------------------
# Floor heating climate entity
# ---------------------------------------------------------------------------


class WattsFloorClimateEntity(
    CoordinatorEntity[WattsDataUpdateCoordinator], ClimateEntity
):
    """Heat-only climate entity for radiant floor heating.

    Shows floor slab temperature and the occupied floor minimum
    (Schedule.Floor.W) as the target. Set target to 0 to disable.
    """

    _attr_has_entity_name = True
    _attr_translation_key = "floor"
    _attr_hvac_modes = [HVACMode.HEAT]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_floor"
        device = coordinator.data[device_id]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name=device.name,
            model=MODEL_NAMES.get(
                device.model_number,
                f"Tekmar WiFi Thermostat {device.model_number}",
            ),
            manufacturer="Watts Home",
        )

    def _device(self) -> WattsDevice:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        try:
            d = self._device()
            s = d.data.sensors if d.data else None
            return (
                d.is_connected
                and s is not None
                and s.floor is not None
                and s.floor.status == "Okay"
            )
        except KeyError:
            return False

    @property
    def hvac_mode(self) -> HVACMode:
        return HVACMode.HEAT

    @property
    def hvac_action(self) -> HVACAction:
        d = self._device()
        if (
            d.data
            and d.data.mode
            and d.data.sensors
            and d.data.sensors.floor
            and d.data.schedule
            and d.data.schedule.floor
        ):
            mode = d.data.mode.val
            if mode not in ("Heat", "Auto", "Emer"):
                return HVACAction.IDLE
            target = d.data.schedule.floor.w
            current = d.data.sensors.floor.val
            if target > 0 and current < target:
                return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        d = self._device()
        if d.data and d.data.sensors and d.data.sensors.floor:
            f = d.data.sensors.floor
            return f.val if f.status == "Okay" else None
        return None

    @property
    def target_temperature(self) -> float | None:
        d = self._device()
        if d.data and d.data.schedule and d.data.schedule.floor:
            return d.data.schedule.floor.w
        return None

    @property
    def min_temp(self) -> float:
        return 0

    @property
    def max_temp(self) -> float:
        d = self._device()
        if d.data and d.data.schedule:
            return d.data.schedule.floor_max
        return 85.0

    @property
    def target_temperature_step(self) -> float:
        return 1.0

    @property
    def temperature_unit(self) -> str:
        d = self._device()
        if d.data and d.data.temp_units and d.data.temp_units.val == "F":
            return UnitOfTemperature.FAHRENHEIT
        return UnitOfTemperature.CELSIUS

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        pass

    async def async_set_temperature(self, **kwargs: Any) -> None:
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        device = self._device()
        current_a = 0.0
        if device.data and device.data.schedule and device.data.schedule.floor:
            current_a = device.data.schedule.floor.a

        client = await self.coordinator.async_get_client()
        await client.set_floor_min(self._device_id, temp, current_a)

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.schedule and d.data.schedule.floor:
                d.data.schedule.floor.w = temp

        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
        await self.coordinator.async_request_refresh()
