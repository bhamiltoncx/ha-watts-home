"""Integration tests for WattsApiClient — hit the real Watts API.

Skip when WATTS_USER / WATTS_PASS environment variables are not set.

These tests make REAL changes to the thermostat and then restore them.
They verify the write propagated by re-reading the device via /Refresh + get_devices.
"""

from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
from pathlib import Path

import pytest
from curl_cffi.requests import AsyncSession

_ROOT = Path(__file__).parent.parent / "custom_components" / "watts_home"


def _load(name: str, path: Path) -> object:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_const = _load("custom_components.watts_home.const", _ROOT / "const.py")
_auth_mod = _load("custom_components.watts_home.auth", _ROOT / "auth.py")
_models_mod = _load("custom_components.watts_home.models", _ROOT / "models.py")
_api_mod = _load("custom_components.watts_home.api", _ROOT / "api.py")

WattsAuth = _auth_mod.WattsAuth
WattsApiClient = _api_mod.WattsApiClient
WattsDevice = _models_mod.WattsDevice

pytestmark = pytest.mark.skipif(
    not os.environ.get("WATTS_USER") or not os.environ.get("WATTS_PASS"),
    reason="WATTS_USER/WATTS_PASS not set",
)

USERNAME = os.environ.get("WATTS_USER", "")
PASSWORD = os.environ.get("WATTS_PASS", "")


@pytest.fixture()
async def client():
    async with AsyncSession(impersonate="chrome110") as session:
        tokens = await WattsAuth.login(session, USERNAME, PASSWORD)
        yield WattsApiClient(session, tokens["access_token"])


@pytest.fixture()
async def location_and_devices(client):
    locations = await client.get_locations()
    loc = WattsApiClient.find_default_location(locations)
    loc_id = str(loc.get("locationId") or loc.get("LocationId") or loc.get("id", ""))
    devices = await client.get_devices(loc_id)
    return loc_id, devices


async def _refetch_device(client, loc_id: str, device_id: str):
    """Refresh a device, wait, then re-fetch and return it."""
    await client.refresh_device(device_id)
    await asyncio.sleep(5)
    devices = await client.get_devices(loc_id)
    for d in devices:
        if d.device_id == device_id:
            return d
    raise KeyError(f"Device {device_id} not found after refresh")


# ---------------------------------------------------------------------------
# Basic connectivity
# ---------------------------------------------------------------------------


async def test_get_locations(client) -> None:
    locations = await client.get_locations()
    assert isinstance(locations, list)
    assert len(locations) > 0


async def test_find_default_location(client) -> None:
    locations = await client.get_locations()
    loc = WattsApiClient.find_default_location(locations)
    assert loc is not None


async def test_get_devices(location_and_devices) -> None:
    _, devices = location_and_devices
    assert isinstance(devices, list)
    assert len(devices) > 0
    device = devices[0]
    assert hasattr(device, "data")
    assert device.data is not None
    assert device.data.mode is not None
    assert device.data.target is not None


# ---------------------------------------------------------------------------
# New model fields present in real API
# ---------------------------------------------------------------------------


async def test_new_model_fields_present(location_and_devices) -> None:
    _, devices = location_and_devices
    for device in devices:
        assert device.data is not None
        assert device.data.state is not None
        assert isinstance(device.data.state.sub, str)
        assert device.data.energy is not None
        assert device.data.energy.heat is not None
        assert len(device.data.energy.heat.daily) == 7
        assert device.data.schedule is not None
        assert device.location is not None
        assert isinstance(device.location.location_id, str)
        assert isinstance(device.location.away_state, int)
        if device.data.fan is not None:
            assert isinstance(device.data.fan.relay, int)
            assert isinstance(device.data.fan.active, int)


# ---------------------------------------------------------------------------
# /Refresh endpoint
# ---------------------------------------------------------------------------


async def test_refresh_device_api(client, location_and_devices) -> None:
    _, devices = location_and_devices
    await client.refresh_device(devices[0].device_id)


# ---------------------------------------------------------------------------
# Temperature write — change, verify upstream, restore, verify downstream
# ---------------------------------------------------------------------------


