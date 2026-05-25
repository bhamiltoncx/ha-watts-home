"""Sensor platform for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    EntityCategory,
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL_NAMES
from .coordinator import WattsDataUpdateCoordinator
from .models import WattsDevice


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WattsDataUpdateCoordinator = entry.runtime_data
    known_entity_ids: set[str] = set()

    @callback
    def _async_add_new() -> None:
        new: list[SensorEntity] = []
        for device_id, device in coordinator.data.items():
            s = device.data.sensors if device.data else None

            # Outdoor temperature
            if s and s.outdoor and s.outdoor.status == "Okay":
                uid = f"{device_id}_outdoor_temp"
                if uid not in known_entity_ids:
                    known_entity_ids.add(uid)
                    new.append(WattsOutdoorTempSensor(coordinator, device_id))

            # Humidity
            if s and s.rh and s.rh.status == "Okay":
                uid = f"{device_id}_humidity"
                if uid not in known_entity_ids:
                    known_entity_ids.add(uid)
                    new.append(WattsHumiditySensor(coordinator, device_id))

            # Floor temperature
            if s and s.floor and s.floor.status == "Okay":
                uid = f"{device_id}_floor_temp"
                if uid not in known_entity_ids:
                    known_entity_ids.add(uid)
                    new.append(WattsFloorTempSensor(coordinator, device_id))

            # Floor max (diagnostic)
            if (
                s
                and s.floor
                and s.floor.status == "Okay"
                and device.data
                and device.data.schedule
            ):
                uid = f"{device_id}_floor_max"
                if uid not in known_entity_ids:
                    known_entity_ids.add(uid)
                    new.append(WattsFloorMaxSensor(coordinator, device_id))

            # Energy heat today
            if (
                device.data
                and device.data.energy
                and device.data.energy.heat
                and device.data.energy.heat.daily
            ):
                uid = f"{device_id}_energy_heat_today"
                if uid not in known_entity_ids:
                    known_entity_ids.add(uid)
                    new.append(WattsEnergyHeatSensor(coordinator, device_id))

            # Energy cool today
            if (
                device.data
                and device.data.energy
                and device.data.energy.cool
                and device.data.energy.cool.daily
            ):
                uid = f"{device_id}_energy_cool_today"
                if uid not in known_entity_ids:
                    known_entity_ids.add(uid)
                    new.append(WattsEnergyCoolSensor(coordinator, device_id))

        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
    _async_add_new()


def _device_info(device: WattsDevice) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, device.device_id)},
        name=device.name,
        model=MODEL_NAMES.get(
            device.model_number, f"Tekmar WiFi Thermostat {device.model_number}"
        ),
        manufacturer="Watts Home",
    )


def _temp_unit(device: WattsDevice) -> str:
    unit = (
        device.data.temp_units.val if device.data and device.data.temp_units else None
    )
    return UnitOfTemperature.FAHRENHEIT if unit == "F" else UnitOfTemperature.CELSIUS


class _WattsSensor(CoordinatorEntity[WattsDataUpdateCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_device_info = _device_info(coordinator.data[device_id])

    def _device(self) -> WattsDevice:
        return self.coordinator.data[self._device_id]

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        try:
            return self._device().is_connected
        except KeyError:
            return False


class WattsOutdoorTempSensor(_WattsSensor):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "outdoor_temperature"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_outdoor_temp"
        self._attr_native_unit_of_measurement = _temp_unit(coordinator.data[device_id])

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
                and s.outdoor is not None
                and s.outdoor.status == "Okay"
            )
        except KeyError:
            return False

    @property
    def native_value(self) -> float | None:
        d = self._device()
        s = d.data.sensors if d.data else None
        if s and s.outdoor and s.outdoor.status == "Okay":
            return s.outdoor.val
        return None


class WattsHumiditySensor(_WattsSensor):
    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "humidity"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_humidity"

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
                and s.rh is not None
                and s.rh.status == "Okay"
            )
        except KeyError:
            return False

    @property
    def native_value(self) -> float | None:
        d = self._device()
        s = d.data.sensors if d.data else None
        if s and s.rh and s.rh.status == "Okay":
            return s.rh.val
        return None


class WattsFloorTempSensor(_WattsSensor):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_translation_key = "floor_temperature"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_floor_temp"
        self._attr_native_unit_of_measurement = _temp_unit(coordinator.data[device_id])

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
    def native_value(self) -> float | None:
        d = self._device()
        s = d.data.sensors if d.data else None
        if s and s.floor and s.floor.status == "Okay":
            return s.floor.val
        return None


class WattsFloorMaxSensor(_WattsSensor):
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "floor_max"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_floor_max"
        self._attr_native_unit_of_measurement = _temp_unit(coordinator.data[device_id])

    @property
    def native_value(self) -> float | None:
        d = self._device()
        if d.data and d.data.schedule:
            return d.data.schedule.floor_max
        return None


class WattsEnergyHeatSensor(_WattsSensor):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_translation_key = "energy_heat_today"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_energy_heat_today"

    @property
    def native_value(self) -> float | None:
        d = self._device()
        if d.data and d.data.energy and d.data.energy.heat and d.data.energy.heat.daily:
            return d.data.energy.heat.daily[-1]
        return None


class WattsEnergyCoolSensor(_WattsSensor):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = UnitOfEnergy.KILO_WATT_HOUR
    _attr_translation_key = "energy_cool_today"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_energy_cool_today"

    @property
    def native_value(self) -> float | None:
        d = self._device()
        if d.data and d.data.energy and d.data.energy.cool and d.data.energy.cool.daily:
            return d.data.energy.cool.daily[-1]
        return None
