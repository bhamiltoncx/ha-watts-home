"""Unit tests for the shared helpers."""

from __future__ import annotations

from custom_components.watts_home.helpers import device_model_name
from custom_components.watts_home.models import WattsDevice


def _device(model: str, device_type: str | None = None) -> WattsDevice:
    payload: dict[str, object] = {
        "deviceId": "d1",
        "name": "Device",
        "modelNumber": model,
        "isConnected": True,
    }
    if device_type is not None:
        payload["deviceType"] = device_type
    return WattsDevice.model_validate(payload)


class TestDeviceModelName:
    def test_known_thermostat_uses_its_catalogue_name(self) -> None:
        assert device_model_name(_device("562", "Thermostat")) == (
            "Tekmar WiFi Thermostat 562"
        )

    def test_setpoint_control_170_uses_its_catalogue_name(self) -> None:
        assert device_model_name(_device("170", "Setpoint")) == (
            "Tekmar Wi-Fi Setpoint Control 170"
        )

    def test_unknown_model_is_named_by_its_device_type(self) -> None:
        assert device_model_name(_device("999", "Setpoint")) == "Tekmar Setpoint 999"

    def test_unknown_model_without_device_type_is_named_by_number(self) -> None:
        assert device_model_name(_device("999")) == "Tekmar 999"
