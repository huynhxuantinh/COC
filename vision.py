from __future__ import annotations

import io
import re
import shutil
from pathlib import Path
from typing import Any


class Vision:
    def __init__(self, config: dict[str, Any], log=None) -> None:
        self.config = config
        self.log = log or (lambda message: None)
        self.enabled = bool(config["ocr"]["enabled"])
        self.available = False
        self.Image = None
        self.ImageOps = None
        self.pytesseract = None
        self._init_ocr()

    def _init_ocr(self) -> None:
        if not self.enabled:
            self.log("[OCR] Dang tat OCR, bot se khong doc duoc loot.")
            return

        try:
            from PIL import Image, ImageOps
            import pytesseract
        except ImportError:
            self.log("[OCR] Thieu Pillow/pytesseract. Chay: python -m pip install -r requirements.txt")
            return

        tess_path = self.config["ocr"].get("tesseract_path") or shutil.which("tesseract")
        if not tess_path:
            default_windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
            if Path(default_windows_path).exists():
                tess_path = default_windows_path
        if tess_path:
            pytesseract.pytesseract.tesseract_cmd = tess_path
            self.available = True
            self.Image = Image
            self.ImageOps = ImageOps
            self.pytesseract = pytesseract
            self.log("[OCR] San sang.")
        else:
            self.log("[OCR] Khong thay Tesseract OCR. Cai Tesseract hoac dien ocr.tesseract_path.")

    def image_from_png(self, png: bytes):
        if self.Image is None:
            return None
        return self.Image.open(io.BytesIO(png)).convert("RGB")

    def read_number(self, image, region: list[int], allow_percent: bool = False) -> int:
        if not self.available or image is None:
            return -1

        x, y, w, h = region
        crop = image.crop((x, y, x + w, y + h))
        crop = crop.resize((w * 3, h * 3))
        gray = self.ImageOps.grayscale(crop)
        gray = gray.point(lambda p: 255 if p > 145 else 0)
        whitelist = "0123456789%" if allow_percent else "0123456789"
        config = f"--psm 7 -c tessedit_char_whitelist={whitelist}"
        text = self.pytesseract.image_to_string(gray, config=config)
        digits = re.sub(r"\D", "", text)
        if not digits:
            return -1
        return int(digits)

    def read_text(self, image, region: list[int]) -> str:
        if not self.available or image is None:
            return ""

        x, y, w, h = region
        crop = image.crop((x, y, x + w, y + h))
        crop = crop.resize((w * 3, h * 3))
        gray = self.ImageOps.grayscale(crop)
        gray = gray.point(lambda p: 255 if p > 135 else 0)
        config = "--psm 7"
        return self.pytesseract.image_to_string(gray, config=config).strip().lower()

    def has_home_attack_button(self, png: bytes) -> bool:
        if not self.available:
            return True
        image = self.image_from_png(png)
        region = self.config["ocr"]["regions"].get("home_attack_button", [20, 715, 170, 160])
        if self._has_attack_button_color(image, region):
            return True
        text = self.read_text(image, region)
        compact = "".join(ch for ch in text if ch.isalpha())
        return "attack" in compact

    def has_battle_started(self, png: bytes) -> bool:
        if not self.available:
            return False
        image = self.image_from_png(png)
        text = self.read_text(image, [690, 0, 260, 110])
        compact = "".join(ch for ch in text if ch.isalpha())
        if "battleendsin" in compact:
            return True
        if "battlestartsin" in compact:
            return False

        next_region = self.config["ocr"]["regions"].get("next_button", [1325, 575, 250, 130])
        damage_region = self.config["ocr"]["regions"].get("damage_panel", [1320, 615, 260, 120])
        return self._has_dark_damage_panel(image, damage_region) and not self._has_orange_button(image, next_region)

    def _has_attack_button_color(self, image, region: list[int]) -> bool:
        if image is None:
            return False
        x, y, w, h = region
        crop = image.crop((x, y, x + w, y + h)).convert("RGB")
        pixels = list(crop.getdata())
        if not pixels:
            return False
        orange = 0
        yellow = 0
        for r, g, b in pixels:
            if r >= 145 and 65 <= g <= 190 and b <= 95:
                orange += 1
            if r >= 190 and g >= 130 and b <= 105:
                yellow += 1
        return (orange / len(pixels)) >= 0.12 or (yellow / len(pixels)) >= 0.10

    def _has_orange_button(self, image, region: list[int]) -> bool:
        if image is None:
            return False
        x, y, w, h = region
        crop = image.crop((x, y, x + w, y + h)).convert("RGB")
        pixels = list(crop.getdata())
        if not pixels:
            return False
        orange = 0
        for r, g, b in pixels:
            if r >= 180 and 70 <= g <= 170 and b <= 80:
                orange += 1
        return (orange / len(pixels)) >= 0.08

    def _has_dark_damage_panel(self, image, region: list[int]) -> bool:
        if image is None:
            return False
        x, y, w, h = region
        crop = image.crop((x, y, x + w, y + h)).convert("RGB")
        pixels = list(crop.getdata())
        if not pixels:
            return False
        dark = 0
        for r, g, b in pixels:
            if r <= 80 and g <= 90 and b <= 80:
                dark += 1
        return (dark / len(pixels)) >= 0.25

    def read_loot(self, png: bytes) -> dict[str, int]:
        image = self.image_from_png(png)
        regions = self.config["ocr"]["regions"]
        return {
            "gold": self.read_number(image, regions["loot_gold"]),
            "elixir": self.read_number(image, regions["loot_elixir"]),
            "dark": self.read_number(image, regions["loot_dark"]),
        }

    def read_damage_percent(self, png: bytes) -> int:
        image = self.image_from_png(png)
        region = self.config["ocr"]["regions"]["damage_percent"]
        value = self.read_number(image, region, allow_percent=True)
        if value > 100:
            return -1
        return value
