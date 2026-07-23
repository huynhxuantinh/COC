from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import StatusPayload
from backend.services.runtime import bot_service


router = APIRouter(prefix="/api/bot", tags=["bot"])


@router.get("/status", response_model=StatusPayload)
def get_status() -> StatusPayload:
    return StatusPayload(**bot_service.get_status())


@router.post("/scan-adb", response_model=StatusPayload)
def scan_adb() -> StatusPayload:
    try:
        return StatusPayload(**bot_service.scan_adb())
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/start", response_model=StatusPayload)
def start_bot() -> StatusPayload:
    return StatusPayload(**bot_service.start_bot())


@router.post("/pause-toggle", response_model=StatusPayload)
def toggle_pause() -> StatusPayload:
    return StatusPayload(**bot_service.toggle_pause())


@router.post("/stop", response_model=StatusPayload)
def stop_bot() -> StatusPayload:
    return StatusPayload(**bot_service.stop_bot())
