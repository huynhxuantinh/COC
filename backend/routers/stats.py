from __future__ import annotations

from fastapi import APIRouter

from backend.models.schemas import StatsPayload
from backend.services.runtime import bot_service


router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("", response_model=StatsPayload)
def get_stats() -> StatsPayload:
    return StatsPayload(**bot_service.get_stats())
