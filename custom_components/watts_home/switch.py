"""Switch platform for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
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
        new: list[SwitchEntity] = []

        # Away switches — one per location
        seen_locations: set[str] = set()
        for device in coordinator.data.values():
            if device.location is None:
                continue
            loc_id = device.location.location_id
            if loc_id in seen_locations:
                continue
            seen_locations.add(loc_id)
            uid = f"location_{loc_id}_away"
            if uid not in known_entity_ids:
                known_entity_ids.add(uid)
                new.append(
                    WattsAwaySwitch(coordinator, loc_id, device.location.name)
                )

        # Emergency heat switches — one per device with Emer in mode enum
        for device_id, device in coordinator.data.items():
            if (
                device.data is not None
                and device.data.mode is not None
                and "Emer" in device.data.mode.enum
            ):
                uid = f"{device_id}_emergency_heat"
                if uid not in known_entity_ids:
                    known_entity_ids.add(uid)
                    new.append(WattsEmergencyHeatSwitch(coordinator, device_id))

        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
    _async_add_new()


class WattsAwaySwitch(CoordinatorEntity[WattsDataUpdateCoordinator], SwitchEntity):
    """Per-location away mode switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "away"
    _attr_icon = "mdi:home-export-outline"

    def __init__(
        self,
        coordinator: WattsDataUpdateCoordinator,
        location_id: str,
        location_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._location_id = location_id
        self._attr_unique_id = f"location_{location_id}_away"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"location_{location_id}")},
            name=location_name,
            manufacturer="Watts Home",
            model="Location",
        )

    @property
    def is_on(self) -> bool:
        for device in self.coordinator.data.values():
            if device.location and device.location.location_id == self._location_id:
                return device.location.away_state == 1
        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = await self.coordinator.async_get_client()
        await client.set_away_state(self._location_id, True)

        def _update_all(data: dict[str, WattsDevice]) -> None:
            for device in data.values():
                if device.location and device.location.location_id == self._location_id:
                    device.location.away_state = 1

        if self.coordinator.data:
            _update_all(self.coordinator.data)
            self.coordinator.async_set_updated_data(self.coordinator.data)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        client = await self.coordinator.async_get_client()
        await client.set_away_state(self._location_id, False)

        def _update_all(data: dict[str, WattsDevice]) -> None:
            for device in data.values():
                if device.location and device.location.location_id == self._location_id:
                    device.location.away_state = 0

        if self.coordinator.data:
            _update_all(self.coordinator.data)
            self.coordinator.async_set_updated_data(self.coordinator.data)
        await self.coordinator.async_request_refresh()


class WattsEmergencyHeatSwitch(
    CoordinatorEntity[WattsDataUpdateCoordinator], SwitchEntity
):
    """Per-device emergency/auxiliary heat switch."""

    _attr_has_entity_name = True
    _attr_translation_key = "emergency_heat"
    _attr_icon = "mdi:fire-alert"

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_emergency_heat"
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
            return self._device().is_connected
        except KeyError:
            return False

    @property
    def is_on(self) -> bool:
        d = self._device()
        return d.data is not None and d.data.mode is not None and d.data.mode.val == "Emer"

    async def async_turn_on(self, **kwargs: Any) -> None:
        client = await self.coordinator.async_get_client()
        await client.set_mode(self._device_id, "Emer")

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.mode:
                d.data.mode.val = "Emer"

        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        d = self._device()
        restore = "Heat"
        if d.data and d.data.mode:
            for m in d.data.mode.enum:
                if m not in ("Off", "Emer"):
                    restore = m
                    break
        client = await self.coordinator.async_get_client()
        await client.set_mode(self._device_id, restore)

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.mode:
                d.data.mode.val = restore

        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
        await self.coordinator.async_request_refresh()
