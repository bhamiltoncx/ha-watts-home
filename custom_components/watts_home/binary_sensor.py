"""Binary sensor platform for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MODEL_NAMES
from .coordinator import WattsDataUpdateCoordinator
from .models import WattsDevice

# ---------------------------------------------------------------------------
# Pure data-mapping helpers (no HA dependency — fully unit-testable)
# ---------------------------------------------------------------------------


def device_fan_running(device: WattsDevice) -> bool | None:
    """Fan relay state. None if fan not active."""
    if device.data is None or device.data.fan is None:
        return None
    if device.data.fan.active != 1:
        return None
    return device.data.fan.relay == 1


def device_radiant_heating(device: WattsDevice) -> bool | None:
    """Radiant floor calling heat. None if no floor sensor.

    Floor zone valve only opens in Heat, Auto, or Emer modes.
    In Cool or Off mode the setpoint is visible but the valve stays closed.
    """
    if device.data is None or device.data.sensors is None:
        return None
    floor = device.data.sensors.floor
    if floor is None or floor.status != "Okay":
        return None
    if device.data.schedule is None or device.data.schedule.floor is None:
        return None
    if device.data.mode is None or device.data.mode.val not in ("Heat", "Auto", "Emer"):
        return False
    target = device.data.schedule.floor.w
    return target > 0 and floor.val < target


def device_humidifier_running(device: WattsDevice) -> bool | None:
    """Humidifier likely running: fan on + no heat/cool call. None if no humidifier."""
    if device.data is None or device.data.hum is None:
        return None
    if device.data.hum.active != 1:
        return None
    if device.data.fan is None or device.data.state is None:
        return None
    return device.data.fan.relay == 1 and device.data.state.op == "Off"


def device_cold_weather_shutdown(device: WattsDevice) -> bool | None:
    """Cold Weather Shutdown active. None if state not available."""
    if device.data is None or device.data.state is None:
        return None
    return device.data.state.sub == "CWSD"


# ---------------------------------------------------------------------------
# HA platform setup
# ---------------------------------------------------------------------------

_SENSOR_DEFS: list[tuple[str, str, BinarySensorDeviceClass, EntityCategory | None, type]] = []


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
        new: list[BinarySensorEntity] = []
        for device_id, device in coordinator.data.items():
            for uid_suffix, cls in _ENTITY_CHECKS:
                uid = f"{device_id}_{uid_suffix}"
                if uid not in known_entity_ids and cls.is_eligible(device):
                    known_entity_ids.add(uid)
                    new.append(cls(coordinator, device_id))
        if new:
            async_add_entities(new)

    entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
    _async_add_new()


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


class _WattsBinarySensor(
    CoordinatorEntity[WattsDataUpdateCoordinator], BinarySensorEntity
):
    _attr_has_entity_name = True

    def __init__(
        self, coordinator: WattsDataUpdateCoordinator, device_id: str
    ) -> None:
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_{self._uid_suffix}"
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


class WattsFanRunningSensor(_WattsBinarySensor):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "fan_running"
    _uid_suffix = "fan_running"

    @staticmethod
    def is_eligible(device: WattsDevice) -> bool:
        return (
            device.data is not None
            and device.data.fan is not None
            and device.data.fan.active == 1
        )

    @property
    def is_on(self) -> bool | None:
        return device_fan_running(self._device())


class WattsRadiantHeatingSensor(_WattsBinarySensor):
    _attr_device_class = BinarySensorDeviceClass.HEAT
    _attr_translation_key = "radiant_heating"
    _uid_suffix = "radiant_heating"

    @staticmethod
    def is_eligible(device: WattsDevice) -> bool:
        if device.data is None or device.data.sensors is None:
            return False
        f = device.data.sensors.floor
        return f is not None and f.status == "Okay"

    @property
    def is_on(self) -> bool | None:
        return device_radiant_heating(self._device())


class WattsHumidifierRunningSensor(_WattsBinarySensor):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_translation_key = "humidifier_running"
    _uid_suffix = "humidifier_running"

    @staticmethod
    def is_eligible(device: WattsDevice) -> bool:
        return (
            device.data is not None
            and device.data.hum is not None
            and device.data.hum.active == 1
        )

    @property
    def is_on(self) -> bool | None:
        return device_humidifier_running(self._device())


class WattsColdWeatherShutdownSensor(_WattsBinarySensor):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "cold_weather_shutdown"
    _uid_suffix = "cold_weather_shutdown"

    @staticmethod
    def is_eligible(device: WattsDevice) -> bool:
        return device.data is not None and device.data.state is not None

    @property
    def is_on(self) -> bool | None:
        return device_cold_weather_shutdown(self._device())


_ENTITY_CHECKS: list[tuple[str, type[_WattsBinarySensor]]] = [
    ("fan_running", WattsFanRunningSensor),
    ("radiant_heating", WattsRadiantHeatingSensor),
    ("humidifier_running", WattsHumidifierRunningSensor),
    ("cold_weather_shutdown", WattsColdWeatherShutdownSensor),
]