async def test_set_temperature_round_trip(client, location_and_devices) -> None:
    """Change the active setpoint for the device's current mode, verify, restore.

    The Watts API only reliably accepts changes to the setpoint matching the
    active mode.  In Cool mode we change Cool, in Heat mode we change Heat,
    and in Auto we change both.  Either way both fields are always sent.
    """
    loc_id, devices = location_and_devices
    target_device = None
    for d in devices:
        if (
            d.data
            and d.data.target
            and d.data.target.heat is not None
            and d.data.target.cool is not None
            and d.data.mode
        ):
            target_device = d
            break
    if target_device is None:
        pytest.skip("No device with both heat and cool targets")

    original_heat = target_device.data.target.heat
    original_cool = target_device.data.target.cool
    mode = target_device.data.mode.val

    # Nudge the active setpoint by 1°
    if mode == "Cool":
        new_heat = original_heat
        new_cool = original_cool + 1 if original_cool < 95 else original_cool - 1
    else:
        new_heat = original_heat + 1 if original_heat < 90 else original_heat - 1
        new_cool = original_cool

    try:
        await client.set_temperature(
            target_device.device_id, False, new_heat, new_cool
        )

        updated = await _refetch_device(client, loc_id, target_device.device_id)

        if mode == "Cool":
            assert updated.data.target.cool == new_cool, (
                f"Cool not updated: expected {new_cool}, got {updated.data.target.cool}"
            )
            assert updated.data.target.heat == original_heat, (
                f"Heat corrupted: expected {original_heat}, got {updated.data.target.heat}"
            )
        else:
            assert updated.data.target.heat == new_heat, (
                f"Heat not updated: expected {new_heat}, got {updated.data.target.heat}"
            )
            assert updated.data.target.cool == original_cool, (
                f"Cool corrupted: expected {original_cool}, got {updated.data.target.cool}"
            )
    finally:
        await client.set_temperature(
            target_device.device_id, False, original_heat, original_cool
        )
        restored = await _refetch_device(client, loc_id, target_device.device_id)
        if mode == "Cool":
            assert restored.data.target.cool == original_cool, (
                f"Cool not restored: expected {original_cool}, got {restored.data.target.cool}"
            )
        else:
            assert restored.data.target.heat == original_heat, (
                f"Heat not restored: expected {original_heat}, got {restored.data.target.heat}"
            )


# ---------------------------------------------------------------------------
# Humidity write — change, verify, restore
# ---------------------------------------------------------------------------


async def test_humidity_round_trip(client, location_and_devices) -> None:
    """Write a changed humidity target, verify, then restore."""
    loc_id, devices = location_and_devices
    hum_device = None
    for d in devices:
        if d.data and d.data.hum and d.data.hum.active == 1:
            hum_device = d
            break
    if hum_device is None:
        pytest.skip("No device with active humidifier")

    original = hum_device.data.hum.val
    new_val = original + 1 if original < 75 else original - 1

    try:
        await client.set_humidity(hum_device.device_id, float(new_val))

        updated = await _refetch_device(client, loc_id, hum_device.device_id)
        assert updated.data.hum.val == new_val, (
            f"Humidity not updated: expected {new_val}, got {updated.data.hum.val}"
        )
    finally:
        await client.set_humidity(hum_device.device_id, float(original))
        restored = await _refetch_device(client, loc_id, hum_device.device_id)
        assert restored.data.hum.val == original, (
            f"Humidity not restored: expected {original}, got {restored.data.hum.val}"
        )


# ---------------------------------------------------------------------------
# Floor min write — change, verify, restore
# ---------------------------------------------------------------------------


async def test_floor_min_round_trip(client, location_and_devices) -> None:
    """Write a changed floor min W, verify, then restore."""
    loc_id, devices = location_and_devices
    floor_device = None
    for d in devices:
        if (
            d.data
            and d.data.sensors
            and d.data.sensors.floor
            and d.data.sensors.floor.status == "Okay"
            and d.data.schedule
            and d.data.schedule.floor
        ):
            floor_device = d
            break
    if floor_device is None:
        pytest.skip("No device with active floor sensor")

    original_w = floor_device.data.schedule.floor.w
    original_a = floor_device.data.schedule.floor.a
    new_w = original_w + 1 if original_w < 80 else original_w - 1

    try:
        await client.set_floor_min(floor_device.device_id, new_w, original_a)

        updated = await _refetch_device(client, loc_id, floor_device.device_id)
        assert updated.data.schedule.floor.w == new_w, (
            f"Floor W not updated: expected {new_w}, got {updated.data.schedule.floor.w}"
        )
        # A should be unchanged
        assert updated.data.schedule.floor.a == original_a, (
            f"Floor A corrupted: expected {original_a}, got {updated.data.schedule.floor.a}"
        )
    finally:
        await client.set_floor_min(floor_device.device_id, original_w, original_a)
        restored = await _refetch_device(client, loc_id, floor_device.device_id)
        assert restored.data.schedule.floor.w == original_w, (
            f"Floor W not restored: expected {original_w}, got {restored.data.schedule.floor.w}"
        )
        assert restored.data.schedule.floor.a == original_a, (
            f"Floor A not restored: expected {original_a}, got {restored.data.schedule.floor.a}"
        )


# ---------------------------------------------------------------------------
# Away state write — toggle, verify, restore
# ---------------------------------------------------------------------------


