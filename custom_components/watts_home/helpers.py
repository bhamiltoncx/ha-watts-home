"""Shared helper functions for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from homeassistant.const import UnitOfTemperature

from .models import WattsDevice


def device_temperature_unit(device: WattsDevice) -> str:
    if device.data is None or device.data.temp_units is None:
        return UnitOfTemperature.CELSIUS
    return (
        UnitOfTemperature.FAHRENHEIT
        if device.data.temp_units.val == "F"
        else UnitOfTemperature.CELSIUS
    )
