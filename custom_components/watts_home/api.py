"""Watts Home REST API client."""

from __future__ import annotations

import json
import logging
from typing import Any

from curl_cffi.requests import AsyncSession

from .const import API_BASE_URL, BROWSER_UA

_LOGGER = logging.getLogger(__name__)

_HEADERS: dict[str, str] = {
    "Api-Version": "2.0",
    "User-Agent": BROWSER_UA,
}


class WattsApiError(Exception):
    """Raised when the Watts API returns an error response."""


class WattsApiClient:
    """Thin wrapper around the Watts Home REST API."""

    def __init__(self, session: AsyncSession, access_token: str) -> None:
        self._session = session
        self._token = access_token

    def _headers(self) -> dict[str, str]:
        return {**_HEADERS, "Authorization": f"Bearer {self._token}"}

    async def _get(self, path: str) -> Any:
        _LOGGER.debug("GET %s", path)
        resp = await self._session.get(f"{API_BASE_URL}{path}", headers=self._headers())
        _LOGGER.debug("GET %s → HTTP %s", path, resp.status_code)
        if resp.status_code >= 400:
            raise WattsApiError(f"GET {path} failed: HTTP {resp.status_code}")
        body = resp.json()
        if body.get("errorNumber", 0) != 0:
            raise WattsApiError(f"GET {path} API error: {body}")
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "GET %s response body:\n%s",
                path,
                json.dumps(body["body"], indent=2),
            )
        return body["body"]

    async def _patch(self, path: str, payload: dict[str, Any]) -> Any:
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug("PATCH %s payload:\n%s", path, json.dumps(payload, indent=2))
        resp = await self._session.patch(
            f"{API_BASE_URL}{path}",
            json=payload,
            headers=self._headers(),
        )
        _LOGGER.debug("PATCH %s → HTTP %s", path, resp.status_code)
        if resp.status_code >= 400:
            raise WattsApiError(f"PATCH {path} failed: HTTP {resp.status_code}")
        body = resp.json()
        if body.get("errorNumber", 0) != 0:
            raise WattsApiError(f"PATCH {path} API error: {body}")
        return body.get("body")

    async def get_user_details(self) -> dict[str, Any]:
        result: dict[str, Any] = await self._get("/User/Details")
        return result

    async def get_locations(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._get("/Location")
        return result

    async def get_devices(self, location_id: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = await self._get(
            f"/Location/{location_id}/Devices"
        )
        return result

    async def set_mode(self, device_id: str, watts_mode: str) -> None:
        await self._patch(f"/Device/{device_id}", {"Settings": {"Mode": watts_mode}})

    async def set_fan_mode(self, device_id: str, fan_mode: str) -> None:
        await self._patch(f"/Device/{device_id}", {"Settings": {"Fan": fan_mode}})

    async def set_temperature(
        self,
        device_id: str,
        schedule_active: bool,
        heat: float | None,
        cool: float | None,
    ) -> None:
        settings: dict[str, Any] = {}
        if schedule_active:
            if heat is not None:
                settings["HeatHold"] = heat
            if cool is not None:
                settings["CoolHold"] = cool
        else:
            if heat is not None:
                settings["Heat"] = heat
            if cool is not None:
                settings["Cool"] = cool
        await self._patch(f"/Device/{device_id}", {"Settings": settings})

    @staticmethod
    def find_default_location(locations: list[dict[str, Any]]) -> dict[str, Any]:
        """Return the best location: default+devices first, then any with devices."""
        with_devices = [loc for loc in locations if loc.get("devicesCount", 0) > 0]
        for loc in with_devices:
            if loc.get("isDefault"):
                return loc
        if with_devices:
            return with_devices[0]
        raise WattsApiError("No location with devices found")
