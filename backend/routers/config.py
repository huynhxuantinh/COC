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
        config = payload.config.model_dump(mode="python", exclude_none=True)
        return ConfigPayload(config=bot_service.save_config_data(config))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Không thể lưu cấu hình: {exc}") from exc


@router.get("/options", response_model=OptionsPayload)
def get_options() -> OptionsPayload:
    return OptionsPayload(**bot_service.get_options())
