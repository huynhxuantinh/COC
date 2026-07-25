from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    SlotDetectPayload,
    SlotDetectionsPayload,
    SlotTemplateSavePayload,
    SlotTemplatesPayload,
)
from backend.services.runtime import bot_service


router = APIRouter(prefix="/api/slots", tags=["slots"])


@router.get("/templates", response_model=SlotTemplatesPayload)
def get_templates() -> SlotTemplatesPayload:
    return SlotTemplatesPayload(**bot_service.slot_templates())


@router.post("/templates", response_model=SlotTemplatesPayload)
def save_template(payload: SlotTemplateSavePayload) -> SlotTemplatesPayload:
    try:
        return SlotTemplatesPayload(
            **bot_service.save_slot_template(
                payload.kind,
                payload.image_base64,
                payload.x,
                payload.y,
                payload.size,
                payload.crop_region,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/detect", response_model=SlotDetectionsPayload)
def detect_slots(payload: SlotDetectPayload) -> SlotDetectionsPayload:
    try:
        return SlotDetectionsPayload(**bot_service.detect_slots(payload.image_base64))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
