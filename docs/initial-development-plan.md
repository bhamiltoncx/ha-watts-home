# Plan: Watts Home Native HA Custom Component

## Context

The user has a Watts Home Tekmar 564 thermostat. The existing open-source project `creamy-waha` bridges the Watts API to HA via MQTT, but requires a separate Docker container and has no MQTT broker in this setup. Porting to a native Python HA custom component eliminates the MQTT + Docker dependency, provides proper HA entity management, and enables HACS installation.

**Recommendation confirmed:** port to Python, standalone repo (no MQTT broker present).

---

## Source Reference

`creamy-waha/main.go` — all auth, API, and mode-mapping logic to port (https://github.com/albinodrought/creamy-waha).

`tests/fixtures/devices.json` — sanitised API response from a real house (11 devices, models 561/562/563).

## Confirmed Device Schema (from live probe)

| Model | Modes | Fan | Notes |
|-------|-------|-----|-------|
| 561 | Off, Heat | none | `Target.Cool = None`, `Fan.Enum = []` |
| 562 | Off, Heat, Cool, Auto | Auto, On | `Target.Cool = 95` when unset (placeholder) |
| 563 | Off, Heat, Cool, Auto | Auto, On | same as 562 |
| 564 | unknown | unknown | creamy-waha target; same API, treat like 562/563 |

All 11 devices use `measurementScale: "I"` (Imperial / °F). All are `isConnected: true` in the `/Location/{id}/Devices` response (the `/User/Details` endpoint shows `false` — ignore it there).

`Target.Cool = 95°F` is the API's "not configured" sentinel for heat-only devices or unconfigured cool setpoints. The component should clamp display to `target_temperature_high` only when a real setpoint has been set (i.e. `< max_temp`), or simply expose it as-is and let the user set it.

---

## New Repo

Create a new GitHub repo (e.g. `ha-watts-home`) with this layout:

```
custom_components/watts_home/
├── __init__.py
├── manifest.json
├── const.py
├── auth.py
├── api.py
├── coordinator.py
├── config_flow.py
├── climate.py
├── sensor.py
├── strings.json
└── translations/en.json
hacs.json
```

During development: `scp -r custom_components/watts_home root@homeassistant.local:/homeassistant/custom_components/` then restart HA.

---

## Implementation Steps

### Step 1 — `manifest.json`
```json
{
  "domain": "watts_home",
  "name": "Watts Home (Tekmar)",
  "config_flow": true,
  "iot_class": "cloud_polling",
  "requirements": ["curl_cffi>=0.7.0"],
  "version": "1.0.0"
}
```
`curl_cffi` is required — Cloudflare on `home.watts.com` blocks Python's default TLS fingerprint (confirmed via probe). `curl_cffi` wraps libcurl and can impersonate a browser TLS handshake, bypassing the check. The auth domain (`login.watts.io`) does NOT have this restriction, so `urllib` is fine there.

---

### Step 2 — `const.py`

Constants ported directly from Go `main.go`:
- `CLIENT_ID = "4b3a6465-94dd-47c2-976c-18bc29c53c2f"`
- `API_BASE_URL = "https://home.watts.com/api"`
- `AUTH_BASE = "https://login.watts.io"`
- `BROWSER_UA` (Dalvik UA string)
- `REDIRECT_URI = f"msal{CLIENT_ID}://auth"`
- `WATTS_TO_HA_MODE`, `HA_TO_WATTS_MODE`, `WATTS_TO_HA_ACTION` dicts (from Go `wattsToHAMode`, `haToWattsMode`, `wattsToHAAction`)
- `DEFAULT_SCAN_INTERVAL = 300`

---

### Step 3 — `auth.py` (most critical — port `LoginSelfAsserted` + `ExchangeAuthToken` + `RefreshAuthToken`)

Use `curl_cffi.requests.AsyncSession` for auth too (same client as API layer, simpler, handles cookies natively). `login.watts.io` doesn't need the Cloudflare bypass but curl_cffi works fine there regardless.

Class `WattsAuth` with static async methods using a `curl_cffi.requests.AsyncSession`:

**`login(session, username, password) → dict`** — full PKCE flow:
1. GET authorize URL with `aiohttp.ClientSession` (with `cookie_jar`, `allow_redirects=False` equivalent via `history`)  
   - Extract `x-ms-cpim-csrf` cookie → `csrf`
   - Extract `x-ms-cpim-trans` cookie → `base64.b64decode(value + '==')` → JSON → `C_ID` field → `transaction`
2. Build `transactionEncoded = base64.urlsafe_b64encode(json.dumps({"TID": transaction}).encode()).decode().rstrip('=')`  
   **Note:** Go uses `base64.URLEncoding` (padded). Use standard padding here.
3. POST to `SelfAsserted` URL with form body + `X-CSRF-TOKEN: csrf` header → expect 200
4. GET `CombinedSigninAndSignup/confirmed` with `allow_redirects=False` → expect 302, extract `code` from `Location` header
5. Call `_exchange_code(session, code, verifier) → dict`

**`_exchange_code(session, code, verifier) → dict`** — POST to token endpoint:
- Body must have literal `+` separators in scope, not `%2B` — use `urllib.parse.urlencode` with `quote_via=urllib.parse.quote` or build body string manually (mirrors Go's `strings.ReplaceAll(data.Encode(), "%2B", "+")`)

**`refresh(session, refresh_token) → dict`** — POST refresh_token grant to same token endpoint.

Exceptions: `WattsAuthError`, `WattsTokenExpiredError(WattsAuthError)`.

Code verifier: use the same hardcoded string from Go (`"DM6nhvQ..."`) or `secrets.token_urlsafe(96)` — either works since PKCE is stateless per-flow.

---

### Step 4 — `api.py`

Class `WattsApiClient(session, access_token)` where `session` is a `curl_cffi.requests.AsyncSession(impersonate="chrome110")`:
- All requests: `Api-Version: 2.0`, `Authorization: Bearer <token>`, `User-Agent: <BROWSER_UA>` headers
- All responses: `{"errorNumber": 0, "body": <T>}` wrapper — unwrap `.body`
- Cloudflare bypass: the `impersonate="chrome110"` argument makes curl_cffi mimic Chrome's TLS fingerprint (JA3/JA4), which passes Cloudflare's bot detection on `home.watts.com`

Methods:
- `async get_user_details() → dict`
- `async get_locations() → list[dict]`
- `async get_devices(location_id) → list[dict]`
- `async set_mode(device_id, watts_mode)` → `PATCH /Device/{id}` with `{"Settings": {"Mode": watts_mode}}`
- `async set_fan_mode(device_id, fan_mode)` → `PATCH /Device/{id}` with `{"Settings": {"Fan": fan_mode}}`
- `async set_temperature(device_id, schedule_active, heat, cool)` → `PATCH /Device/{id}`  
  - `schedule_active=True` → keys `HeatHold`/`CoolHold`; `False` → keys `Heat`/`Cool`  
  - (mirrors Go `SetDeviceTemperature` which checks `SchedEnable.Val`)
- `def find_default_location(locations)` → prefer `isDefault=True` with `devicesCount > 0`, else first with `devicesCount > 0`

Exception: `WattsApiError`.

---

### Step 5 — `coordinator.py`

`WattsDataUpdateCoordinator(DataUpdateCoordinator)`:
- `update_interval = timedelta(seconds=300)`
- Holds `aiohttp.ClientSession` (created in `__init__.py`, passed in constructor)
- `_async_update_data()`:
  1. Call `_ensure_token()` → checks `expires_on < now + 120`, refreshes if needed, falls back to full re-login on failure, saves updated tokens via `async_update_entry`
  2. `WattsApiClient` → `get_locations()` → `find_default_location()` → `get_devices(location_id)`
  3. Store `location_id` on coordinator for command use
  4. Return `list[dict]` of devices; wrap failures as `UpdateFailed`
  5. On refresh token expiry: raise `ConfigEntryAuthFailed` (triggers HA re-auth repair)

---

### Step 6 — `config_flow.py`

Single step: username + password form. On submit:
1. `WattsAuth.login(session, username, password)` in a temporary `aiohttp.ClientSession`
2. `WattsApiClient.get_user_details()` for display name + unique ID
3. `async_set_unique_id(user["userId"])` → abort if already configured
4. `async_create_entry(title=name, data={username, password, **tokens})`
5. Errors: `invalid_auth` on `WattsAuthError`, `unknown` on other exceptions

Storing password in `entry.data` is required: full re-login is needed when refresh tokens expire (~90 days). HA encrypts `entry.data` at rest.

---

### Step 7 — `__init__.py`

```python
PLATFORMS = [Platform.CLIMATE, Platform.SENSOR]

async def async_setup_entry(hass, entry):
    session = AsyncSession(impersonate="chrome110")
    coordinator = WattsDataUpdateCoordinator(hass, entry, session)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

async def async_unload_entry(hass, entry):
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await entry.runtime_data.close()  # closes curl_cffi session
    return ok
```

---

### Step 8 — `climate.py`

`WattsClimateEntity(CoordinatorEntity, ClimateEntity)`:

Key properties (all read from `coordinator.data` device dict):
- `hvac_modes` — from `data.Mode.Enum` mapped through `WATTS_TO_HA_MODE`
- `hvac_mode` — `data.Mode.Val` mapped
- `hvac_action` — `data.State.Op` mapped through `WATTS_TO_HA_ACTION`
- `current_temperature` — `data.Sensors.Room.Val` (if `Status == "Okay"`)
- `current_humidity` — `data.Sensors.RH.Val` (if `Status == "Okay"`)
- `target_temperature` — `data.Target.Heat` or `data.Target.Cool` based on current mode
- `target_temperature_high/low` — for `heat_cool` mode
- `min_temp`, `max_temp`, `target_temperature_step` — from `data.Target.Min/Max/Steps`
- `temperature_unit` — from `data.TempUnits.Val` (`"C"` or `"F"`)
- `fan_mode` / `fan_modes` — from `data.Fan.Val` / `data.Fan.Enum`
- `available` — `device.isConnected`

`supported_features`: always `TARGET_TEMPERATURE | TURN_ON | TURN_OFF`; add `TARGET_TEMPERATURE_RANGE` if `heat_cool` in modes; add `FAN_MODE` if `Fan.Enum` non-empty.

Service methods (`async_set_hvac_mode`, `async_set_temperature`, `async_set_fan_mode`): call `WattsApiClient` with fresh token from `coordinator._ensure_token()`, then `coordinator.async_request_refresh()`.

`async_set_temperature`: route `ATTR_TEMPERATURE` vs `ATTR_TARGET_TEMP_HIGH/LOW` based on current mode; pass `schedule_active` from `data.SchedEnable.Val.lower() in ("on", "enabled")`.

---

### Step 9 — `sensor.py`

Two sensor entities per device (created only if sensor `Status == "Okay"`):
- `WattsOutdoorTempSensor` — `SensorDeviceClass.TEMPERATURE`, reads `data.Sensors.Outdoor.Val`
- `WattsHumiditySensor` — `SensorDeviceClass.HUMIDITY`, reads `data.Sensors.RH.Val`

Both share the same `DeviceInfo` identifiers as the climate entity (grouped under one device in HA).

---

### Step 10 — Strings / translations

`strings.json` and `translations/en.json` (identical): config flow step labels, error keys `invalid_auth` / `unknown`, abort key `already_configured`.

---

### Step 11 — `hacs.json` (repo root)
```json
{"name": "Watts Home (Tekmar 564)", "content_in_root": false}
```

---

## Implementation Order

1. Repo scaffold — directory layout, git init, `manifest.json`, `hacs.json`, `const.py`
2. `auth.py` — port PKCE flow + integration test (real API, uses WAHA_USER/WAHA_PASS env vars)
3. `api.py` — API client + integration test (real API)
4. `config_flow.py`
5. `coordinator.py` + `__init__.py`
6. `climate.py` + unit tests (pure logic using `tests/fixtures/devices.json` fixture)
7. `sensor.py` + unit tests
8. `strings.json` + `translations/en.json`

## Code Standards

- **Typed Python throughout** — all functions, methods, and module-level variables must have type annotations
- **No mocks** — integration tests use real API (env vars `WAHA_USER`/`WAHA_PASS`); unit tests use real fixture data from `tests/fixtures/devices.json` (copy of `watts_device_dump.json`)
- **Single HTTP client** — `curl_cffi.requests.AsyncSession(impersonate="chrome110")` used for both auth and API calls

---

## Verification

1. `scp -r custom_components/watts_home root@homeassistant.local:/homeassistant/custom_components/`
2. `ssh root@homeassistant.local "ha core restart"`
3. Settings → Integrations → Add → "Watts Home" → enter credentials
4. Verify `climate.tekmar_564` entity appears with correct temperature
5. `hass-cli state get climate.tekmar_564`
6. `ssh root@homeassistant.local "ha core logs | grep -i watts_home | tail -30"`
7. Test mode change from HA UI → verify API call succeeds
8. Wait 5 min → confirm coordinator poll updates state

---

## Tools / LSPs

No LSPs needed. Context7 MCP is available for live HA docs.

## Key Risks Resolved by Probe

- ✅ Auth flow works end-to-end (Azure AD B2C PKCE confirmed)
- ✅ API accessible and schema matches creamy-waha structs
- ✅ 11 devices, all connected, live temperature data confirmed
- ✅ Model differences handled naturally via `Mode.Enum` / `Fan.Enum` — no model-specific code needed
- ⚠️ Cloudflare blocks Python TLS on `home.watts.com` → solved by `curl_cffi`
- ⚠️ `Target.Cool = 95` is a sentinel "not set" value on heat-only/unconfigured devices
