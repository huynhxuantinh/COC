from __future__ import annotations

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_SLOT_KINDS = ("dragon", "balloon", "valkyrie", "hero", "rage", "freeze")


@dataclass
class SlotDetection:
    kind: str
    center: list[int]
    score: float
    template: str
    count: int = -1

    def as_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "center": self.center,
            "score": round(float(self.score), 4),
            "template": self.template,
            "count": int(self.count),
        }


class SlotDetector:
    def __init__(self, config: dict[str, Any], log=None) -> None:
        self.config = config
        self.log = log or (lambda message: None)
        settings = config.get("slot_detection", {})
        self.template_dir = Path(settings.get("template_dir", "img/slots"))
        self.threshold = float(settings.get("threshold", 0.72))
        self.bar_region = [int(value) for value in settings.get("bar_region", [80, 720, 1220, 180])]
        self.template_size = [int(value) for value in settings.get("template_size", [76, 76])]
        self.kinds = list(settings.get("kinds", DEFAULT_SLOT_KINDS))

    def available(self) -> bool:
        try:
            import cv2  # noqa: F401
            import numpy  # noqa: F401
        except ImportError:
            return False
        return True

    def has_templates(self, kinds: list[str] | tuple[str, ...] | None = None) -> bool:
        active_kinds = kinds or self.kinds
        return any(self.templates_for(kind) for kind in active_kinds)

    def templates_for(self, kind: str) -> list[Path]:
        directory = self.template_dir / self._safe_kind(kind)
        if not directory.exists():
            return []
        return [
            path
            for path in sorted(directory.iterdir())
            if path.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")
        ]

    def template_summary(self) -> list[dict[str, Any]]:
        return [
            {
                "kind": kind,
                "count": len(self.templates_for(kind)),
                "path": str(self.template_dir / self._safe_kind(kind)),
            }
            for kind in self.kinds
        ]

    def save_template_from_base64(
        self,
        kind: str,
        image_base64: str,
        x: int,
        y: int,
        size: int | None = None,
        crop_region: list[int] | None = None,
    ) -> Path:
        from PIL import Image
        import io

        safe_kind = self._safe_kind(kind)
        if safe_kind not in self.kinds:
            raise ValueError(f"Loai slot khong hop le: {kind}")

        raw = base64.b64decode(image_base64)
        with Image.open(io.BytesIO(raw)) as source:
            image = source.convert("RGB")
            if crop_region and len(crop_region) >= 4:
                rx, ry, rw, rh = [int(value) for value in crop_region[:4]]
                if rw <= 0 or rh <= 0:
                    raise ValueError("Vung crop slot khong hop le.")
                x1 = max(0, rx)
                y1 = max(0, ry)
                x2 = min(image.width, rx + rw)
                y2 = min(image.height, ry + rh)
            else:
                crop_size = int(size or self.template_size[0])
                half = max(8, crop_size // 2)
                x1 = max(0, int(x) - half)
                y1 = max(0, int(y) - half)
                x2 = min(image.width, int(x) + half)
                y2 = min(image.height, int(y) + half)
            if x2 <= x1 or y2 <= y1:
                raise ValueError("Vung crop slot nam ngoai anh.")
            crop = image.crop((x1, y1, x2, y2))

        directory = self.template_dir / safe_kind
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{int(time.time() * 1000)}-{int(x)}-{int(y)}.png"
        crop.save(path)
        return path

    def detect(self, png: bytes, kinds: list[str] | tuple[str, ...] | None = None) -> list[SlotDetection]:
        if not self.available():
            self.log("[SLOT] Thieu opencv-python/numpy. Chay: python -m pip install -r requirements.txt")
            return []

        import cv2
        import numpy as np

        image_array = np.frombuffer(png, dtype=np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        if image is None:
            return []

        x, y, w, h = self.bar_region
        y2 = min(image.shape[0], y + h)
        x2 = min(image.shape[1], x + w)
        search = image[y:y2, x:x2]
        if search.size == 0:
            return []

        gray_search = cv2.cvtColor(search, cv2.COLOR_BGR2GRAY)
        detections: list[SlotDetection] = []
        active_kinds = [kind for kind in (kinds or self.kinds) if kind in self.kinds]
        for kind in active_kinds:
            for template_path in self.templates_for(kind):
                template = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
                if template is None:
                    continue
                if template.shape[0] > gray_search.shape[0] or template.shape[1] > gray_search.shape[1]:
                    continue
                result = cv2.matchTemplate(gray_search, template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(result >= self.threshold)
                for top, left in zip(locations[0], locations[1]):
                    score = float(result[top, left])
                    center = [int(x + left + template.shape[1] / 2), int(y + top + template.shape[0] / 2)]
                    detections.append(SlotDetection(kind=kind, center=center, score=score, template=template_path.name))

        detections.sort(key=lambda item: item.score, reverse=True)
        return self._dedupe(detections)

    def _dedupe(self, detections: list[SlotDetection]) -> list[SlotDetection]:
        kept: list[SlotDetection] = []
        for detection in detections:
            duplicate = False
            for current in kept:
                dx = detection.center[0] - current.center[0]
                dy = detection.center[1] - current.center[1]
                if dx * dx + dy * dy <= 48 * 48:
                    duplicate = True
                    break
            if not duplicate:
                kept.append(detection)
        return sorted(kept, key=lambda item: item.center[0])

    def _safe_kind(self, kind: str) -> str:
        return "".join(ch for ch in kind.lower().strip() if ch.isalnum() or ch in ("_", "-"))
