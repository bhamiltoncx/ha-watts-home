# Pydantic typed models + dynamic device discovery

**Date:** 2026-05-06
**Branch:** to be created from `main`

## Problem

The integration represents every Watts API device as `dict[str, Any]` throughout the
codebase. This has caused two bugs already:

- `85f9554` — `device["data"]["Mode"]` crashed when sub-fields were `None`
- `e7a9eb8` — `device["data"]` itself can be `None` during brief disconnects (e.g.
  HAOS update reboot); crashing `async_setup_entry` left entities permanently
  unavailable until manual reload

Additionally, new thermostats added to the Watts account after HA starts are never
discovered — `async_setup_entry` runs once and there is no re-check.

## Goals

1. Replace all `dict[str, Any]` device access with Pydantic models validated at the
   API boundary, eliminating the class of `AttributeError`/`TypeError` bugs entirely.
2. Automatically discover new devices within one poll interval (default 60 s) without
   requiring an integration reload.

## Out of scope

- Modelling the `GET /Location` or `GET /User/Details` response shapes (no bugs,
  minimal consumers, YAGNI).
- Removing stale entities for permanently-deleted devices (entities become
  unavailable via `KeyError → available=False`; users remove them manually).
- `get_user_details()` dead-code removal (separate PR).

---

## Design

### New file: `models.py`

A single new file `custom_components/watts_home/models.py` holds all Pydantic v2
models. Every model uses:

```python
model_config = ConfigDict()
```

Extra fields are ignored by default, tolerating additive API changes (new fields, new firmware).
Test objects are constructed via `model_validate({"deviceId": "x", ..., "data": None})` using
the API's own keys — no need for `populate_by_name` / `validate_by_name`.

#### Model hierarchy

```
WattsSensor
  val:    float    ← Val
  status: str      ← Status

WattsSensors
  room:    WattsSensor | None   ← Room
  floor:   WattsSensor | None   ← Floor
  outdoor: WattsSensor | None   ← Outdoor
  rh:      WattsSensor | None   ← RH

WattsState
  op: str   ← Op

WattsMode
  val:  str        ← Val
  enum: list[str]  ← Enum

WattsTarget
  heat:  float | None   ← Heat
  cool:  float | None   ← Cool
  min:   float          ← Min
  max:   float          ← Max
  steps: float          ← Steps

WattsTempUnits
  val: str   ← Val

WattsFan
  val:  str        ← Val
  enum: list[str]  ← Enum

WattsSchedEnable
  val: str   ← Val

WattsDeviceData
  sensors:      WattsSensors | None      ← Sensors
  state:        WattsState | None        ← State
  mode:         WattsMode | None         ← Mode
  target:       WattsTarget | None       ← Target
  temp_units:   WattsTempUnits | None    ← TempUnits
  sched_enable: WattsSchedEnable | None  ← SchedEnable
  fan:          WattsFan | None          ← Fan
  (Schedule, Energy, DateTime, TZOffset, Units → extra="ignore")

WattsDevice
  device_id:    str                  ← deviceId
  name:         str
  model_number: str                  ← modelNumber
  is_connected: bool                 ← isConnected
  data:         WattsDeviceData | None
  (location, modelId, deviceType, requestingUser, imageUrl, isShared → extra="ignore")
```

Field aliases match the API's title-case / camelCase keys exactly.
`Active` fields present in Mode/Target/TempUnits/SchedEnable are not modelled
(unused by the integration).

### `api.py` — `get_devices()`

Return type changes from `list[dict[str, Any]]` to `list[WattsDevice]`.
Parsing is per-device: one invalid device is logged and skipped; the rest are
returned normally. Entities for a skipped device go unavailable via the existing
`KeyError → available=False` path in `_device()`.

```python
async def get_devices(self, location_id: str) -> list[WattsDevice]:
    raw: list[dict] = await self._get(f"/Location/{location_id}/Devices")
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
```

`get_locations()`, `find_default_location()`, `set_mode()`, `set_temperature()`,
and `set_fan_mode()` are unchanged.

### `coordinator.py` — type and data shape

`WattsDataUpdateCoordinator` becomes
`DataUpdateCoordinator[dict[str, WattsDevice]]` — a dict keyed by `device_id`.

`_async_update_data` returns:

```python
{d.device_id: d for d in await client.get_devices(self.location_id)}
```

O(1) device lookup replaces the current O(n) linear scan in `_device()`.

### `climate.py` — helpers and entity

