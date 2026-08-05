from __future__ import annotations

import io
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any


class Vision:
    def __init__(self, config: dict[str, Any], log=None) -> None:
        self.config = config
        self.log = log or (lambda message: None)
        self.enabled = bool(config["ocr"]["enabled"])
        self.available = False
        self.Image = None
        self.ImageEnhance = None
        self.ImageFilter = None
        self.ImageOps = None
        self.pytesseract = None
        self._init_ocr()

    def _init_ocr(self) -> None:
        if not self.enabled:
            self.log("[OCR] Dang tat OCR, bot se khong doc duoc loot.")
            return

        try:
            from PIL import Image, ImageEnhance, ImageFilter, ImageOps
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
            self.ImageEnhance = ImageEnhance
            self.ImageFilter = ImageFilter
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
        scale = 3 if allow_percent else 4
        crop = crop.resize((w * scale, h * scale))
        gray = self.ImageOps.grayscale(crop)
        whitelist = "0123456789%" if allow_percent else "0123456789"
        if allow_percent:
            return self._read_percent_from_candidates(crop, gray, whitelist)

        white_mask = self._white_digit_mask(crop)
        fast_candidates = [
            (white_mask, 7),
            (white_mask, 8),
        ]
        values: Counter[int] = Counter()
        for candidate, psm in fast_candidates:
            value = self._ocr_digits(candidate, whitelist, psm)
            if value >= 0:
                values[value] += 1
                if values[value] >= 2 and len(str(value)) >= 4:
                    return value

        candidates = [
            (white_mask, 13),
            (white_mask.filter(self.ImageFilter.MinFilter(3)), 7),
            (white_mask.filter(self.ImageFilter.MaxFilter(3)), 7),
            (gray, 8),
            (gray, 13),
            (gray, 7),
            (self.ImageEnhance.Contrast(gray).enhance(2.2), 8),
            (gray.point(lambda p: 255 if p > 120 else 0), 8),
        ]
        for candidate, psm in candidates:
            value = self._ocr_digits(candidate, whitelist, psm)
            if value >= 0:
                values[value] += 1
        if values:
            return max(values, key=lambda value: (values[value] * len(str(value)), values[value], len(str(value)), value))
        return -1

    def _read_percent_from_candidates(self, crop, gray, whitelist: str, max_percent: int = 100) -> int:
        white_mask = self._white_digit_mask(crop)
        candidates = [
            (gray.point(lambda p: 255 if p > 145 else 0), 7),
            (gray.point(lambda p: 255 if p > 130 else 0), 7),
            (gray.point(lambda p: 255 if p > 160 else 0), 7),
            (white_mask, 7),
            (white_mask, 8),
            (self.ImageEnhance.Contrast(gray).enhance(2.2), 7),
            (gray, 7),
            (gray, 8),
        ]
        values: Counter[int] = Counter()
        for candidate, psm in candidates:
            value = self._ocr_digits(candidate, whitelist, psm)
            if 0 <= value <= max_percent:
                values[value] += 1
        if not values:
            return -1
        return max(values, key=lambda value: (values[value], len(str(value)), value))

    def read_percent(self, image, region: list[int], max_percent: int = 100) -> int:
        if not self.available or image is None:
            return -1
        x, y, width, height = region
        crop = image.crop((x, y, x + width, y + height)).resize((width * 3, height * 3))
        gray = self.ImageOps.grayscale(crop)
        return self._read_percent_from_candidates(crop, gray, "0123456789%", max_percent=max_percent)

    def _ocr_digits(self, image, whitelist: str, psm: int) -> int:
        config = f"--psm {psm} -c tessedit_char_whitelist={whitelist}"
        text = self.pytesseract.image_to_string(image, config=config)
        digits = re.sub(r"\D", "", text)
        return int(digits) if digits else -1

    def _white_digit_mask(self, image):
        import numpy as np

        pixels = np.asarray(image.convert("RGB"), dtype=np.int16)
        bright = np.all(pixels > 175, axis=2)
        low_chroma = pixels.max(axis=2) - pixels.min(axis=2) < 85
        digit_pixels = bright & low_chroma
        mask = np.where(digit_pixels, 0, 255).astype(np.uint8)
        return self.Image.fromarray(mask, mode="L")

    def read_text(self, image, region: list[int], psm: int = 7) -> str:
        if not self.available or image is None:
            return ""

        x, y, w, h = region
        crop = image.crop((x, y, x + w, y + h))
        crop = crop.resize((w * 3, h * 3))
        gray = self.ImageOps.grayscale(crop)
        gray = gray.point(lambda p: 255 if p > 135 else 0)
        config = f"--psm {int(psm)}"
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

    def has_return_home_button(self, png: bytes) -> bool:
        if not self.available:
            return False
        image = self.image_from_png(png)
        region = self.config["ocr"]["regions"].get("return_home_button", [650, 700, 300, 160])
        if self._has_green_button(image, region):
            return True
        text = self.read_text(image, region)
        compact = "".join(ch for ch in text if ch.isalpha())
        return "returnhome" in compact

    def slot_looks_available(self, png: bytes, center: list[int], size: list[int] | None = None) -> bool:
        if not self.available:
            return True
        image = self.image_from_png(png)
        if image is None:
            return True

        width, height = size or [86, 104]
        cx, cy = center
        x1 = max(0, int(cx - width / 2))
        y1 = max(0, int(cy - height / 2))
        x2 = min(image.width, int(cx + width / 2))
        y2 = min(image.height, int(cy + height / 2))
        crop = image.crop((x1, y1, x2, y2)).convert("RGB")
        pixels = list(crop.getdata())
        if not pixels:
            return True

        colorful = 0
        visible = 0
        for r, g, b in pixels:
            brightness = max(r, g, b)
            if brightness < 35:
                continue
            visible += 1
            saturation = brightness - min(r, g, b)
            if saturation >= 45:
                colorful += 1
        if visible == 0:
            return True
        return colorful / visible >= 0.14

    def read_slot_count(self, png: bytes, center: list[int], kind: str = "") -> int:
        if not self.available:
            return -1
        image = self.image_from_png(png)
        if image is None:
            return -1

        if kind == "hero":
            return 1 if self.slot_looks_available(png, center) else 0

        cx, cy = center
        regions = [
            [int(cx - 64), int(cy - 92), 128, 52],
            [int(cx - 58), int(cy - 90), 88, 48],
            [int(cx - 24), int(cy - 90), 88, 48],
            [int(cx - 72), int(cy - 102), 144, 62],
        ]
        candidates: Counter[int] = Counter()
        for region in regions:
            candidates.update(self._read_slot_count_region(image, region))
        if candidates:
            return self._select_slot_count_candidate(kind, candidates)

        if self.slot_looks_available(png, center):
            return 1
        return 0

    def _select_slot_count_candidate(self, kind: str, candidates: Counter[int]) -> int:
        settings = self.config.get("slot_detection", {})
        corrections = settings.get("count_corrections", {}).get(kind, {})
        max_by_kind = settings.get("count_max_by_kind", {})
        max_value = int(max_by_kind.get(kind, 99))

        corrected: Counter[int] = Counter()
        for value, weight in candidates.items():
            mapped = int(corrections.get(str(value), value))
            corrected[mapped] += weight

        in_range = Counter({value: weight for value, weight in corrected.items() if 1 <= value <= max_value})
        if in_range:
            return in_range.most_common(1)[0][0]
        return corrected.most_common(1)[0][0]

    def _read_slot_count_region(self, image, region: list[int]) -> Counter[int]:
        values: Counter[int] = Counter()
        x, y, w, h = region
        x = max(0, x)
        y = max(0, y)
        crop = image.crop((x, y, min(image.width, x + w), min(image.height, y + h)))
        if crop.width <= 0 or crop.height <= 0:
            return values
        crop = crop.resize((crop.width * 5, crop.height * 5))
        variants = self._slot_count_ocr_variants(crop)
        for candidate in variants:
            for psm in (7, 8, 13):
                text = self.pytesseract.image_to_string(
                    candidate,
                    config=f"--psm {psm} -c tessedit_char_whitelist=xX0123456789",
                )
                value, weight = self._parse_slot_count_text(text)
                if value > 0:
                    values[value] += weight
        return values

    def _slot_count_ocr_variants(self, crop) -> list[Any]:
        gray = self.ImageOps.grayscale(crop)
        contrast = self.ImageEnhance.Contrast(gray).enhance(3.2)
        white_text = crop.convert("RGB").point(
            lambda p: 0 if p >= 172 else 255
        ).convert("L")
        white_text = white_text.filter(self.ImageFilter.MinFilter(3))
        variants = [
            gray,
            self.ImageOps.autocontrast(gray),
            contrast,
            contrast.point(lambda p: 255 if p > 145 else 0),
            white_text,
            self.ImageOps.invert(white_text),
        ]
        return variants

    def _parse_slot_count_text(self, text: str) -> tuple[int, int]:
        compact = re.sub(r"\s+", "", text)
        match = re.search(r"[xX](\d{1,2})", compact)
        if match:
            value = int(match.group(1))
            return (value, 4) if 1 <= value <= 99 else (-1, 0)

        digit_groups = re.findall(r"\d{1,2}", compact)
        if not digit_groups:
            return -1, 0
        value = max(int(group) for group in digit_groups)
        return ((value, 1) if 1 <= value <= 99 else (-1, 0))

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

    def _has_green_button(self, image, region: list[int]) -> bool:
        if image is None:
            return False
        x, y, w, h = region
        crop = image.crop((x, y, x + w, y + h)).convert("RGB")
        pixels = list(crop.getdata())
        if not pixels:
            return False
        green = sum(1 for r, g, b in pixels if g >= 115 and g >= r * 1.15 and g >= b * 1.2)
        dark = sum(1 for r, g, b in pixels if r <= 70 and g <= 80 and b <= 70)
        return (green / len(pixels)) >= 0.15 and (dark / len(pixels)) >= 0.12

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
        }

    def read_result_loot(self, png: bytes) -> dict[str, int]:
        image = self.image_from_png(png)
        regions = self.config["ocr"]["regions"]
        return {
            "gold": self.read_number(image, regions.get("result_gold", [612, 388, 210, 40])),
            "elixir": self.read_number(image, regions.get("result_elixir", [612, 430, 210, 40])),
        }

    def read_home_resources(self, png: bytes) -> dict[str, int]:
        image = self.image_from_png(png)
        regions = self.config["ocr"]["regions"]
        return {
            "gold": self.read_number(image, regions.get("home_gold", [1330, 35, 200, 40])),
            "elixir": self.read_number(image, regions.get("home_elixir", [1330, 105, 200, 40])),
        }

    def find_wall_row(self, png: bytes, search_region: list[int]) -> list[int] | None:
        if not self.available:
            return None
        image = self.image_from_png(png)
        if image is None:
            return None
        x, y, w, h = search_region
        crop = image.crop((x, y, x + w, y + h))
        data = self.pytesseract.image_to_data(crop, output_type=self.pytesseract.Output.DICT)
        candidates: list[tuple[float, int, int]] = []
        for index, text in enumerate(data.get("text", [])):
            if not text.strip().lower().startswith("wall"):
                continue
            bx = int(data["left"][index])
            by = int(data["top"][index])
            bw = int(data["width"][index])
            bh = int(data["height"][index])
            center_y = by + bh // 2

            # The list is translucent, so reject village labels behind it.
            # A real Wall row starts on the left and has a price on the right.
            if bx > int(w * 0.5):
                continue
            has_price = False
            for price_index, price_text in enumerate(data.get("text", [])):
                if price_index == index or not any(character.isdigit() for character in price_text):
                    continue
                price_x = int(data["left"][price_index])
                price_y = int(data["top"][price_index])
                price_h = int(data["height"][price_index])
                price_center_y = price_y + price_h // 2
                if price_x >= int(w * 0.55) and abs(price_center_y - center_y) <= max(18, bh):
                    has_price = True
                    break
            if not has_price:
                continue
            try:
                confidence = float(data["conf"][index])
            except (TypeError, ValueError):
                confidence = 0.0
            candidates.append((confidence, x + bx + bw // 2, y + center_y))
        if not candidates:
            return None
        _, center_x, center_y = max(candidates, key=lambda candidate: candidate[0])
        return [center_x, center_y]

    def read_wall_upgrade_cost(self, png: bytes, button_center: list[int]) -> int:
        image = self.image_from_png(png)
        cx, cy = int(button_center[0]), int(button_center[1])
        return self.read_number(image, [cx - 90, cy - 55, 180, 35])

    def read_wall_confirmation(
        self,
        png: bytes,
        settings: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        image = self.image_from_png(png)
        wall = settings or self.config.get("wall_upgrade", {})
        region = wall.get("confirmation_region", [420, 210, 760, 300])
        cost_region = wall.get("confirmation_cost_region", [560, 365, 480, 105])
        text = self.read_text(image, region, psm=6)
        compact = "".join(character for character in text if character.isalnum())
        currency = "elixir" if "elixir" in compact else "gold" if "gold" in compact else ""
        cost = -1
        if currency:
            match = re.search(rf"for(\d{{1,12}}){currency}", compact)
            if match:
                cost = int(match.group(1))
        if cost < 0:
            cost = self.read_number(image, cost_region)
        is_wall_upgrade = "upgradewalls" in compact or (
            "upgrade" in compact and "selectedwalls" in compact
        )
        return {
            "is_wall_upgrade": is_wall_upgrade,
            "currency": currency,
            "cost": cost,
        }

    def read_damage_percent(self, png: bytes) -> int:
        image = self.image_from_png(png)
        region = self.config["ocr"]["regions"]["damage_percent"]
        value = self.read_number(image, region, allow_percent=True)
        if value > 100:
            return -1
        return value
