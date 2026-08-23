"""Shared helper functions for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from homeassistant.const import UnitOfTemperature

from .const import MODEL_NAMES
from .models import WattsDevice


def device_temperature_unit(device: WattsDevice) -> str:
    if device.data is None or device.data.temp_units is None:
        return UnitOfTemperature.CELSIUS
    return (
        UnitOfTemperature.FAHRENHEIT
        if device.data.temp_units.val == "F"
        else UnitOfTemperature.CELSIUS
    )


def device_model_name(device: WattsDevice) -> str:
    """Catalogue name if we know the model, else name it by its device type."""
    if (name := MODEL_NAMES.get(device.model_number)) is not None:
        return name
    if device.device_type:
        return f"Tekmar {device.device_type} {device.model_number}"
    return f"Tekmar {device.model_number}"