**Helper functions** keep the same names and stay as standalone pure functions
(HA enum mapping belongs in the HA layer, not on the domain model). Their
signatures change from `device: dict[str, Any]` to `device: WattsDevice`.
The `(device.get("data") or {}).get(…)` chains are replaced by direct typed
attribute access, e.g.:

```python
# before
mode = (device.get("data") or {}).get("Mode")

# after
mode = device.data.mode if device.data else None
```

**`_device()`** becomes a plain dict lookup:

```python
def _device(self) -> WattsDevice:
    return self.coordinator.data[self._device_id]  # KeyError → available=False
```

**Entity constructor** takes `device_id: str` instead of a device dict.
`DeviceInfo` is populated at construction time from `coordinator.data[device_id]`
(safe — device is always present when the entity is constructed).

**`async_setup_entry`** uses a coordinator listener for dynamic discovery.
Tracks by `device_id`; every device gets exactly one climate entity:

```python
known_device_ids: set[str] = set()

@callback
def _async_add_new() -> None:
    new = [
        WattsClimateEntity(coordinator, device_id)
        for device_id in coordinator.data
        if device_id not in known_device_ids
    ]
    if new:
        known_device_ids.update(e._device_id for e in new)
        async_add_entities(new)

entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
_async_add_new()
```

### `sensor.py` — entity and discovery

**Entity methods** replace `(self._device().get("data") or {}).get("Sensors") or {}`
with `self._device().data.sensors if self._device().data else None`.

**`async_setup_entry`** tracks by entity unique ID (not device ID) so that a
device which first appeared with `data=null` gets its sensor entities added on the
next poll once live data arrives:

```python
known_entity_ids: set[str] = set()

@callback
def _async_add_new() -> None:
    new: list[SensorEntity] = []
    for device_id, device in coordinator.data.items():
        s = device.data.sensors if device.data else None
        if s and s.outdoor and s.outdoor.status == "Okay":
            uid = f"{device_id}_outdoor_temp"
            if uid not in known_entity_ids:
                known_entity_ids.add(uid)
                new.append(WattsOutdoorTempSensor(coordinator, device_id))
        if s and s.rh and s.rh.status == "Okay":
            uid = f"{device_id}_humidity"
            if uid not in known_entity_ids:
                known_entity_ids.add(uid)
                new.append(WattsHumiditySensor(coordinator, device_id))
    if new:
        async_add_entities(new)

entry.async_on_unload(coordinator.async_add_listener(_async_add_new))
_async_add_new()
```

### Validation failure behaviour

| Scenario | Result |
|---|---|
| One device fails Pydantic validation | Logged at ERROR, skipped; its entities go `unavailable` |
| Device disappears from API response | Falls out of `coordinator.data`; `_device()` raises `KeyError`; `available=False` |
| Device reappears after temporary absence | Re-enters `coordinator.data`; entity recovers automatically |
| New device added to Watts account | Picked up within one poll interval (≤60 s) |

### Testing

- `tests/test_models.py` (new): validates `WattsDevice.model_validate()` against
  the full `devices.json` fixture; confirms `extra="ignore"` tolerates unknown
  fields; confirms `data=null` parses to `WattsDevice(data=None)` without error.
- `tests/test_climate.py`: fixture helpers change from raw dicts to
  `WattsDevice` instances. `_NULL_DEVICE` and `_NULL_DATA_FIELD_DEVICE` become
  `WattsDevice.model_validate({"deviceId": "x", ..., "data": None})`.
- `tests/test_sensor.py`: same pattern.
- `pydantic` is already bundled with Home Assistant; no change to `manifest.json`
  requirements.

---

## Files changed

| File | Change |
|---|---|
| `custom_components/watts_home/models.py` | **new** — all Pydantic models |
| `custom_components/watts_home/api.py` | `get_devices()` return type + per-item parse |
| `custom_components/watts_home/coordinator.py` | type param, `_async_update_data` return value |
| `custom_components/watts_home/climate.py` | helper signatures, entity constructor, discovery listener |
| `custom_components/watts_home/sensor.py` | entity constructor, discovery listener, typed attribute access |
| `tests/test_models.py` | **new** |
| `tests/test_climate.py` | fixture helpers use typed objects |
| `tests/test_sensor.py` | fixture helpers use typed objects |
| `scripts/dump_fixtures.py` | **new** — dev tool for capturing fixture data (personal data not committed) |
| `.gitignore` | add `tests/fixtures/user_details.json` and `tests/fixtures/locations.json` |
