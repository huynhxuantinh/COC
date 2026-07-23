from __future__ import annotations

from fastapi import APIRouter, Query

from backend.models.schemas import ApiMessage, LogsPayload
from backend.services.runtime import bot_service


router = APIRouter(prefix="/api/logs", tags=["logs"])


@router.get("", response_model=LogsPayload)
def get_logs(after: int = Query(default=0, ge=0)) -> LogsPayload:
    return LogsPayload(**bot_service.get_logs(after))


@router.delete("", response_model=ApiMessage)
def clear_logs() -> ApiMessage:
    bot_service.clear_logs()
    return ApiMessage(message="Đã xóa logs.")
