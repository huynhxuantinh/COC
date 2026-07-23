from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiMessage(BaseModel):
    ok: bool = True
    message: str = ""


class ConfigPayload(BaseModel):
    config: dict[str, Any]


class StatusPayload(BaseModel):
    status: str
    adb_ready: bool
    running: bool
    paused: bool
    active_devices: list[str] = Field(default_factory=list)


class LogEntry(BaseModel):
    id: int
    message: str
    created_at: str


class LogsPayload(BaseModel):
    items: list[LogEntry]
    next_after: int


class StatsPayload(BaseModel):
    current_session: dict[str, int]
    total: dict[str, int]
    by_device: dict[str, dict[str, Any]]


class SelectOption(BaseModel):
    label: str
    value: str


class OptionsPayload(BaseModel):
    combos: list[str]
    deploy_modes: list[SelectOption]
    attack_edges: list[SelectOption]
    attack_views: list[SelectOption] = Field(default_factory=list)


class ScreenshotPayload(BaseModel):
    image_base64: str
    width: int
    height: int


class ReferenceImageItem(BaseModel):
    name: str
    label: str
    width: int
    height: int


class ReferenceImagesPayload(BaseModel):
    items: list[ReferenceImageItem]


class TapPayload(BaseModel):
    x: int
    y: int


class SavePointsPayload(BaseModel):
    target: str
    points: list[list[int]]
    combo_name: str = ""
