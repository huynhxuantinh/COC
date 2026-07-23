from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import ConfigPayload, OptionsPayload
from backend.services.runtime import bot_service


router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("", response_model=ConfigPayload)
def get_config() -> ConfigPayload:
    return ConfigPayload(config=bot_service.get_config())


@router.put("", response_model=ConfigPayload)
def update_config(payload: ConfigPayload) -> ConfigPayload:
    try:
        return ConfigPayload(config=bot_service.save_config_data(payload.config))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/options", response_model=OptionsPayload)
def get_options() -> OptionsPayload:
    return OptionsPayload(**bot_service.get_options())
