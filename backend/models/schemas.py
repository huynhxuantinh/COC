from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConfigSection(BaseModel):
    model_config = ConfigDict(extra="allow")


class GameConfig(ConfigSection):
    auto_stop: bool | None = None
    auto_restart_after_seconds: float | None = Field(default=None, ge=0)
    periodic_restart_game: bool | None = None
    periodic_restart_min_seconds: float | None = Field(default=None, ge=0)
    periodic_restart_max_seconds: float | None = Field(default=None, ge=0)
    restart_wait_seconds: float | None = Field(default=None, gt=0)
    result_wait_seconds: float | None = Field(default=None, gt=0)
    home_zoom_out_keyevents: int | None = Field(default=None, ge=0)
    ldplayer_index: int | None = Field(default=None, ge=0)
    max_consecutive_cycle_errors: int | None = Field(default=None, ge=1)
    attack_missing_retries: int | None = Field(default=None, ge=1)
    max_home_restart_failures: int | None = Field(default=None, ge=1)


class FarmConfig(ConfigSection):
    gold_min: int | None = Field(default=None, ge=0)
    elixir_min: int | None = Field(default=None, ge=0)
    total_min: int | None = Field(default=None, ge=0)
    loot_gold_max: int | None = Field(default=None, ge=0)
    loot_elixir_max: int | None = Field(default=None, ge=0)
    max_next: int | None = Field(default=None, ge=1)
    search_delay_seconds: float | None = Field(default=None, gt=0)
    ocr_fail_restart_seconds: float | None = Field(default=None, ge=0)
    max_ocr_restarts: int | None = Field(default=None, ge=1)


class SurrenderConfig(ConfigSection):
    time_min_seconds: int | None = Field(default=None, ge=0)
    time_max_seconds: int | None = Field(default=None, ge=0)
    destruction_min_percent: int | None = Field(default=None, ge=0, le=100)
    destruction_max_percent: int | None = Field(default=None, ge=0, le=100)
    total_remaining_less_than: int | None = Field(default=None, ge=0)
    max_battle_seconds: int | None = Field(default=None, ge=1, le=175)
    damage_jump_confirm_percent: int | None = Field(default=None, ge=0, le=100)
    damage_jump_max_pending_reads: int | None = Field(default=None, ge=1)
    damage_stall_seconds: float | None = Field(default=None, ge=0)
    damage_unknown_restart_seconds: float | None = Field(default=None, ge=0)
    max_damage_ocr_restarts: int | None = Field(default=None, ge=1)


class MainTimingConfig(ConfigSection):
    after_click: float | None = Field(default=None, ge=0)
    after_home_attack: float | None = Field(default=None, ge=0)
    after_find_match: float | None = Field(default=None, ge=0)
    after_my_army_attack: float | None = Field(default=None, ge=0)
    after_next: float | None = Field(default=None, ge=0)
    after_return_home: float | None = Field(default=None, ge=0)
    loop_sleep: float | None = Field(default=None, gt=0)
    sleep_jitter_percent: float | None = Field(default=None, ge=0)
    sleep_jitter_min_seconds: float | None = Field(default=None, ge=0)


class BuilderTimingConfig(ConfigSection):
    after_attack_seconds: float | None = Field(default=None, gt=0)
    after_find_now_seconds: float | None = Field(default=None, gt=0)
    attack_cooldown_retry_seconds: float | None = Field(default=None, gt=0)
    screen_poll_seconds: float | None = Field(default=None, gt=0)
    prep_timeout_seconds: float | None = Field(default=None, gt=0)
    battle_timeout_seconds: float | None = Field(default=None, gt=0)
    stage_transition_timeout_seconds: float | None = Field(default=None, gt=0)
    result_wait_seconds: float | None = Field(default=None, gt=0)
    star_bonus_wait_seconds: float | None = Field(default=None, gt=0)


class BuilderBaseConfig(ConfigSection):
    timing: BuilderTimingConfig = Field(default_factory=BuilderTimingConfig)


class AppConfig(ConfigSection):
    game: GameConfig = Field(default_factory=GameConfig)
    farm: FarmConfig = Field(default_factory=FarmConfig)
    surrender: SurrenderConfig = Field(default_factory=SurrenderConfig)
    timing: MainTimingConfig = Field(default_factory=MainTimingConfig)
    builder_base: BuilderBaseConfig = Field(default_factory=BuilderBaseConfig)


class ApiMessage(BaseModel):
    ok: bool = True
    message: str = ""


class ConfigPayload(BaseModel):
    config: AppConfig


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


class SlotTemplateFile(BaseModel):
    filename: str
    image_base64: str


class SlotTemplateItem(BaseModel):
    kind: str
    count: int
    path: str
    files: list[SlotTemplateFile] = Field(default_factory=list)


class SlotTemplatesPayload(BaseModel):
    kinds: list[str]
    items: list[SlotTemplateItem]


class SlotTemplateSavePayload(BaseModel):
    kind: str
    image_base64: str
    x: int
    y: int
    size: int = 76
    crop_region: list[int] = Field(default_factory=list)


class SlotDetectPayload(BaseModel):
    image_base64: str = ""


class SlotDetectionItem(BaseModel):
    kind: str
    center: list[int]
    score: float
    template: str
    count: int = -1


class SlotDetectionsPayload(BaseModel):
    items: list[SlotDetectionItem]
