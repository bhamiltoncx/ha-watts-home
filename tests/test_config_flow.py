"""Tests for the Watts Home config flow.

Happy-path and already-configured tests require real credentials
(WATTS_USER / WATTS_PASS env vars) and hit the live Watts API.

The invalid-auth test uses a deliberate wrong password so the login
server rejects it — no mocks needed.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.watts_home.auth import WattsAuthError

USERNAME = os.environ.get("WATTS_USER", "")
PASSWORD = os.environ.get("WATTS_PASS", "")

_needs_creds = pytest.mark.skipif(
    not USERNAME or not PASSWORD,
    reason="WATTS_USER/WATTS_PASS not set",
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


@pytest.fixture
def reauth_entry(hass: HomeAssistant) -> MockConfigEntry:
    """A configured entry whose stored password has gone stale."""
    entry = MockConfigEntry(
        domain="watts_home",
        unique_id="user-123",
        title="Tester",
        data={
            "username": "tester@example.com",
            "password": "stale",
            "scan_interval": 60,
            "access_token": "old-access",
            "refresh_token": "old-refresh",
            "expires_on": 0,
        },
    )
    entry.add_to_hass(hass)
    return entry


def _patch_login(tokens: dict[str, Any] | Exception, user_id: str = "user-123"):
    """Patch the login + user-details calls the reauth step makes."""
    login = patch(
        "custom_components.watts_home.config_flow.WattsAuth.login",
        new=AsyncMock(
            side_effect=tokens if isinstance(tokens, Exception) else None,
            return_value=None if isinstance(tokens, Exception) else tokens,
        ),
    )
    details = patch(
        "custom_components.watts_home.config_flow.WattsApiClient.get_user_details",
        new=AsyncMock(return_value={"userId": user_id, "firstName": "Tester"}),
    )
    return login, details


async def test_reauth_updates_credentials(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_setup_entry: None,
    reauth_entry: MockConfigEntry,
) -> None:
    """A correct password must refresh the stored tokens and end the flow."""
    result = await reauth_entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    new_tokens = {
        "access_token": "new-access",
        "refresh_token": "new-refresh",
        "expires_on": 9999999999,
    }
    login, details = _patch_login(new_tokens)
    with login, details:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "correct-horse"}
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert reauth_entry.data["password"] == "correct-horse"
    assert reauth_entry.data["access_token"] == "new-access"
    assert reauth_entry.data["refresh_token"] == "new-refresh"
    # Untouched fields must survive the partial update.
    assert reauth_entry.data["username"] == "tester@example.com"
    assert reauth_entry.data["scan_interval"] == 60


async def test_reauth_wrong_password_shows_error(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_setup_entry: None,
    reauth_entry: MockConfigEntry,
) -> None:
    """A rejected password must re-show the form without touching the entry."""
    result = await reauth_entry.start_reauth_flow(hass)

    login, details = _patch_login(WattsAuthError("Credentials rejected"))
    with login, details:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "still-wrong"}
        )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": "invalid_auth"}
    assert reauth_entry.data["password"] == "stale"


async def test_reauth_different_account_aborts(
    hass: HomeAssistant,
    enable_custom_integrations: None,
    mock_setup_entry: None,
    reauth_entry: MockConfigEntry,
) -> None:
    """Credentials for another account must abort rather than repoint the entry."""
    result = await reauth_entry.start_reauth_flow(hass)

    login, details = _patch_login(
        {"access_token": "a", "refresh_token": "b", "expires_on": 1},
        user_id="somebody-else",
    )
    with login, details:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "valid-but-other-account"}
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert reauth_entry.data["password"] == "stale"
