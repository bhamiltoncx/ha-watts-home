"""DataUpdateCoordinator for the Watts Home integration."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any

from curl_cffi.requests import AsyncSession
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WattsApiClient, WattsApiError
from .auth import WattsAuth, WattsAuthError, WattsTokenExpiredError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    TOKEN_REFRESH_BUFFER_SECONDS,
)

_LOGGER = __import__("logging").getLogger(__name__)


class WattsDataUpdateCoordinator(DataUpdateCoordinator[list[dict[str, Any]]]):
    """Polls the Watts API and manages token lifecycle."""

    location_id: str

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        session: AsyncSession,
    ) -> None:
        scan_interval: int = int(
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self._entry = entry
        self._session = session

    async def _ensure_token(self) -> str:
        """Return a valid access_token, refreshing or re-logging as needed."""
        data: dict[str, Any] = dict(self._entry.data)
        expires_on: int = int(data.get("expires_on", 0))

        if expires_on > time.time() + TOKEN_REFRESH_BUFFER_SECONDS:
            _LOGGER.debug("Access token still valid (expires_on=%s)", expires_on)
            return str(data["access_token"])

        refresh_token: str = str(data.get("refresh_token", ""))
        if refresh_token:
            try:
                _LOGGER.debug("Access token expiring, attempting refresh")
                new_tokens = await WattsAuth.refresh(self._session, refresh_token)
                data.update(new_tokens)
                self.hass.config_entries.async_update_entry(self._entry, data=data)
                _LOGGER.debug("Token refreshed successfully")
                return str(data["access_token"])
            except WattsTokenExpiredError:
                _LOGGER.debug("Refresh token expired, falling back to full re-login")
            except WattsAuthError as exc:
                raise ConfigEntryAuthFailed(str(exc)) from exc

        # Refresh token expired — attempt full re-login.
        _LOGGER.debug("Performing full re-login")
        try:
            new_tokens = await WattsAuth.login(
                self._session,
                str(data[CONF_USERNAME]),
                str(data[CONF_PASSWORD]),
            )
            data.update(new_tokens)
            self.hass.config_entries.async_update_entry(self._entry, data=data)
            _LOGGER.debug("Full re-login succeeded")
            return str(data["access_token"])
        except WattsAuthError as exc:
            raise ConfigEntryAuthFailed(str(exc)) from exc

    async def _async_update_data(self) -> list[dict[str, Any]]:
        try:
            access_token = await self._ensure_token()
            client = WattsApiClient(self._session, access_token)
            locations = await client.get_locations()
            location = WattsApiClient.find_default_location(locations)
            self.location_id = str(location["locationId"])
            _LOGGER.debug(
                "Polling location %s (%s)", location.get("name"), self.location_id
            )
            devices = await client.get_devices(self.location_id)
            _LOGGER.debug("Fetched %d device(s)", len(devices))
            return devices
        except ConfigEntryAuthFailed:
            raise
        except (WattsApiError, WattsAuthError) as exc:
            raise UpdateFailed(str(exc)) from exc

    async def async_get_client(self) -> WattsApiClient:
        """Return an API client with a fresh token for command use."""
        access_token = await self._ensure_token()
        return WattsApiClient(self._session, access_token)

    async def close(self) -> None:
        await self._session.close()
