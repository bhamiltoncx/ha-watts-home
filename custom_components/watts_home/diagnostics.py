"""Diagnostics support for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .api import WattsApiClient

TO_REDACT = {
    CONF_USERNAME,
    CONF_PASSWORD,
    "access_token",
    "refresh_token",
    "address",
    "deviceId",
    "locationId",
    "requestingUser",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    # Fetch raw payloads: the parsed models drop fields they don't know, which
    # are exactly what's needed to add support for a new device.
    client = await entry.runtime_data.async_get_client()
    locations = await client.get_locations()
    for location in WattsApiClient.locations_with_devices(locations):
        location["devices"] = await client.get_raw_devices(
            str(location["locationId"])
        )
    return async_redact_data(
        {"entry": dict(entry.data), "locations": locations}, TO_REDACT
    )
