"""Watts Home REST API client."""

from __future__ import annotations

import json
import logging
from typing import Any

from curl_cffi.requests import AsyncSession
from pydantic import ValidationError

from .const import API_BASE_URL, BROWSER_UA
from .models import WattsDevice

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
        text = resp.text.strip()
        if not text:
            return None
        body = resp.json()
        if body.get("errorNumber", 0) != 0:
            raise WattsApiError(f"GET {path} API error: {body}")
        if _LOGGER.isEnabledFor(logging.DEBUG):
            _LOGGER.debug(
                "GET %s response body:\n%s",
                path,
                json.dumps(body.get("body"), indent=2),
            )
        return body.get("body")

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
        text = resp.text.strip()
        if not text:
            return None
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

    async def get_devices(self, location_id: str) -> list[WattsDevice]:
        raw = await self._get(f"/Location/{location_id}/Devices")
        if not isinstance(raw, list):
            raise WattsApiError(f"Expected list from /Devices, got {type(raw).__name__}")
        devices: list[WattsDevice] = []
        for item in raw:
            try:
                devices.append(WattsDevice.model_validate(item))
            except ValidationError as exc:
                _LOGGER.error(
                    "Device %s failed Pydantic validation, marking unavailable: %s",
                    item.get("deviceId"),
                    exc,
                )
        return devices

    async def set_mode(self, device_id: str, watts_mode: str) -> None:
        await self._patch(f"/Device/{device_id}", {"Settings": {"Mode": watts_mode}})

    async def set_fan_mode(self, device_id: str, fan_mode: str) -> None:
        await self._patch(f"/Device/{device_id}", {"Settings": {"Fan": fan_mode}})

    async def set_temperature(
        self,
        device_id: str,
        schedule_active: bool,
        heat: float,
        cool: float,
    ) -> None:
        heat_key = "HeatHold" if schedule_active else "Heat"
        cool_key = "CoolHold" if schedule_active else "Cool"
        await self._patch(
            f"/Device/{device_id}",
            {"Settings": {heat_key: heat, cool_key: cool}},
        )

    async def refresh_device(self, device_id: str) -> None:
        """Ask the server to pull fresh state from the thermostat."""
        await self._get(f"/Device/{device_id}/Refresh")

    async def set_humidity(self, device_id: str, target: float) -> None:
        await self._patch(f"/Device/{device_id}", {"Settings": {"Hum": target}})

    async def set_floor_min(
        self, device_id: str, w: float, a: float
    ) -> None:
        await self._patch(
            f"/Device/{device_id}",
            {"Settings": {"Schedule": {"Floor": {"W": w, "A": a}}}},
        )

    async def set_away_state(self, location_id: str, away: bool) -> None:
        await self._patch(
            f"/Location/{location_id}/State",
            {"awayState": 1 if away else 0},
        )

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
