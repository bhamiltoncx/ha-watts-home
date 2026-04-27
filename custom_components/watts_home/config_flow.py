"""Config flow for the Watts Home (Tekmar) integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from curl_cffi.requests import AsyncSession
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

from .api import WattsApiClient, WattsApiError
from .auth import WattsAuth, WattsAuthError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MAX_SCAN_INTERVAL,
    MIN_SCAN_INTERVAL,
)

_STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            int, vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL)
        ),
    }
)


class WattsHomeConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup of a Watts Home account."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            username: str = user_input[CONF_USERNAME]
            password: str = user_input[CONF_PASSWORD]

            try:
                async with AsyncSession(impersonate="chrome110") as session:
                    tokens = await WattsAuth.login(session, username, password)
                    client = WattsApiClient(session, tokens["access_token"])
                    user = await client.get_user_details()
            except WattsAuthError:
                errors["base"] = "invalid_auth"
            except (WattsApiError, Exception):  # noqa: BLE001
                errors["base"] = "unknown"
            else:
                user_id: str = user.get("userId", username)
                display_name: str = user.get("firstName", username)

                await self.async_set_unique_id(user_id)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=display_name,
                    data={
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                        **tokens,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_STEP_SCHEMA,
            errors=errors,
        )