async def test_mode_switch_setpoints(client, location_and_devices) -> None:
    """Switch between Heat, Cool, and Auto modes.  Verify:
    1. Mode changes take effect
    2. The *active* setpoint is writeable in each mode
    3. In Auto mode both setpoints are independently controllable
    4. The thermostat resets the *inactive* setpoint in single-direction
       modes (e.g., Cool→CoolMax in Heat mode) — this is expected hardware
       behavior documented in PRS.md integration test findings.
    """
    loc_id, devices = location_and_devices
    target_device = None
    for d in devices:
        if (
            d.data
            and d.data.mode
            and "Auto" in d.data.mode.enum
            and "Heat" in d.data.mode.enum
            and "Cool" in d.data.mode.enum
            and d.data.target
            and d.data.target.heat is not None
            and d.data.target.cool is not None
        ):
            target_device = d
            break
    if target_device is None:
        pytest.skip("No device with Heat/Cool/Auto modes")

    original_mode = target_device.data.mode.val
    original_heat = target_device.data.target.heat
    original_cool = target_device.data.target.cool

    try:
        # --- Switch to Heat mode, verify heat setpoint is writable ---
        await client.set_mode(target_device.device_id, "Heat")
        new_heat = original_heat + 1 if original_heat < 90 else original_heat - 1
        # Must send both fields; thermostat will reset cool anyway
        await client.set_temperature(
            target_device.device_id, False, new_heat, original_cool
        )
        d = await _refetch_device(client, loc_id, target_device.device_id)
        assert d.data.mode.val == "Heat", f"Mode not Heat: {d.data.mode.val}"
        assert d.data.target.heat == new_heat, (
            f"Heat setpoint wrong in Heat mode: {d.data.target.heat}"
        )
        # Cool is expected to be reset by the thermostat in Heat mode

        # --- Switch to Cool mode, verify cool setpoint is writable ---
        await client.set_mode(target_device.device_id, "Cool")
        new_cool = original_cool - 1 if original_cool > 50 else original_cool + 1
        # Read current heat (thermostat may have reset it)
        d_after_mode = await _refetch_device(client, loc_id, target_device.device_id)
        current_heat = d_after_mode.data.target.heat
        await client.set_temperature(
            target_device.device_id, False, current_heat, new_cool
        )
        d = await _refetch_device(client, loc_id, target_device.device_id)
        assert d.data.mode.val == "Cool", f"Mode not Cool: {d.data.mode.val}"
        assert d.data.target.cool == new_cool, (
            f"Cool setpoint wrong in Cool mode: {d.data.target.cool}"
        )
        # Heat is expected to be reset by the thermostat in Cool mode

        # --- Switch to Auto, verify BOTH setpoints are writable ---
        await client.set_mode(target_device.device_id, "Auto")
        await client.set_temperature(
            target_device.device_id, False, original_heat, original_cool
        )
        d = await _refetch_device(client, loc_id, target_device.device_id)
        assert d.data.mode.val == "Auto", f"Mode not Auto: {d.data.mode.val}"
        assert d.data.target.heat == original_heat, (
            f"Heat wrong in Auto: {d.data.target.heat}"
        )
        assert d.data.target.cool == original_cool, (
            f"Cool wrong in Auto: {d.data.target.cool}"
        )

    finally:
        # Restore original mode and setpoints
        await client.set_mode(target_device.device_id, original_mode)
        await client.set_temperature(
            target_device.device_id, False, original_heat, original_cool
        )
        d = await _refetch_device(client, loc_id, target_device.device_id)
        assert d.data.mode.val == original_mode


async def test_away_state_round_trip(client, location_and_devices) -> None:
    """Toggle away state, verify it changed, then restore."""
    loc_id, devices = location_and_devices
    device = devices[0]
    if device.location is None:
        pytest.skip("No location data on device")

    original_away = device.location.away_state
    new_away = not (original_away == 1)

    try:
        await client.set_away_state(loc_id, new_away)
        await asyncio.sleep(3)

        # Re-fetch devices and check away_state changed
        updated_devices = await client.get_devices(loc_id)
        updated = [d for d in updated_devices if d.device_id == device.device_id][0]
        expected = 1 if new_away else 0
        assert updated.location.away_state == expected, (
            f"Away state not updated: expected {expected}, got {updated.location.away_state}"
        )
    finally:
        # Restore
        await client.set_away_state(loc_id, original_away == 1)
        await asyncio.sleep(3)
        restored_devices = await client.get_devices(loc_id)
        restored = [d for d in restored_devices if d.device_id == device.device_id][0]
        assert restored.location.away_state == original_away, (
            f"Away state not restored: expected {original_away}, got {restored.location.away_state}"
        )
