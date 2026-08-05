from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from vision import Vision


class BuilderScreen:
    MAIN_HOME = "main_home"
    BUILDER_HOME = "builder_home"
    START_DIALOG = "start_dialog"
    STAGE_PREP = "stage_prep"
    BATTLE = "battle"
    RESULT = "result"
    ELIXIR_CART = "elixir_cart"
    STAR_BONUS = "star_bonus"
    INTERRUPTED = "interrupted"
    RESTARTED = "restarted"
    UNKNOWN = "unknown"


class BuilderBaseVision:
    def __init__(self, config: dict[str, Any], log=None, vision: Vision | None = None) -> None:
        self.config = config
        self.log = log or (lambda message: None)
        self.vision = vision or Vision(config, log=log)
        self.builder = config.get("builder_base", {})

    @property
    def available(self) -> bool:
        return self.vision.available

    def classify(self, png: bytes) -> str:
        if self.is_elixir_cart_popup(png):
            return BuilderScreen.ELIXIR_CART
        if self.is_star_bonus_popup(png):
            return BuilderScreen.STAR_BONUS
        if self.is_result_screen(png):
            return BuilderScreen.RESULT
        prep_match = self.find_template_center(
            png,
            Path("img/builder/states/prep"),
            threshold=0.0,
            scales=(1.0,),
            search_region=[650, 0, 330, 65],
        )
        battle_match = self.find_template_center(
            png,
            Path("img/builder/states/battle"),
            threshold=0.0,
            scales=(1.0,),
            search_region=[650, 0, 330, 65],
        )
        prep_score = prep_match[2] if prep_match else 0.0
        battle_score = battle_match[2] if battle_match else 0.0
        if max(prep_score, battle_score) >= 0.82:
            return BuilderScreen.STAGE_PREP if prep_score > battle_score else BuilderScreen.BATTLE
        if self.find_template_center(
            png,
            Path("img/builder/states/start-dialog"),
            threshold=0.72,
            scales=(1.0,),
            search_region=[550, 95, 500, 125],
        ):
            return BuilderScreen.START_DIALOG

        if self.is_builder_home(png):
            return BuilderScreen.BUILDER_HOME
        if self.vision.has_home_attack_button(png):
            return BuilderScreen.MAIN_HOME
        return BuilderScreen.UNKNOWN

    def is_builder_home(self, png: bytes) -> bool:
        template_dir = Path("img/builder/home")
        match = self.find_template_center(
            png,
            template_dir,
            threshold=0.85,
            scales=(0.9, 1.0, 1.1),
            search_region=[0, 680, 230, 220],
        )
        if match is not None:
            return True

        image = self.vision.image_from_png(png)
        if image is None:
            return False
        attack_region = self.builder.get("ocr_regions", {}).get("builder_attack_button", [20, 710, 175, 175])
        if not self.vision._has_attack_button_color(image, attack_region):
            return False
        crop = np.asarray(image.crop((15, 105, 245, 205)).convert("RGB"))
        if crop.size == 0:
            return False
        cyan = (crop[:, :, 1] >= 115) & (crop[:, :, 2] >= 130) & (crop[:, :, 2] >= crop[:, :, 0] * 1.05)
        return float(cyan.mean()) >= 0.035

    def is_result_screen(self, png: bytes) -> bool:
        regions = self.builder.get("ocr_regions", {})
        region = regions.get("return_home_button", [680, 710, 245, 105])
        if self.find_template_center(
            png,
            Path("img/builder/states/result"),
            threshold=0.78,
            scales=(0.9, 1.0, 1.1),
            search_region=[550, 650, 500, 220],
        ):
            return True

        image = self.vision.image_from_png(png)
        if image is None:
            return False
        x, y, width, height = [int(value) for value in region]
        button = np.asarray(image.crop((x, y, x + width, y + height)).convert("RGB"))
        if button.size == 0:
            return False
        red = button[:, :, 0].astype(np.int16)
        green = button[:, :, 1].astype(np.int16)
        blue = button[:, :, 2].astype(np.int16)
        green_pixels = (green >= 120) & (green >= red + 25) & (green >= blue + 25)
        if float(green_pixels.mean()) < 0.08:
            return False
        title = self._compact_text(image, [620, 300, 360, 150])
        return "totaldamage" in title

    def find_boat(self, png: bytes) -> tuple[int, int, float] | None:
        entry = self.builder.get("entry", {})
        directory = Path(entry.get("boat_template_dir", "img/builder/boat"))
        threshold = float(entry.get("boat_match_threshold", 0.62))
        return self.find_template_center(png, directory, threshold=threshold)

    def find_return_boat(self, png: bytes) -> tuple[int, int, float] | None:
        entry = self.builder.get("entry", {})
        directory = Path(entry.get("return_boat_template_dir", "img/builder/return_boat"))
        threshold = float(entry.get("return_boat_match_threshold", 0.68))
        region = entry.get("return_boat_search_region", [900, 250, 700, 650])
        return self.find_template_center(png, directory, threshold=threshold, search_region=region)

    def find_elixir_cart(self, png: bytes) -> tuple[int, int, float] | None:
        cart = self.builder.get("elixir_cart", {})
        directory = Path(cart.get("icon_template_dir", "img/builder/elixir-cart/icon"))
        threshold = float(cart.get("icon_match_threshold", 0.76))
        return self.find_template_center(png, directory, threshold=threshold, scales=(0.85, 1.0, 1.15))

    def is_elixir_cart_popup(self, png: bytes) -> bool:
        cart = self.builder.get("elixir_cart", {})
        directory = Path(cart.get("popup_template_dir", "img/builder/elixir-cart/popup"))
        threshold = float(cart.get("popup_match_threshold", 0.82))
        return self.find_template_center(
            png,
            directory,
            threshold=threshold,
            scales=(1.0,),
            search_region=[500, 30, 600, 120],
        ) is not None

    def read_elixir_cart_reward(self, png: bytes) -> int:
        image = self.vision.image_from_png(png)
        cart = self.builder.get("elixir_cart", {})
        region = cart.get("reward_region", [850, 185, 190, 55])
        return self.vision.read_number(image, region)

    def find_now_available(self, png: bytes) -> bool:
        image = self.vision.image_from_png(png)
        if image is None:
            return False
        x, y, width, height = self.builder.get("ocr_regions", {}).get(
            "find_now_button",
            [1025, 520, 330, 140],
        )
        button = np.asarray(image.crop((x, y, x + width, y + height)).convert("RGB"))
        if button.size == 0:
            return False
        red = button[:, :, 0].astype(np.int16)
        green = button[:, :, 1].astype(np.int16)
        blue = button[:, :, 2].astype(np.int16)
        green_pixels = (green >= 115) & (green >= red + 20) & (green >= blue + 20)
        return float(green_pixels.mean()) >= 0.12

    def is_star_bonus_popup(self, png: bytes) -> bool:
        image = self.vision.image_from_png(png)
        if image is None:
            return False
        regions = self.builder.get("ocr_regions", {})
        button_x, button_y, button_width, button_height = regions.get(
            "star_bonus_okay_button",
            [650, 640, 300, 130],
        )
        button = np.asarray(
            image.crop(
                (button_x, button_y, button_x + button_width, button_y + button_height)
            ).convert("RGB")
        )
        if button.size == 0:
            return False
        button_red = button[:, :, 0].astype(np.int16)
        button_green = button[:, :, 1].astype(np.int16)
        button_blue = button[:, :, 2].astype(np.int16)
        green_button = (
            (button_green >= 115)
            & (button_green >= button_red + 20)
            & (button_green >= button_blue + 20)
        )
        if float(green_button.mean()) < 0.12:
            return False

        title = self._compact_text(image, regions.get("star_bonus_title", [550, 120, 500, 120]))
        return "starbonus" in title

    def find_template_center(
        self,
        png: bytes,
        directory: Path,
        threshold: float,
        scales: tuple[float, ...] = (0.65, 0.75, 0.85, 1.0, 1.15, 1.3),
        search_region: list[int] | None = None,
    ) -> tuple[int, int, float] | None:
        screen = cv2.imdecode(np.frombuffer(png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if screen is None or not directory.exists():
            return None

        offset_x = 0
        offset_y = 0
        search = screen
        if search_region:
            offset_x, offset_y, width, height = [int(value) for value in search_region]
            search = screen[offset_y : offset_y + height, offset_x : offset_x + width]
            if search.size == 0:
                return None

        best: tuple[int, int, float] | None = None
        for path in sorted(directory.glob("*.png")):
            template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
            if template is None:
                continue
            for scale in scales:
                width = max(12, int(template.shape[1] * scale))
                height = max(12, int(template.shape[0] * scale))
                if width >= search.shape[1] or height >= search.shape[0]:
                    continue
                resized = cv2.resize(template, (width, height), interpolation=cv2.INTER_AREA)
                result = cv2.matchTemplate(search, resized, cv2.TM_CCOEFF_NORMED)
                _, score, _, location = cv2.minMaxLoc(result)
                if score < threshold:
                    continue
                center = (
                    offset_x + location[0] + width // 2,
                    offset_y + location[1] + height // 2,
                    float(score),
                )
                if best is None or center[2] > best[2]:
                    best = center
        return best

    def read_damage(self, png: bytes, stage: int = 2) -> int:
        image = self.vision.image_from_png(png)
        region = self.builder.get("ocr_regions", {}).get("damage_percent", [1450, 630, 135, 70])
        return self.vision.read_percent(image, region, max_percent=100 if stage == 1 else 200)

    def battle_frame_difference(self, previous_png: bytes, current_png: bytes) -> float:
        previous = cv2.imdecode(np.frombuffer(previous_png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        current = cv2.imdecode(np.frombuffer(current_png, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        if previous is None or current is None or previous.shape != current.shape:
            return float("inf")

        x, y, width, height = self.builder.get("ocr_regions", {}).get(
            "battle_activity",
            [250, 120, 1100, 500],
        )
        x = max(0, int(x))
        y = max(0, int(y))
        right = min(previous.shape[1], x + max(1, int(width)))
        bottom = min(previous.shape[0], y + max(1, int(height)))
        if right <= x or bottom <= y:
            return float("inf")

        previous_crop = cv2.resize(previous[y:bottom, x:right], (96, 54), interpolation=cv2.INTER_AREA)
        current_crop = cv2.resize(current[y:bottom, x:right], (96, 54), interpolation=cv2.INTER_AREA)
        return float(cv2.absdiff(previous_crop, current_crop).mean())

    def read_result(self, png: bytes) -> dict[str, int]:
        image = self.vision.image_from_png(png)
        regions = self.builder.get("ocr_regions", {})
        return {
            "damage": self.vision.read_percent(image, regions.get("result_damage", [690, 335, 230, 105]), 200),
            "gold": self.vision.read_number(image, regions.get("result_gold", [930, 532, 150, 42])),
            "trophies": self.vision.read_number(image, regions.get("result_trophies", [920, 590, 235, 70])),
        }

    def read_home_resources(self, png: bytes) -> dict[str, int]:
        image = self.vision.image_from_png(png)
        regions = self.builder.get("wall_upgrade", {}).get("resource_regions", {})
        return {
            "gold": self.vision.read_number(image, regions.get("gold", [1280, 15, 285, 60])),
            "elixir": self.vision.read_number(image, regions.get("elixir", [1280, 95, 285, 60])),
        }

    def find_wall_row(self, png: bytes, search_region: list[int]) -> list[int] | None:
        return self.vision.find_wall_row(png, search_region)

    def read_wall_upgrade_cost(self, png: bytes, button_center: list[int]) -> int:
        return self.vision.read_wall_upgrade_cost(png, button_center)

    def read_wall_confirmation(self, png: bytes) -> dict[str, Any]:
        image = self.vision.image_from_png(png)
        settings = self.builder.get("wall_upgrade", {})
        region = settings.get("confirmation_region", [420, 210, 760, 300])
        cost_region = settings.get("confirmation_cost_region", [690, 365, 480, 85])
        text = self._compact_text(image, region)
        return {
            "is_wall_upgrade": "upgradewalls" in text,
            "currency": "elixir" if "builderelixir" in text else "gold" if "buildergold" in text else "",
            "cost": self.vision.read_number(image, cost_region),
        }

    def slot_available(self, png: bytes, center: list[int]) -> bool:
        return self.vision.slot_looks_available(png, center, size=[92, 150])

    def hero_deployed(self, png: bytes, center: list[int]) -> bool:
        image = self.vision.image_from_png(png)
        if image is None:
            return False
        cx, cy = int(center[0]), int(center[1])
        crop = np.asarray(image.crop((cx - 58, cy - 102, cx + 58, cy - 57)).convert("RGB"))
        if crop.size == 0:
            return False
        red = crop[:, :, 0].astype(np.int16)
        green = crop[:, :, 1].astype(np.int16)
        blue = crop[:, :, 2].astype(np.int16)
        health_bar = (green >= 120) & (green >= red + 35) & (green >= blue + 20)
        return float(health_bar.mean()) >= 0.08

    def hero_ability_ready(self, png: bytes, center: list[int]) -> bool:
        image = self.vision.image_from_png(png)
        if image is None:
            return False
        cx, cy = int(center[0]), int(center[1])
        crop = np.asarray(image.crop((cx - 48, cy - 115, cx + 48, cy - 55)).convert("RGB"))
        if crop.size == 0:
            return False
        bright = crop.max(axis=2)
        chroma = crop.max(axis=2) - crop.min(axis=2)
        ready_pixels = (bright >= 115) & (chroma >= 35)
        return float(ready_pixels.mean()) >= 0.18

    def _compact_text(self, image, region: list[int]) -> str:
        text = self.vision.read_text(image, region)
        return "".join(character for character in text if character.isalpha())
