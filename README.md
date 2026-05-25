# Watts Home (Tekmar) — Home Assistant Integration

Native Home Assistant custom component for Watts Home / Tekmar thermostats (models 561, 562, 563, 564). Based on and alternative to the [creamy-waha](https://github.com/AlbinoDrought/creamy-waha) MQTT bridge with a direct cloud-polling integration — no Docker, no MQTT broker required.

## Supported Devices

| Model | Modes | Fan | Humidity | Radiant Floor |
|---|---|---|---|---|
| 561 | Off, Heat | — | — | — |
| 562 | Off, Heat, Cool, Auto | Auto, On | — | Optional |
| 563 | Off, Heat, Cool, Auto | Auto, On | Humidifier + RH sensor | Optional |
| 564 | Off, Heat, Cool, Auto | Auto, On | — | Optional |

Capabilities are read dynamically from the API, so any future Tekmar model using the same API should work without code changes.

## Entities

### Climate

One `climate` entity per thermostat with heat, cool, auto, fan-only, and off modes (model-dependent). Supports single setpoint (heat or cool mode) and dual setpoint (auto / heat_cool mode). Fan mode control where available.

### Sensors

| Entity | Domain | Condition | Description |
|---|---|---|---|
| Outdoor Temperature | `sensor` | Outdoor probe present | Outdoor temp from shared gateway probe |
| Humidity | `sensor` | RH sensor present | Relative humidity (model 563) |
| Floor Temperature | `sensor` | Floor probe present | Radiant floor slab temperature |
| Floor Max | `sensor` (diagnostic) | Floor probe present | Hardware upper limit for floor temperature |
| Heat Today | `sensor` | Always | Daily heating energy (kWh, `total_increasing`) |
| Cool Today | `sensor` | Always | Daily cooling energy (kWh, `total_increasing`) |

### Binary Sensors

| Entity | Device Class | Condition | Description |
|---|---|---|---|
| Fan Running | `running` | Fan hardware present | Standalone fan circulation (G terminal). Does **not** reflect the HVAC blower during heat/cool calls — see note below. |
| Radiant Heating | `heat` | Floor probe present | Floor temp is below the occupied floor minimum setpoint |
| Humidifier Running | `running` | Humidifier installed | Fan relay on with no heat/cool call (heuristic — whole-home humidifiers use the G terminal) |
| Cold Weather Shutdown | `problem` (diagnostic) | Always | Heat-pump cooling locked out due to low outdoor temperature (`State.Sub == "CWSD"`) |

### Humidifier

One `humidifier` entity per device with `Hum.Active == 1`. Target humidity is writable; current humidity from the RH sensor. The entity is always-on because the Watts API has no humidifier on/off toggle. Action reports `humidifying` or `idle`.

### Number

| Entity | Condition | Description |
|---|---|---|
| Floor Min | Floor probe + schedule data | Occupied radiant floor minimum temperature. Set to 0 to disable floor heating. Range 0–FloorMax. |

### Switches

| Entity | Scope | Description |
|---|---|---|
| Away | Per location | Toggles vacation/away mode for all thermostats at the location |
| Emergency Heat | Per device (heat pump) | Activates auxiliary/emergency heat. Restores previous mode on turn-off. Only appears on devices with `Emer` in their mode enum. |

## Fan.Relay Note

`Fan.Relay` in the Watts API reflects the thermostat's **G terminal** (standalone fan circulation), not the air handler blower during heating/cooling calls. The HVAC blower is driven by W/Y signals from the furnace control board and is not exposed by the cloud API. `Fan Running` will show OFF during normal heat/cool operation — this is correct behavior, not a bug.

The `Humidifier Running` heuristic remains valid because whole-home humidifiers DO energize the G terminal to circulate moist air.

## Write Safety

Temperature writes always send **both** Heat and Cool setpoints to the API, even in single-direction modes. The Watts API silently corrupts the omitted setpoint if only one field is sent (e.g., sending only Heat resets Cool to the schedule maximum).

After every write operation, the integration calls `/Device/{id}/Refresh` to force the thermostat to sync with the cloud, and applies optimistic state updates to prevent UI snap-back.

## Installation

### HACS

Add this repository as a custom repository in HACS, then install **Watts Home (Tekmar)**.

### Manual

```bash
scp -r custom_components/watts_home root@homeassistant.local:/homeassistant/custom_components/
```

Restart Home Assistant, then go to **Settings → Integrations → Add → Watts Home**.

## Configuration

| Field | Default | Description |
|---|---|---|
| Email address | — | Your Watts Home account email |
| Password | — | Your Watts Home account password |
| Polling interval | 40 s | How often to poll the API (30–3600 s) |

## Removal

1. Go to **Settings → Integrations**, find **Watts Home**, and click **Delete**.
2. Remove the component files (if manually installed):
   ```bash
   rm -rf /homeassistant/custom_components/watts_home
   ```
3. Restart Home Assistant.

## Credits

Auth flow, API structure, and mode mappings ported from [creamy-waha](https://github.com/AlbinoDrought/creamy-waha) by [AlbinoDrought](https://github.com/AlbinoDrought), published under CC0 1.0 Universal.

## License

Apache 2.0 — see [LICENSE](LICENSE). Portions derived from [creamy-waha](https://github.com/AlbinoDrought/creamy-waha) (CC0 1.0 Universal).
