# Watts Home (Tekmar) — Home Assistant Integration

Native Home Assistant custom component for Watts Home / Tekmar thermostats (models 561, 562, 563, 564). Based on and alternative to the [creamy-waha](https://github.com/AlbinoDrought/creamy-waha) MQTT bridge with a direct cloud-polling integration — no Docker, no MQTT broker required.

## Supported Devices

| Model | Modes | Fan |
|---|---|---|
| 561 | Off, Heat | — |
| 562 | Off, Heat, Cool, Auto | Auto, On |
| 563 | Off, Heat, Cool, Auto | Auto, On |
| 564 | Off, Heat, Cool, Auto | Auto, On |

Capabilities are read dynamically from the API, so any future Tekmar model using the same API should work without code changes.

## Features

- `climate` entity per thermostat — heat, cool, auto, fan, and off modes (model-dependent)
- `sensor` entities for outdoor temperature and humidity (where available)
- Token refresh with automatic re-login on expiry
- Configurable polling interval (default 60 s)

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
| Polling interval | 60 s | How often to poll the API (30–3600 s) |

## Credits

Auth flow, API structure, and mode mappings ported from [creamy-waha](https://github.com/AlbinoDrought/creamy-waha) by [AlbinoDrought](https://github.com/AlbinoDrought), published under CC0 1.0 Universal.

## License

Apache 2.0 — see [LICENSE](LICENSE). Portions derived from [creamy-waha](https://github.com/AlbinoDrought/creamy-waha) (CC0 1.0 Universal).
