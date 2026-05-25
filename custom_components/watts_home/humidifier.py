"""Humidifier platform for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL_NAMES
from .coordinator import WattsDataUpdateCoordinator
from .models import WattsDevice


def _device_info(device: WattsDevice) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, device.device_id)},
        name=device.name,
        model=MODEL_NAMES.get(
            device.model_number, f"Tekmar WiFi Thermostat {device.model_number}"
        ),
        manufacturer="Watts Home",
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: WattsDataUpdateCoordinator = entry.runtime_data
    known_entity_ids: set[str] = set()

    @callback
    def _async_add_new() -> None:
        new: list[HumidifierEntity] = []
        for device_id, device in coordinator.data.items():
            uid = f"{device_id}_humidifier"
            if uid in known_entity_ids:
                continue
            if (
                device.data is not None
                and device.data.hum is not None
                and device.data.hum.active == 1
            ):
                known_entity_ids.add(uid)
                new.append(WattsHumidifierEntity(coordinator, device_id))
        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
    _async_add_new()


class WattsHumidifierEntity(
    CoordinatorEntity[WattsDataUpdateCoordinator], HumidifierEntity
):
    """Whole-home humidifier entity for a Watts/Tekmar device."""

    _attr_device_class = HumidifierDeviceClass.HUMIDIFIER
    _attr_supported_features = HumidifierEntityFeature(0)
    _attr_has_entity_name = True
    _attr_translation_key = "humidifier"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_humidifier"
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

    @property
    def is_on(self) -> bool:
        return True

    @property
    def target_humidity(self) -> int | None:
        d = self._device()
        if d.data and d.data.hum:
            return d.data.hum.val
        return None

    @property
    def current_humidity(self) -> float | None:
        d = self._device()
        if d.data and d.data.sensors and d.data.sensors.rh:
            rh = d.data.sensors.rh
            return rh.val if rh.status == "Okay" else None
        return None

    @property
    def min_humidity(self) -> int:
        d = self._device()
        return d.data.hum.min if d.data and d.data.hum else 10

    @property
    def max_humidity(self) -> int:
        d = self._device()
        return d.data.hum.max if d.data and d.data.hum else 80

    @property
    def action(self) -> str | None:
        d = self._device()
        if d.data and d.data.fan and d.data.state:
            if d.data.fan.relay == 1 and d.data.state.op == "Off":
                return "humidifying"
        return "idle"

    async def async_set_humidity(self, humidity: int) -> None:
        client = await self.coordinator.async_get_client()
        await client.set_humidity(self._device_id, float(humidity))

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.hum:
                d.data.hum.val = humidity

        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs: Any) -> None:
        pass

    async def async_turn_off(self, **kwargs: Any) -> None:
        pass
