"""Sensor platform for the Watts Home (Tekmar) integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import WattsDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WattsDataUpdateCoordinator = entry.runtime_data
    entities: list[SensorEntity] = []
    for device in coordinator.data:
        sensors = device["data"]["Sensors"]
        if sensors.get("Outdoor", {}).get("Status") == "Okay":
            entities.append(WattsOutdoorTempSensor(coordinator, device))
        if sensors.get("RH", {}).get("Status") == "Okay":
            entities.append(WattsHumiditySensor(coordinator, device))
    async_add_entities(entities)


def _device_info(device: dict[str, Any]) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, device["deviceId"])},
        name=device["name"],
        model=device["modelNumber"],
        manufacturer="Watts Home",
    )


class WattsOutdoorTempSensor(
    CoordinatorEntity[WattsDataUpdateCoordinator], SensorEntity
):
    """Outdoor temperature sensor for a Watts/Tekmar device."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_has_entity_name = True
    _attr_translation_key = "outdoor_temperature"

    def __init__(
        self,
        coordinator: WattsDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._device_id: str = device["deviceId"]
        self._attr_unique_id = f"{self._device_id}_outdoor_temp"
        self._attr_device_info = _device_info(device)
        unit = device["data"]["TempUnits"]["Val"]
        self._attr_native_unit_of_measurement = (
            UnitOfTemperature.FAHRENHEIT if unit == "F" else UnitOfTemperature.CELSIUS
        )

    def _device(self) -> dict[str, Any]:
        for d in self.coordinator.data:
            if d["deviceId"] == self._device_id:
                return d
        raise KeyError(self._device_id)

    @property
    def available(self) -> bool:
        try:
            d = self._device()
            return (
                bool(d["isConnected"])
                and d["data"]["Sensors"].get("Outdoor", {}).get("Status") == "Okay"
            )
        except KeyError:
            return False

    @property
    def native_value(self) -> float | None:
        outdoor = self._device()["data"]["Sensors"].get("Outdoor", {})
        if outdoor.get("Status") == "Okay":
            return float(outdoor["Val"])
        return None


class WattsHumiditySensor(
    CoordinatorEntity[WattsDataUpdateCoordinator], SensorEntity
):
    """Relative humidity sensor for a Watts/Tekmar device."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_has_entity_name = True
    _attr_translation_key = "humidity"

    def __init__(
        self,
        coordinator: WattsDataUpdateCoordinator,
        device: dict[str, Any],
    ) -> None:
        super().__init__(coordinator)
        self._device_id: str = device["deviceId"]
        self._attr_unique_id = f"{self._device_id}_humidity"
        self._attr_device_info = _device_info(device)

    def _device(self) -> dict[str, Any]:
        for d in self.coordinator.data:
            if d["deviceId"] == self._device_id:
                return d
        raise KeyError(self._device_id)

    @property
    def available(self) -> bool:
        try:
            d = self._device()
            return (
                bool(d["isConnected"])
                and d["data"]["Sensors"].get("RH", {}).get("Status") == "Okay"
            )
        except KeyError:
            return False

    @property
    def native_value(self) -> float | None:
        rh = self._device()["data"]["Sensors"].get("RH", {})
        if rh.get("Status") == "Okay":
            return float(rh["Val"])
        return None
