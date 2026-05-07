"""Pydantic v2 models for Watts Home API device responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class WattsSensor(BaseModel):
    val: float = Field(alias="Val")
    status: str = Field(alias="Status")


class WattsSensors(BaseModel):
    room: WattsSensor | None = Field(None, alias="Room")
    floor: WattsSensor | None = Field(None, alias="Floor")
    outdoor: WattsSensor | None = Field(None, alias="Outdoor")
    rh: WattsSensor | None = Field(None, alias="RH")


class WattsState(BaseModel):
    op: str = Field(alias="Op")


class WattsMode(BaseModel):
    val: str = Field(alias="Val")
    enum: list[str] = Field(alias="Enum")


class WattsTarget(BaseModel):
    heat: float | None = Field(None, alias="Heat")
    cool: float | None = Field(None, alias="Cool")
    min: float = Field(alias="Min")
    max: float = Field(alias="Max")
    steps: float = Field(alias="Steps")


class WattsTempUnits(BaseModel):
    val: str = Field(alias="Val")


class WattsFan(BaseModel):
    val: str = Field(alias="Val")
    enum: list[str] = Field(alias="Enum")


class WattsSchedEnable(BaseModel):
    val: str = Field(alias="Val")


class WattsDeviceData(BaseModel):
    sensors: WattsSensors | None = Field(None, alias="Sensors")
    state: WattsState | None = Field(None, alias="State")
    mode: WattsMode | None = Field(None, alias="Mode")
    target: WattsTarget | None = Field(None, alias="Target")
    temp_units: WattsTempUnits | None = Field(None, alias="TempUnits")
    sched_enable: WattsSchedEnable | None = Field(None, alias="SchedEnable")
    fan: WattsFan | None = Field(None, alias="Fan")


class WattsDevice(BaseModel):
    device_id: str = Field(alias="deviceId")
    name: str
    model_number: str = Field(alias="modelNumber")
    is_connected: bool = Field(alias="isConnected")
    data: WattsDeviceData | None = None
