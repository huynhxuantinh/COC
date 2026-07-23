from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.models.schemas import (
    ApiMessage,
    ConfigPayload,
    ReferenceImagesPayload,
    SavePointsPayload,
    ScreenshotPayload,
    TapPayload,
)
from backend.services.runtime import bot_service


router = APIRouter(prefix="/api/coordinates", tags=["coordinates"])


@router.post("/screenshot", response_model=ScreenshotPayload)
def capture_screenshot() -> ScreenshotPayload:
    try:
        return ScreenshotPayload(**bot_service.capture_screenshot())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/reference-images", response_model=ReferenceImagesPayload)
def list_reference_images() -> ReferenceImagesPayload:
    return ReferenceImagesPayload(**bot_service.list_reference_images())


@router.get("/reference-images/{name}", response_model=ScreenshotPayload)
def get_reference_image(name: str) -> ScreenshotPayload:
    try:
        return ScreenshotPayload(**bot_service.reference_image(name))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/test-tap", response_model=ApiMessage)
def test_tap(payload: TapPayload) -> ApiMessage:
    try:
        bot_service.test_tap(payload.x, payload.y)
        return ApiMessage(message=f"Tapped {payload.x},{payload.y}")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/save-points", response_model=ConfigPayload)
def save_points(payload: SavePointsPayload) -> ConfigPayload:
    try:
        return ConfigPayload(config=bot_service.save_points(payload.target, payload.points))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
