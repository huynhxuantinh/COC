from __future__ import annotations

import json
import random
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from adb_client import ADBClient, ADBError
from slot_detector import SlotDetector
from vision import Vision


class FarmBot:
    STAT_KEYS = ("attacks", "next", "gold_seen", "elixir_seen", "dark_seen")

    def __init__(
        self,
        config: dict[str, Any],
        log,
        stop_event: threading.Event,
        pause_event: threading.Event,
        stats_callback=None,
    ) -> None:
        self.config = config
        self.log = log
        self.stop_event = stop_event
        self.pause_event = pause_event
        resolution = tuple(config["game"].get("resolution", [1600, 900]))
        self.adb = ADBClient(config["adb"]["path"], config["adb"]["device"], log=log, resolution=resolution)
        self.vision = Vision(config, log=log)
        self.slot_detector = SlotDetector(config, log)
        self.stats = {key: 0 for key in self.STAT_KEYS}
        self.stats_callback = stats_callback or (lambda stats: None)
        self.stats_path = Path(config.get("runtime", {}).get("stats_path", "stats.json"))
        self.safe_device = self._safe_name(config["adb"]["device"])
        self.debug_dir = Path("debug")
        self.session_started_at = datetime.now().isoformat(timespec="seconds")
        self.base_total_stats = self._load_total_stats()
        self.run_started_at = 0.0
        self.auto_stop_at = 0.0
        self.active_combo = self._select_active_combo()
        self.active_deploy = self._active_deploy()
        self.current_attack_view = ""
        self.home_restart_failures = 0
        self.runtime_slots: dict[str, list[dict[str, Any]]] = {}
        self.manual_slot_counts: dict[str, int] = {}

    def run(self) -> None:
        try:
            if self.config["adb"]["connect_on_start"]:
                self.adb.connect()
            if not self._ocr_ready_or_stop():
                return
            self.log(f"[COMBO] Đang dùng: {self.active_combo}.")
            if not self.config["game"]["skip_restart_game"]:
                self.log("[GAME] Start Clash of Clans.")
                self.adb.start_app(self.config["adb"]["package"])
                self._sleep(10)

            self._publish_stats()
            self.log("[INFO] Bot started.")
            self.run_started_at = time.time()
            auto_stop_after = self._auto_stop_after_seconds()
            self.auto_stop_at = self.run_started_at + auto_stop_after if auto_stop_after > 0 else 0.0
            next_periodic_restart_at = self._next_periodic_restart_at(self.run_started_at)
            cycle_errors = 0
            max_cycle_errors = int(self.config["game"].get("max_consecutive_cycle_errors", 8))
            while not self.stop_event.is_set():
                self._pause_gate()
                if self._auto_stop_due():
                    break
                if next_periodic_restart_at and time.time() >= next_periodic_restart_at:
                    self._periodic_restart_game()
                    next_periodic_restart_at = self._next_periodic_restart_at(time.time())
                    continue
                try:
                    self._run_cycle()
                    cycle_errors = 0
                except ADBError as exc:
                    cycle_errors += 1
                    self.log(f"[WARN] Cycle ADB error ({cycle_errors}): {exc}. Retry next cycle.")
                    if self._too_many_cycle_errors(cycle_errors, max_cycle_errors):
                        break
                    try:
                        self.adb.connect()
                    except ADBError as reconnect_exc:
                        self.log(f"[WARN] ADB reconnect failed: {reconnect_exc}")
                    self._sleep(3)
                except Exception as exc:
                    cycle_errors += 1
                    self.log(f"[WARN] Cycle error ({cycle_errors}): {exc}. Retry next cycle.")
                    if self._too_many_cycle_errors(cycle_errors, max_cycle_errors):
                        break
                    self._sleep(3)
                self._sleep(self.config["timing"]["loop_sleep"])
        except ADBError as exc:
            self.log(f"[ERROR] {exc}")
        except Exception as exc:
            self.log(f"[ERROR] Bot stopped by error: {exc}")
        finally:
            self._publish_stats()
            self.log("[INFO] Bot stopped.")

    def _run_cycle(self) -> None:
        if not self._ensure_home_attack_visible():
            self.log("[HOME] Attack button still missing. Skip this cycle.")
            return

        self._zoom_out_home()

        self.log("[HOME] Tap Attack.")
        self._tap_coord("home_attack")
        self._sleep(self.config["timing"]["after_home_attack"])

        self.log("[MATCH] Tap Find a Match.")
        self._tap_coord("find_match")
        self._sleep(self.config["timing"]["after_find_match"])

        self.log("[ARMY] Confirm Attack in My Army.")
        self._tap_coord("my_army_attack")
        self._sleep(self.config["timing"]["after_my_army_attack"])

        if self._search_base():
            self._attack_base()
            self._wait_return_home()

    def _too_many_cycle_errors(self, cycle_errors: int, max_cycle_errors: int) -> bool:
        if max_cycle_errors <= 0 or cycle_errors < max_cycle_errors:
            return False
        self.log(
            f"[ERROR] Quá nhiều lỗi cycle liên tiếp ({cycle_errors}/{max_cycle_errors}). "
            "Tự động dừng bot."
        )
        self.stop_event.set()
        return True

    def _ocr_ready_or_stop(self) -> bool:
        if self.vision.available:
            return True
        tesseract_path = self.config.get("ocr", {}).get("tesseract_path") or "PATH/default Windows path"
        self.log(
            "[ERROR] OCR chưa sẵn sàng. Kiểm tra ocr.tesseract_path, cài Tesseract OCR, "
            f"và cài Pillow/pytesseract. Hiện tại tesseract_path={tesseract_path!r}."
        )
        self.stop_event.set()
        return False

    def _zoom_out_home(self) -> None:
        zoom_count = int(self.config.get("game", {}).get("home_zoom_out_keyevents", 0))
        if zoom_count <= 0:
            return
        self.log(f"[HOME] Zoom out x{zoom_count}.")
        for _ in range(zoom_count):
            if self.stop_event.is_set():
                return
            if not self._ldplayer_zoom_out():
                self.adb.shell("input", "keyevent", "KEYCODE_ZOOM_OUT", timeout=5)
            self._sleep(0.2)

    def _ldplayer_zoom_out(self) -> bool:
        adb_path = Path(self.config.get("adb", {}).get("path", ""))
        ldconsole = adb_path.with_name("ldconsole.exe") if adb_path.name else Path()
        if not ldconsole.exists():
            return False
        index = str(int(self.config.get("game", {}).get("ldplayer_index", 0)))
        try:
            subprocess.run(
                [str(ldconsole), "zoomOut", "--index", index],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
        except (OSError, subprocess.SubprocessError, ValueError):
            return False
        return True

    def _select_active_combo(self) -> str:
        combos = self.config.get("combos", {})
        if not combos:
            return self.config["farm"].get("combo", "Rong Dien")

        names = list(combos.keys())
        selected = self.config["farm"].get("combo") or names[0]
        if self.config["game"].get("change_combo_on_start", False):
            selected = random.choice(names)
        if selected not in combos:
            selected = names[0]
        self.config["farm"]["combo"] = selected
        return selected

    def _active_deploy(self) -> dict[str, Any]:
        combos = self.config.get("combos", {})
        if self.active_combo in combos:
            return combos[self.active_combo].get("deploy", combos[self.active_combo])
        return self.config["deploy"]

    def _auto_stop_after_seconds(self) -> int:
        game = self.config["game"]
        if not game.get("auto_stop", False):
            return 0
        return max(0, int(game.get("auto_restart_after_seconds", 0)))

    def _auto_stop_due(self) -> bool:
        if self.auto_stop_at <= 0 or time.time() < self.auto_stop_at:
            return False
        elapsed = int(time.time() - self.run_started_at)
        self.log(f"[SCHEDULE] Auto stop sau {elapsed}s.")
        self.stop_event.set()
        return True

    def _next_periodic_restart_at(self, now: float) -> float:
        game = self.config["game"]
        if not game.get("periodic_restart_game", False):
            return 0.0
        min_seconds = max(1, int(game.get("periodic_restart_min_seconds", 3600)))
        max_seconds = max(min_seconds, int(game.get("periodic_restart_max_seconds", min_seconds)))
        delay = random.randint(min_seconds, max_seconds)
        self.log(f"[SCHEDULE] Restart game tiep theo sau {delay}s.")
        return now + delay

    def _periodic_restart_game(self) -> None:
        package = self.config["adb"]["package"]
        wait_seconds = float(self.config["game"].get("restart_wait_seconds", 18))
        self.log("[SCHEDULE] Restart game dinh ky.")
        self._restart_app_interruptible(package, wait_seconds)

    def _ensure_home_attack_visible(self) -> bool:
        game = self.config["game"]
        if not game.get("restart_if_attack_missing", True):
            return True

        retries = int(game.get("attack_missing_retries", 3))
        last_png = b""
        for attempt in range(1, retries + 1):
            self._pause_gate()
            if self.stop_event.is_set():
                return False
            png = self.adb.screencap_png()
            last_png = png
            if self.vision.has_home_attack_button(png):
                if attempt > 1:
                    self.log("[HOME] Attack button found.")
                self.home_restart_failures = 0
                return True
            self.log(f"[HOME] Không thấy nút Attack ({attempt}/{retries}).")
            self._sleep(1)

        self._dump_debug_png("home_attack_missing_before_restart", last_png)
        package = self.config["adb"]["package"]
        wait_seconds = float(game.get("restart_wait_seconds", 18))
        self.log("[HOME] Không thấy nút Attack. Restart game...")
        self._restart_app_interruptible(package, wait_seconds)

        png = self.adb.screencap_png()
        if self.vision.has_home_attack_button(png):
            self.log("[HOME] Restart xong, da thay nut Attack.")
            self.home_restart_failures = 0
            return True

        self._dump_debug_png("home_attack_missing_after_restart", png)
        self.home_restart_failures += 1
        max_failures = int(game.get("max_home_restart_failures", 3))
        self.log(
            f"[HOME] Restart xong nhưng vẫn không thấy nút Attack "
            f"({self.home_restart_failures}/{max_failures})."
        )
        if max_failures > 0 and self.home_restart_failures >= max_failures:
            self.log("[ERROR] Quá nhiều lần restart home thất bại. Tự động dừng bot.")
            self.stop_event.set()
        return False

    def _search_base(self) -> bool:
        max_next = int(self.config["farm"]["max_next"])
        ocr_fail_started_at: float | None = None
        ocr_fail_restart_seconds = float(self.config["farm"].get("ocr_fail_restart_seconds", 30))
        for index in range(max_next):
            self._pause_gate()
            if self.stop_event.is_set():
                return False

            png, loot = self._read_loot_frame()
            if self._loot_is_valid(loot):
                ocr_fail_started_at = None
                dark_label = f"{loot['dark']:,}" if loot.get("dark", -1) >= 0 else "skip"
                self.log(
                    f"[SEARCH] Loot: gold={loot['gold']:,} | elixir={loot['elixir']:,} | "
                    f"dark={dark_label}"
                )
                if self._should_attack(loot):
                    self.stats["attacks"] += 1
                    self._publish_stats()
                    self.log("[SEARCH] Base matched. Deploy troops.")
                    return True

                self.stats["next"] += 1
                self._publish_stats()
                self.log(f"[SEARCH] Base low. Next ({index + 1}/{max_next}).")
                self._tap_coord("next")
                self._sleep(self.config["timing"]["after_next"])
            else:
                if self.vision.has_battle_started(png):
                    self.log("[SEARCH] Da vao battle screen. Continue deploy.")
                    return True
                if ocr_fail_started_at is None:
                    ocr_fail_started_at = time.time()
                fail_seconds = int(time.time() - ocr_fail_started_at)
                self.log(f"[SEARCH] OCR could not read loot ({fail_seconds}s), wait.")
                if fail_seconds >= ocr_fail_restart_seconds:
                    self._dump_debug_png("loot_ocr_fail_restart", png)
                    self.log("[SEARCH] OCR failed too long. Restart game.")
                    self._restart_game_from_search()
                    return False
                self._sleep(self.config["farm"]["search_delay_seconds"])

        self.log("[SEARCH] Max Next reached, try returning home.")
        self._tap_coord("end_battle")
        self._sleep(1)
        self._tap_coord("end_battle_okay")
        return False

    def _restart_game_from_search(self) -> None:
        package = self.config["adb"]["package"]
        wait_seconds = float(self.config["game"].get("restart_wait_seconds", 18))
        self._restart_app_interruptible(package, wait_seconds)

    def _restart_app_interruptible(self, package: str, wait_seconds: float) -> None:
        self.adb.force_stop_app(package)
        self._sleep(1)
        if self.stop_event.is_set():
            return
        self.adb.start_app(package)
        self._sleep(wait_seconds)

    def _attack_base(self) -> None:
        self.current_attack_view = self._selected_attack_view()
        self.manual_slot_counts = self._manual_army_counts()
        self._prepare_camera()
        self._scan_runtime_slots()

        attack_start = time.time()
        if not self._deploy_troops():
            self.log("[ATTACK] Không thả được lính vì thiếu vùng polygon. End battle.")
            self._tap_coord("end_battle")
            self._sleep(1)
            self._tap_coord("end_battle_okay")
            return
        deploy_finished = time.time()
        self._cast_spells(deploy_finished)
        self._activate_post_deploy_slots(deploy_finished)
        self._monitor_battle(attack_start)

    def _prepare_camera(self) -> None:
        deploy = self.active_deploy
        zoom_count = int(deploy.get("zoom_out_keyevents", 0))
        if zoom_count > 0:
            self.log(f"[CAMERA] Zoom out x{zoom_count}.")
            for _ in range(zoom_count):
                self.adb.shell("input", "keyevent", "169", timeout=5)
                self._sleep(0.2)

        swipes = self._camera_swipes_for_current_view()
        if swipes:
            self.log(f"[CAMERA] Move camera {self.current_attack_view or 'default'} x{len(swipes)}.")
        for swipe in swipes:
            self.adb.swipe(*swipe)
            self._sleep(0.35)

        for swipe in deploy.get("pre_attack_swipes", []):
            self.adb.swipe(*swipe)
            self._sleep(0.35)

        self._sleep(float(deploy.get("camera_settle_seconds", 0.5)))

    def _scan_runtime_slots(self) -> None:
        self.runtime_slots = {}
        manual_enabled = self._manual_army_enabled()

        slot_detection = self.config.get("slot_detection", {})
        if not slot_detection.get("enabled", False):
            if manual_enabled:
                self.log("[SLOT] Slot detection tắt, dùng số nhập tay + tọa độ slot cũ.")
            return

        detector = self.slot_detector
        active_kinds = self._active_slot_detection_kinds(detector.kinds)
        if not active_kinds:
            self.log("[SLOT] Combo hiện tại không có kind slot nào cần detect.")
            return
        if not detector.has_templates(active_kinds):
            self.log(f"[SLOT] Chưa có mẫu icon cho combo {self.active_combo}: {', '.join(active_kinds)}.")
            return

        try:
            png = self.adb.screencap_png()
        except ADBError as exc:
            self.log(f"[SLOT] Không chụp được thanh quân để nhận diện: {exc}")
            return

        self.log(f"[SLOT] Detect theo combo {self.active_combo}: {', '.join(active_kinds)}.")
        detections = detector.detect(png, active_kinds)
        manual_remaining = dict(self.manual_slot_counts)
        for detection in detections:
            if manual_enabled:
                detection.count = self._manual_detection_count(detection.kind, manual_remaining)
                if detection.count <= 0:
                    continue
            else:
                detection.count = self.vision.read_slot_count(png, detection.center, detection.kind)
            self.runtime_slots.setdefault(detection.kind, []).append(detection.as_dict())

        if not self.runtime_slots:
            if manual_enabled:
                self.log("[SLOT] Không nhận diện được slot nào, dùng số nhập tay + tọa độ slot cũ.")
            else:
                self.log("[SLOT] Không nhận diện được slot nào, dùng tọa độ slot cũ.")
            return

        details: list[str] = []
        for kind, items in self.runtime_slots.items():
            for item in items:
                count = item.get("count", -1)
                label = count if int(count) >= 0 else "?"
                x, y = item.get("center", [0, 0])
                details.append(f"{kind}=x{label}@{x},{y}")
        self.log("[SLOT] Detected " + " | ".join(details) + ".")

    def _active_slot_detection_kinds(self, supported_kinds: list[str]) -> list[str]:
        supported = set(supported_kinds)
        wanted: list[str] = []

        def add(slot: str) -> None:
            if slot in supported and slot not in wanted:
                wanted.append(slot)

        for step in self.active_deploy.get("sequence", []):
            add(str(step.get("slot", "")))
        for spell in self.active_deploy.get("spells", []):
            if spell.get("enabled", True):
                add(str(spell.get("slot", "")))
        for group in self.active_deploy.get("spell_groups", []):
            if not group.get("enabled", True):
                continue
            for slot in group.get("slots", []):
                add(str(slot))
        return wanted

    def _manual_army_enabled(self) -> bool:
        return bool(self.config.get("manual_army", {}).get("enabled", False))

    def _manual_army_counts(self) -> dict[str, int]:
        if not self._manual_army_enabled():
            return {}
        raw_counts = self.config.get("manual_army", {}).get("counts", {})
        counts: dict[str, int] = {}
        if isinstance(raw_counts, dict):
            for kind, value in raw_counts.items():
                try:
                    counts[str(kind)] = max(0, int(value))
                except (TypeError, ValueError):
                    counts[str(kind)] = 0
        details = " | ".join(f"{kind}={count}" for kind, count in counts.items() if count > 0)
        self.log(f"[ARMY] Dùng số quân nhập tay: {details or 'empty'}.")
        return counts

    def _manual_detection_count(self, kind: str, remaining: dict[str, int]) -> int:
        count = max(0, int(remaining.get(kind, 0)))
        if count <= 0:
            return 0
        if kind == "hero":
            remaining[kind] = count - 1
            return 1
        remaining[kind] = 0
        return count

    def _deploy_troops(self) -> bool:
        points = self._deploy_points()
        if not points:
            self.log("[ATTACK] Chưa có vùng thả lính hợp lệ, skip thả lính.")
            return False
        slot_counts = self._read_deploy_slot_counts()
        deployed_any = False
        for step in self.active_deploy["sequence"]:
            slot = step["slot"]
            count = self._deploy_count_for_step(step, slot_counts)
            if count <= 0:
                self.log(f"[ATTACK] Skip {slot}, slot empty or count unknown.")
                continue
            label = "all" if self._is_all(step.get("count")) else str(count)
            self.log(f"[ATTACK] Select {slot}, deploy {label} (max {count}).")
            select_each_tap = self._select_slot_before_each_tap(slot)
            if not select_each_tap:
                self._tap_slot(slot)
            delay = self._troop_delay_seconds(float(step.get("delay", 0.2)))
            for i in range(count):
                if self._slot_check_due(step, i) and not self._slot_available(slot):
                    self.log(f"[ATTACK] Slot {slot} looks empty, stop deploy.")
                    break
                if select_each_tap:
                    self._tap_slot(slot)
                x, y = points[i % len(points)]
                self.adb.tap(x, y)
                self._consume_runtime_slot(slot)
                deployed_any = True
                self._optimized_action_pause()
                self._sleep(delay)
        return deployed_any

    def _read_deploy_slot_counts(self) -> dict[str, int]:
        if self._manual_army_enabled():
            counts = dict(self.manual_slot_counts)
            details = " | ".join(f"{slot}={count}" for slot, count in counts.items() if count > 0)
            self.log(f"[ATTACK] Manual slot counts: {details or 'empty'}.")
            return counts

        counts: dict[str, int] = {}
        detected_kinds: set[str] = set()

        if self.runtime_slots:
            for kind, items in self.runtime_slots.items():
                counts[kind] = sum(max(0, int(item.get("count", -1))) for item in items)
                detected_kinds.add(kind)

        deploy = self.active_deploy
        fallback_slots: list[str] = []
        for step in deploy.get("sequence", []):
            slot = step.get("slot", "")
            if slot and slot not in detected_kinds and slot not in fallback_slots:
                fallback_slots.append(slot)

        if fallback_slots and deploy.get("scan_slot_counts", True):
            try:
                png = self.adb.screencap_png()
            except ADBError as exc:
                self.log(f"[ATTACK] Slot count scan failed: {exc}")
                png = None
            if png:
                for slot in fallback_slots:
                    coords = self.config["coords"]["slots"].get(slot)
                    if coords:
                        counts[slot] = self.vision.read_slot_count(png, coords, slot)

        if counts:
            details = " | ".join(f"{slot}={count if count >= 0 else '?'}" for slot, count in counts.items())
            self.log(f"[ATTACK] Slot counts: {details}.")
        return counts

    def _deploy_count_for_step(self, step: dict[str, Any], slot_counts: dict[str, int]) -> int:
        slot = step.get("slot", "")
        fallback = self._tap_limit(step.get("count", 0), int(step.get("max_taps", 0)))
        detected = slot_counts.get(slot, -1)

        if detected == 0:
            return 0
        if detected > 0:
            if self._is_all(step.get("count")):
                max_taps = int(step.get("max_taps", detected))
                return min(detected, max_taps) if max_taps > 0 else detected
            return min(fallback, detected)

        if self.active_deploy.get("strict_slot_counts", True):
            return 0
        return fallback

    def _select_slot_before_each_tap(self, slot: str) -> bool:
        if not self.runtime_slots:
            return False
        return len(self.runtime_slots.get(slot, [])) > 1

    def _cast_spells(self, deploy_finished: float) -> None:
        spell_groups = self.active_deploy.get("spell_groups", [])
        if spell_groups:
            self._cast_spell_groups(spell_groups, deploy_finished)
            return

        for spell in self.active_deploy["spells"]:
            if not spell.get("enabled", True):
                continue
            delay = float(spell.get("delay_after_deploy", 0))
            while time.time() - deploy_finished < delay and not self.stop_event.is_set():
                self._sleep(0.1)
            spell_name = spell.get("name", spell["slot"])
            max_casts = int(spell.get("max_casts", 0))
            points = self._spell_zone_points(spell, max_casts)
            if not points:
                self.log(f"[SPELL] Skip {spell_name}, chưa có vùng thả spell.")
                continue
            slot = spell["slot"]
            self.log(f"[SPELL] Cast {spell_name} ({slot}) in zone.")
            for x, y in points:
                if not self._slot_available(slot):
                    self.log(f"[SPELL] Slot {slot} looks empty, stop {spell_name}.")
                    break
                self._tap_slot(slot)
                self._spell_random_delay(spell["slot"])
                self.adb.tap(int(x), int(y))
                self._consume_runtime_slot(slot)
                self._optimized_action_pause()
                self._sleep(0.18)

    def _cast_spell_groups(self, spell_groups: list[dict[str, Any]], deploy_finished: float) -> None:
        for group in spell_groups:
            if not group.get("enabled", True):
                continue
            slots = group.get("slots", [])
            if not slots:
                continue
            delay = float(group.get("delay_after_deploy", 0))
            while time.time() - deploy_finished < delay and not self.stop_event.is_set():
                self._sleep(0.1)

            max_casts = self._tap_limit(group.get("max_casts", 0), 0)
            points = self._spell_zone_points(group, max_casts)
            if not points:
                self.log(f"[SPELL] Skip group {group.get('name', 'spell')}, chưa có vùng thả spell.")
                continue
            delay_between = float(group.get("delay_between_casts", 0.18))
            self.log(f"[SPELL] Group {group.get('name', 'spell')} max {max_casts}.")
            for i in range(max_casts):
                slot = self._first_available_slot(slots)
                if not slot:
                    self.log(f"[SPELL] No available slot in {slots}, skip group.")
                    break
                x, y = points[i % len(points)]
                self.log(f"[SPELL] Cast {slot} at {int(x)},{int(y)}.")
                self._tap_slot(slot)
                self._spell_random_delay(slot)
                self.adb.tap(int(x), int(y))
                self._consume_runtime_slot(slot)
                self._optimized_action_pause()
                self._sleep(delay_between)

    def _spell_zone_points(self, item: dict[str, Any], count: int) -> list[list[int]]:
        view = self.current_attack_view or self._selected_attack_view()
        zones = item.get("zones", {})
        zone = zones.get(view, []) if isinstance(zones, dict) else []
        if len(zone) < 3:
            return []
        return self._random_points_in_polygon(zone, max(1, int(count)))

    def _activate_post_deploy_slots(self, deploy_finished: float) -> None:
        if not self._custom_attack_timing_enabled():
            return

        activations = [
            ("hero", "hero_skill_min_ms", "hero_skill_max_ms", "Skill tướng"),
        ]
        scheduled: list[tuple[float, str, str]] = []
        for slot, min_key, max_key, label in activations:
            if not self._sequence_uses_slot(slot):
                continue
            delay = self._random_timing_seconds(min_key, max_key)
            scheduled.append((delay, slot, label))

        for delay, slot, label in sorted(scheduled):
            while time.time() - deploy_finished < delay and not self.stop_event.is_set():
                self._sleep(0.1)
            if self.stop_event.is_set():
                return
            if slot == "hero":
                hero_search_delay = float(self._attack_timing().get("hero_search_delay_seconds", 0))
                if hero_search_delay > 0:
                    self._sleep(hero_search_delay)
                if self.runtime_slots.get("hero"):
                    self.log("[SKILL] Activate all detected heroes.")
                    for item in self.runtime_slots.get("hero", []):
                        x, y = item.get("center", [0, 0])
                        self.adb.tap(int(x), int(y))
                        self._optimized_action_pause()
                        self._sleep(0.18)
                    continue
            self.log(f"[SKILL] Activate {label} ({slot}).")
            self._tap_slot(slot)

    def _monitor_battle(self, attack_start: float) -> None:
        surrender = self.config["surrender"]
        target_time = random.randint(
            int(surrender["time_min_seconds"]),
            int(surrender["time_max_seconds"]),
        )
        target_damage = random.randint(
            int(surrender["destruction_min_percent"]),
            int(surrender["destruction_max_percent"]),
        )
        max_seconds = min(int(surrender["max_battle_seconds"]), 175)
        best_damage = -1
        last_damage = -1
        last_damage_changed_at = time.time()
        pending_damage: dict[str, int] = {"value": -1, "reads": 0}
        max_jump = int(surrender.get("damage_jump_confirm_percent", 40))
        max_pending_reads = int(surrender.get("damage_jump_max_pending_reads", 3))
        damage_stall_seconds = max(0, int(surrender.get("damage_stall_seconds", 20)))

        self.log(f"[BATTLE] Monitor. time={target_time}s, damage={target_damage}%.")
        while not self.stop_event.is_set():
            self._pause_gate()
            elapsed = int(time.time() - attack_start)
            png = self.adb.screencap_png()
            raw_damage = self.vision.read_damage_percent(png)
            best_damage, pending_damage = self._filter_damage_reading(
                raw_damage,
                best_damage,
                pending_damage,
                max_jump,
                max_pending_reads,
            )
            damage = best_damage
            loot = self.vision.read_loot(png) if self.vision.available else {}
            if damage >= 0 and damage != last_damage:
                last_damage = damage
                last_damage_changed_at = time.time()

            surrender_reason = self._surrender_reason(
                elapsed,
                damage,
                loot,
                target_time,
                target_damage,
            )
            if not surrender["never_surrender"] and surrender_reason:
                self.log(f"[BATTLE] Surrender condition matched: {surrender_reason}.")
                self._tap_coord("end_battle")
                self._sleep(1)
                self._tap_coord("end_battle_okay")
                return

            if (
                not surrender["never_surrender"]
                and damage_stall_seconds > 0
                and damage >= 0
                and time.time() - last_damage_changed_at >= damage_stall_seconds
            ):
                self.log(f"[BATTLE] Damage đứng ở {damage}% quá {damage_stall_seconds}s. End battle.")
                self._tap_coord("end_battle")
                self._sleep(1)
                self._tap_coord("end_battle_okay")
                return

            if elapsed >= max_seconds:
                self.log("[BATTLE] Max battle wait reached.")
                if not surrender["never_surrender"]:
                    self._tap_coord("end_battle")
                    self._sleep(1)
                    self._tap_coord("end_battle_okay")
                return

            shown_damage = "?" if damage < 0 else f"{damage}%"
            self.log(f"[BATTLE] {elapsed}s | damage={shown_damage}")
            self._sleep(3)

    def _filter_damage_reading(
        self,
        raw_damage: int,
        best_damage: int,
        pending_damage: dict[str, int],
        max_jump: int,
        max_pending_reads: int,
    ) -> tuple[int, dict[str, int]]:
        if raw_damage < 0:
            return best_damage, pending_damage
        if raw_damage < best_damage:
            self.log(f"[BATTLE] Ignore OCR damage drop {best_damage}% -> {raw_damage}%.")
            return best_damage, pending_damage

        baseline = max(best_damage, 0)
        if best_damage >= 0 and raw_damage - baseline > max_jump:
            pending_value = int(pending_damage.get("value", -1))
            pending_reads = int(pending_damage.get("reads", 0))
            if pending_value >= 0 and abs(raw_damage - pending_value) <= 5:
                self.log(f"[BATTLE] Confirm OCR damage jump {best_damage}% -> {raw_damage}%.")
                return raw_damage, {"value": -1, "reads": 0}
            pending_reads = pending_reads + 1 if pending_value >= 0 else 1
            if max_pending_reads > 0 and pending_reads >= max_pending_reads:
                self.log(
                    f"[BATTLE] Accept OCR damage jump after hold "
                    f"{best_damage}% -> {raw_damage}% ({pending_reads}/{max_pending_reads})."
                )
                return raw_damage, {"value": -1, "reads": 0}
            self.log(
                f"[BATTLE] Hold OCR damage jump {best_damage}% -> {raw_damage}% "
                f"({pending_reads}/{max_pending_reads}) for confirm."
            )
            return best_damage, {"value": raw_damage, "reads": pending_reads}

        return raw_damage, {"value": -1, "reads": 0}

    def _wait_return_home(self) -> None:
        self.log("[RESULT] Wait result screen.")
        self._sleep(6)
        if self.stop_event.is_set():
            return
        self._record_result_loot()
        self.log("[RESULT] Tap Return Home.")
        self._tap_coord("return_home")
        self._sleep(self.config["timing"]["after_return_home"])
        self._next_battle_random_delay()

    def _record_result_loot(self) -> None:
        if not self.vision.available:
            return
        try:
            png = self.adb.screencap_png()
        except ADBError as exc:
            self.log(f"[RESULT] Không chụp được màn hình kết quả để thống kê: {exc}")
            return
        loot = self.vision.read_result_loot(png)
        gold = int(loot.get("gold", -1))
        elixir = int(loot.get("elixir", -1))
        if gold < 0 and elixir < 0:
            self.log("[RESULT] Không đọc được vàng/dầu trên màn hình kết quả.")
            return
        self.stats["gold_seen"] += max(gold, 0)
        self.stats["elixir_seen"] += max(elixir, 0)
        self._publish_stats()
        gold_label = "?" if gold < 0 else f"{gold:,}"
        elixir_label = "?" if elixir < 0 else f"{elixir:,}"
        self.log(f"[RESULT] Loot thực nhận: gold={gold_label} | elixir={elixir_label}.")

    def _read_loot(self) -> dict[str, int]:
        return self._read_loot_frame()[1]

    def _read_loot_frame(self) -> tuple[bytes, dict[str, int]]:
        if not self.vision.available:
            raise RuntimeError("OCR is not ready, cannot read loot.")
        png = self.adb.screencap_png()
        return png, self.vision.read_loot(png)

    def _loot_is_valid(self, loot: dict[str, int]) -> bool:
        return loot["gold"] >= 0 and loot["elixir"] >= 0

    def _should_attack(self, loot: dict[str, int]) -> bool:
        if not self._loot_is_valid(loot):
            return False
        farm = self.config["farm"]
        gold_ok = loot["gold"] >= int(farm["gold_min"])
        elixir_ok = loot["elixir"] >= int(farm["elixir_min"])
        total_ok = self._loot_total(loot) >= int(farm["total_min"])
        mode = farm.get("threshold_mode", "any")
        if mode == "all":
            return gold_ok and elixir_ok and total_ok
        if mode == "total":
            return total_ok
        return gold_ok or elixir_ok or total_ok

    def _surrender_reason(
        self,
        elapsed: int,
        damage: int,
        loot: dict[str, int],
        target_time: int,
        target_damage: int,
    ) -> str:
        surrender = self.config["surrender"]
        if surrender["by_time"] and elapsed >= target_time:
            return f"time {elapsed}s >= {target_time}s"
        if surrender["by_destruction"] and damage >= target_damage:
            return f"damage {damage}% >= {target_damage}%"
        if surrender["when_low_loot"] and loot:
            total = self._loot_total(loot)
            if total < int(surrender["total_remaining_less_than"]):
                return f"remaining loot {total:,} < {int(surrender['total_remaining_less_than']):,}"
        return ""

    def _loot_total(self, loot: dict[str, int]) -> int:
        return max(loot.get("gold", -1), 0) + max(loot.get("elixir", -1), 0)

    def _deploy_points(self) -> list[list[int]]:
        deploy = self.active_deploy
        view = self.current_attack_view or self._selected_attack_view()
        zone, source = self._deploy_zone_for_view(view)
        if len(zone) >= 3:
            suffix = "default deploy" if source == "default" else "combo deploy"
            self.log(f"[ZONE] Deploy random in zone: {view} ({suffix}).")
            return self._random_points_in_polygon(
                zone,
                int(deploy.get("zone_random_points", 48)),
            )
        self.log(f"[ZONE] Missing deploy zone for {view or 'unknown view'} in combo/default deploy.")
        return []

    def _deploy_zone_for_view(self, view: str) -> tuple[list[list[int]], str]:
        zone = self._valid_polygon(self.active_deploy.get("deploy_zones", {}).get(view, []))
        if zone:
            return zone, "combo"

        base_deploy = self.config.get("deploy", {})
        if base_deploy is not self.active_deploy:
            zone = self._valid_polygon(base_deploy.get("deploy_zones", {}).get(view, []))
            if zone:
                return zone, "default"

        return [], ""

    def _valid_polygon(self, points: Any) -> list[list[int]]:
        if not isinstance(points, list):
            return []
        normalized = [[int(point[0]), int(point[1])] for point in points if isinstance(point, list) and len(point) >= 2]
        return normalized if len(normalized) >= 3 else []

    def _random_points_in_polygon(self, polygon: list[list[int]], count: int) -> list[list[int]]:
        normalized = [[int(point[0]), int(point[1])] for point in polygon if len(point) >= 2]
        if len(normalized) < 3:
            return normalized

        min_x = min(point[0] for point in normalized)
        max_x = max(point[0] for point in normalized)
        min_y = min(point[1] for point in normalized)
        max_y = max(point[1] for point in normalized)
        points: list[list[int]] = []
        attempts = 0
        target_count = max(1, int(count))
        while len(points) < target_count and attempts < target_count * 80:
            attempts += 1
            candidate = [random.randint(min_x, max_x), random.randint(min_y, max_y)]
            if self._point_in_polygon(candidate, normalized):
                points.append(candidate)
        return points or normalized

    def _point_in_polygon(self, point: list[int], polygon: list[list[int]]) -> bool:
        x, y = point
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            intersects = ((yi > y) != (yj > y)) and (
                x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    def _selected_attack_edge(self) -> str:
        edge = self.config["farm"].get("attack_edge", "top")
        valid_edges = ("top", "bottom", "left", "right")
        if edge == "random":
            chosen = random.choice(valid_edges)
            self.log(f"[EDGE] Random edge: {chosen}.")
            return chosen
        if edge == "auto":
            fallback = self.active_deploy.get("auto_edge_fallback", "top")
            self.log(f"[EDGE] Auto edge chưa bật vision kho, fallback {fallback}.")
            return fallback
        if edge in valid_edges:
            return edge
        return "top"

    def _selected_attack_view(self) -> str:
        valid_views = tuple(
            view
            for view in ("trenbenphai", "trenbentrai", "duoibenphai", "duoibentrai")
            if len(self._deploy_zone_for_view(view)[0]) >= 3
        )
        if not valid_views:
            return ""
        configured = self.config["farm"].get("attack_view", "random")
        if configured == "random":
            chosen = random.choice(valid_views)
            self.log(f"[VIEW] Random view: {chosen}.")
            return chosen
        if configured == "auto":
            fallback = valid_views[0]
            self.log(f"[VIEW] Auto view chưa bật vision, fallback {fallback}.")
            return fallback
        if configured in valid_views:
            self.log(f"[VIEW] Selected view: {configured}.")
            return configured
        fallback = valid_views[0]
        self.log(f"[VIEW] Invalid view {configured}, fallback {fallback}.")
        return fallback

    def _camera_swipes_for_current_view(self) -> list[list[int]]:
        deploy = self.active_deploy
        view_swipes = deploy.get("view_camera_swipes", {})
        if self.current_attack_view and self.current_attack_view in view_swipes:
            return view_swipes[self.current_attack_view]
        return deploy.get("camera_swipes", [])

    def _tap_coord(self, name: str) -> None:
        x, y = self.config["coords"][name]
        self.adb.tap(int(x), int(y))
        self._optimized_action_pause()
        self._sleep(self._after_click_seconds())

    def _tap_slot(self, name: str) -> None:
        runtime_slot = self._runtime_slot(name)
        if runtime_slot:
            x, y = runtime_slot["center"]
        else:
            x, y = self.config["coords"]["slots"][name]
        self.adb.tap(int(x), int(y))
        self._optimized_action_pause()
        self._sleep(0.18)

    def _tap_limit(self, value: Any, fallback: int) -> int:
        if self._is_all(value):
            return max(0, int(fallback))
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return max(0, int(fallback))

    def _is_all(self, value: Any) -> bool:
        return isinstance(value, str) and value.strip().lower() == "all"

    def _slot_check_due(self, step: dict[str, Any], index: int) -> bool:
        every = int(step.get("slot_check_every", self.active_deploy.get("slot_check_every", 2)))
        return every > 0 and index % every == 0

    def _slot_available(self, slot: str) -> bool:
        runtime_slot = self._runtime_slot(slot)
        if runtime_slot is not None:
            return True
        if slot in self.runtime_slots:
            return False
        if self._manual_army_enabled():
            return self.manual_slot_counts.get(slot, 0) > 0

        coords = self.config["coords"]["slots"].get(slot)
        if not coords:
            return False
        try:
            png = self.adb.screencap_png()
        except ADBError as exc:
            self.log(f"[WARN] Slot check failed: {exc}")
            return True
        return self.vision.slot_looks_available(png, coords)

    def _first_available_slot(self, slots: list[str]) -> str:
        for slot in slots:
            if self._slot_available(slot):
                return slot
        return ""

    def _runtime_slot(self, kind: str) -> dict[str, Any] | None:
        for item in self.runtime_slots.get(kind, []):
            if int(item.get("count", -1)) != 0:
                return item
        return None

    def _consume_runtime_slot(self, kind: str) -> None:
        item = self._runtime_slot(kind)
        if item:
            count = int(item.get("count", -1))
            if count > 0:
                item["count"] = count - 1
        if self._manual_army_enabled() and self.manual_slot_counts.get(kind, 0) > 0:
            self.manual_slot_counts[kind] -= 1

    def _sequence_uses_slot(self, slot: str) -> bool:
        for step in self.active_deploy.get("sequence", []):
            if step.get("slot") == slot and self._tap_limit(step.get("count", 0), int(step.get("max_taps", 0))) > 0:
                return True
        return False

    def _attack_timing(self) -> dict[str, Any]:
        return self.config.get("attack_timing", {})

    def _custom_attack_timing_enabled(self) -> bool:
        return not bool(self._attack_timing().get("use_default", True))

    def _optimized_action_pause(self) -> None:
        if self._custom_attack_timing_enabled() and self._attack_timing().get("optimized_mode", False):
            self._sleep(0.12)

    def _troop_delay_seconds(self, fallback: float) -> float:
        if not self._custom_attack_timing_enabled():
            return fallback
        timing = self._attack_timing()
        return max(0.0, float(timing.get("troop_delay_ms", int(fallback * 1000))) / 1000.0)

    def _random_timing_seconds(self, min_key: str, max_key: str) -> float:
        timing = self._attack_timing()
        minimum = int(timing.get(min_key, 0))
        maximum = int(timing.get(max_key, minimum))
        if maximum < minimum:
            maximum = minimum
        return random.randint(minimum, maximum) / 1000.0

    def _spell_random_delay(self, slot: str) -> None:
        if not self._custom_attack_timing_enabled():
            return
        timing = self._attack_timing()
        if slot == "freeze":
            minimum = int(timing.get("freeze_random_min_ms", 0))
            maximum = int(timing.get("freeze_random_max_ms", minimum))
        elif slot == "rage":
            minimum = int(timing.get("rage_random_min_ms", 0))
            maximum = int(timing.get("rage_random_max_ms", minimum))
        else:
            return
        if maximum < minimum:
            maximum = minimum
        self._sleep(random.randint(minimum, maximum) / 1000.0)

    def _next_battle_random_delay(self) -> None:
        if not self._custom_attack_timing_enabled():
            return
        timing = self._attack_timing()
        minimum = int(timing.get("next_battle_min_ms", 0))
        maximum = int(timing.get("next_battle_max_ms", minimum))
        if maximum < minimum:
            maximum = minimum
        self._sleep(random.randint(minimum, maximum) / 1000.0)

    def _after_click_seconds(self) -> float:
        if not self._custom_attack_timing_enabled():
            return float(self.config["timing"]["after_click"])
        timing = self._attack_timing()
        return max(0.0, float(timing.get("adb_delay_seconds", self.config["timing"]["after_click"])))

    def _sleep(self, seconds: float) -> None:
        end = time.time() + self._jittered_sleep_seconds(seconds)
        while time.time() < end:
            if self.stop_event.is_set():
                return
            time.sleep(min(0.1, end - time.time()))

    def _jittered_sleep_seconds(self, seconds: float) -> float:
        base = max(0.0, float(seconds))
        timing = self.config.get("timing", {})
        min_seconds = float(timing.get("sleep_jitter_min_seconds", 0.25))
        jitter_percent = max(0.0, float(timing.get("sleep_jitter_percent", 0.15)))
        if base < min_seconds or jitter_percent <= 0:
            return base
        delta = base * jitter_percent
        return max(0.0, random.uniform(base - delta, base + delta))

    def _pause_gate(self) -> None:
        pause_started_at = 0.0
        while self.pause_event.is_set() and not self.stop_event.is_set():
            if pause_started_at <= 0:
                pause_started_at = time.time()
            time.sleep(0.2)
        if pause_started_at > 0 and self.auto_stop_at > 0:
            paused_seconds = time.time() - pause_started_at
            self.auto_stop_at += paused_seconds
            self.log(f"[SCHEDULE] Pause {int(paused_seconds)}s, auto-stop được dời lại.")

    def _load_total_stats(self) -> dict[str, int]:
        try:
            with self.stats_path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError):
            return {key: 0 for key in self.STAT_KEYS}

        total = data.get("total", {})
        return {key: int(total.get(key, 0)) for key in self.STAT_KEYS}

    def _publish_stats(self) -> None:
        payload = self._stats_payload()
        self._save_stats(payload)
        self.stats_callback(payload)

    def _stats_payload(self) -> dict[str, Any]:
        total = {
            key: self.base_total_stats.get(key, 0) + self.stats.get(key, 0)
            for key in self.STAT_KEYS
        }
        return {
            "session_started_at": self.session_started_at,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "current_session": dict(self.stats),
            "total": total,
        }

    def _save_stats(self, payload: dict[str, Any]) -> None:
        try:
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            with self.stats_path.open("w", encoding="utf-8") as file:
                json.dump(payload, file, ensure_ascii=True, indent=2)
        except OSError as exc:
            self.log(f"[WARN] Không ghi được stats.json: {exc}")

    def _dump_debug_png(self, reason: str, png: bytes) -> None:
        if not png:
            return
        safe_reason = self._safe_name(reason)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.debug_dir / f"{self.safe_device}-{timestamp}-{safe_reason}.png"
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
            self.log(f"[DEBUG] Saved screencap: {path}")
        except OSError as exc:
            self.log(f"[WARN] Không ghi được debug screencap: {exc}")

    def _safe_name(self, value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
