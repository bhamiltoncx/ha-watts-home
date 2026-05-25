"""Number platform for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
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
        new: list[NumberEntity] = []
        for device_id, device in coordinator.data.items():
            uid = f"{device_id}_floor_min"
            if uid in known_entity_ids:
                continue
            if (
                device.data is not None
                and device.data.sensors is not None
                and device.data.sensors.floor is not None
                and device.data.sensors.floor.status == "Okay"
                and device.data.schedule is not None
                and device.data.schedule.floor is not None
            ):
                known_entity_ids.add(uid)
                new.append(WattsFloorMinNumber(coordinator, device_id))
        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
    _async_add_new()


class WattsFloorMinNumber(
    CoordinatorEntity[WattsDataUpdateCoordinator], NumberEntity
):
    """Radiant floor minimum temperature (occupied)."""

    _attr_has_entity_name = True
    _attr_translation_key = "floor_min"
    _attr_mode = NumberMode.SLIDER

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_floor_min"
        device = coordinator.data[device_id]
        self._attr_device_info = _device_info(device)
        unit = (
            device.data.temp_units.val
            if device.data and device.data.temp_units
            else None
        )
        self._attr_native_unit_of_measurement = (
            UnitOfTemperature.FAHRENHEIT if unit == "F" else UnitOfTemperature.CELSIUS
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
    def native_min_value(self) -> float:
        return 0

    @property
    def native_max_value(self) -> float:
        d = self._device()
        if d.data and d.data.schedule:
            return d.data.schedule.floor_max
        return 85.0

    @property
    def native_step(self) -> float:
        return 1.0

    @property
    def native_value(self) -> float | None:
        d = self._device()
        if d.data and d.data.schedule and d.data.schedule.floor:
            return d.data.schedule.floor.w
        return None

    async def async_set_native_value(self, value: float) -> None:
        device = self._device()
        current_a = 0.0
        if device.data and device.data.schedule and device.data.schedule.floor:
            current_a = device.data.schedule.floor.a

        client = await self.coordinator.async_get_client()
        await client.set_floor_min(self._device_id, value, current_a)

        def _update(d: WattsDevice) -> None:
            if d.data and d.data.schedule and d.data.schedule.floor:
                d.data.schedule.floor.w = value

        self.coordinator.optimistic_update(self._device_id, _update)
        await client.refresh_device(self._device_id)
        await self.coordinator.async_request_refresh()
