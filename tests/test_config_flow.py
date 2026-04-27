"""Tests for the Watts Home config flow.

Happy-path and already-configured tests require real credentials
(WAHA_USER / WAHA_PASS env vars) and hit the live Watts API.

The invalid-auth test uses a deliberate wrong password so the login
server rejects it — no mocks needed.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USERNAME = os.environ.get("WAHA_USER", "")
PASSWORD = os.environ.get("WAHA_PASS", "")

_needs_creds = pytest.mark.skipif(
    not USERNAME or not PASSWORD,
    reason="WAHA_USER/WAHA_PASS not set",
)


@pytest.fixture
def mock_setup_entry() -> None:
    """Prevent the integration from actually loading platforms during flow tests."""
    with patch(
        "custom_components.watts_home.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_invalid_auth_shows_error(
    hass: HomeAssistant, enable_custom_integrations: None
) -> None:
    """Wrong password must show the invalid_auth error without creating an entry."""
    result = await hass.config_entries.flow.async_init(
        "watts_home", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "username": "nobody@example.com",
            "password": "definitelywrong",
            "scan_interval": 60,
        },
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


@_needs_creds
async def test_successful_setup_creates_entry(
    hass: HomeAssistant, enable_custom_integrations: None, mock_setup_entry: None
) -> None:
    """Valid credentials must create a config entry and finish the flow."""
    result = await hass.config_entries.flow.async_init(
        "watts_home", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"username": USERNAME, "password": PASSWORD, "scan_interval": 60},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["username"] == USERNAME
    assert "access_token" in result["data"]
    assert "refresh_token" in result["data"]


@_needs_creds
async def test_duplicate_entry_aborts(
    hass: HomeAssistant, enable_custom_integrations: None, mock_setup_entry: None
) -> None:
    """A second setup with the same account must abort as already_configured."""
    for _ in range(2):
        result = await hass.config_entries.flow.async_init(
            "watts_home", context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": USERNAME, "password": PASSWORD, "scan_interval": 60},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
