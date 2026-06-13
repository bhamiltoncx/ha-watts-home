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
    sub: str = Field("None", alias="Sub")


class WattsMode(BaseModel):
    val: str = Field(alias="Val")
    enum: list[str] = Field(alias="Enum")


class WattsTarget(BaseModel):
    heat: float | None = Field(None, alias="Heat")
    cool: float | None = Field(None, alias="Cool")
    min: float | None = Field(None, alias="Min")
    max: float | None = Field(None, alias="Max")
    steps: float | None = Field(None, alias="Steps")


class WattsTempUnits(BaseModel):
    val: str = Field(alias="Val")


class WattsFan(BaseModel):
    active: int = Field(0, alias="Active")
    val: str = Field(alias="Val")
    enum: list[str] = Field(alias="Enum")
    relay: int = Field(0, alias="Relay")


class WattsSchedEnable(BaseModel):
    val: str = Field(alias="Val")


class WattsHum(BaseModel):
    active: int = Field(0, alias="Active")
    val: int = Field(0, alias="Val")
    min: int = Field(10, alias="Min")
    max: int = Field(80, alias="Max")
    steps: int = Field(1, alias="Steps")


class WattsFloorSetpoint(BaseModel):
    w: float = Field(0, alias="W")
    a: float = Field(0, alias="A")


class WattsSchedule(BaseModel):
    sched_active: int = Field(0, alias="SchedActive")
    heat_active: int = Field(0, alias="HeatActive")
    cool_active: int = Field(0, alias="CoolActive")
    floor_active: int = Field(0, alias="FloorActive")
    floor: WattsFloorSetpoint | None = Field(None, alias="Floor")
    floor_min: float = Field(0, alias="FloorMin")
    floor_max: float = Field(0, alias="FloorMax")
    heat_min: float = Field(40, alias="HeatMin")
    heat_max: float = Field(95, alias="HeatMax")
    cool_min: float = Field(45, alias="CoolMin")
    cool_max: float = Field(100, alias="CoolMax")


class WattsEnergyChannel(BaseModel):
    daily: list[float] = Field(default_factory=list, alias="Daily")
    monthly: list[float] = Field(default_factory=list, alias="Monthly")


class WattsEnergy(BaseModel):
    heat: WattsEnergyChannel | None = Field(None, alias="Heat")
    cool: WattsEnergyChannel | None = Field(None, alias="Cool")


class WattsLocation(BaseModel):
    location_id: str = Field(alias="locationId")
    name: str = ""
    away_state: int = Field(0, alias="awayState")
    user_type: int = Field(0, alias="userType")


class WattsDeviceData(BaseModel):
    sensors: WattsSensors | None = Field(None, alias="Sensors")
    state: WattsState | None = Field(None, alias="State")
    mode: WattsMode | None = Field(None, alias="Mode")
    target: WattsTarget | None = Field(None, alias="Target")
    temp_units: WattsTempUnits | None = Field(None, alias="TempUnits")
    sched_enable: WattsSchedEnable | None = Field(None, alias="SchedEnable")
    fan: WattsFan | None = Field(None, alias="Fan")
    hum: WattsHum | None = Field(None, alias="Hum")
    schedule: WattsSchedule | None = Field(None, alias="Schedule")
    energy: WattsEnergy | None = Field(None, alias="Energy")


class WattsDevice(BaseModel):
    device_id: str = Field(alias="deviceId")
    name: str
    model_number: str = Field(alias="modelNumber")
    is_connected: bool = Field(alias="isConnected")
    data: WattsDeviceData | None = None
    location: WattsLocation | None = None
