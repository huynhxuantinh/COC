from __future__ import annotations

import json
import random
import subprocess
import threading
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from adb_client import ADBClient, ADBError
from builder_vision import BuilderBaseVision, BuilderScreen
from slot_detector import SlotDetector
from stats_store import STAT_KEYS, load_total_stats, merge_existing_stats
from vision import Vision


class FarmBot:
    STAT_KEYS = STAT_KEYS

    def __init__(
        self,
        config: dict[str, Any],
        log,
        stop_event: threading.Event,
        pause_event: threading.Event,
        stats_callback=None,
        lifecycle_callback=None,
    ) -> None:
        self.config = config
        self.log = log
        self.stop_event = stop_event
        self.pause_event = pause_event
        resolution = tuple(config["game"].get("resolution", [1600, 900]))
        self.adb = ADBClient(config["adb"]["path"], config["adb"]["device"], log=log, resolution=resolution)
        self.vision = Vision(config, log=log)
        self.village_vision = BuilderBaseVision(config, log=log, vision=self.vision)
        self.slot_detector = SlotDetector(config, log)
        self.stats = {key: 0 for key in self.STAT_KEYS}
        self.stats_callback = stats_callback or (lambda stats: None)
        self.lifecycle_callback = lifecycle_callback or (lambda event, detail="": None)
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
        self.attacks_since_wall_upgrade = 0
        self.search_ocr_restarts = 0
        self.damage_ocr_restarts = 0
        self.next_periodic_restart_at = 0.0
        self._paused_seconds_total = 0.0

    def run(self) -> None:
        try:
            if self.config["adb"]["connect_on_start"]:
                self.adb.connect()
            if not self._ocr_ready_or_stop():
                self._notify_lifecycle("error", "OCR chưa sẵn sàng.")
                return
            if not self._slot_inputs_ready_or_stop():
                return
            self.log(f"[COMBO] Đang dùng: {self.active_combo}.")
            if not self.config["game"]["skip_restart_game"]:
                self.log("[GAME] Start Clash of Clans.")
                self._start_app(self.config["adb"]["package"])
                self._sleep(10)

            self._publish_stats()
            self.log("[INFO] Bot started.")
            self._notify_lifecycle("running")
            self.run_started_at = time.time()
            auto_stop_after = self._auto_stop_after_seconds()
            self.auto_stop_at = self.run_started_at + auto_stop_after if auto_stop_after > 0 else 0.0
            self.next_periodic_restart_at = self._next_periodic_restart_at(self.run_started_at)
            cycle_errors = 0
            max_cycle_errors = int(self.config["game"].get("max_consecutive_cycle_errors", 8))
            while not self.stop_event.is_set():
                self._pause_gate()
                if self._auto_stop_due():
                    break
                if self.next_periodic_restart_at and time.time() >= self.next_periodic_restart_at:
                    self._periodic_restart_game()
                    self.next_periodic_restart_at = self._next_periodic_restart_at(time.time())
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
            self._notify_lifecycle("error", str(exc))
        except Exception as exc:
            self.log(f"[ERROR] Bot stopped by error: {exc}")
            self._notify_lifecycle("error", str(exc))
        finally:
            self._publish_stats()
            self.log("[INFO] Bot stopped.")
            self._notify_lifecycle("stopped")

    def _notify_lifecycle(self, event: str, detail: str = "") -> None:
        try:
            self.lifecycle_callback(event, detail)
        except Exception:
            pass

    def _run_cycle(self) -> None:
        if not self._ensure_main_village():
            return
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
            attack_result = self._attack_base()
            state = str(attack_result.get("state", ""))
            if state in {"stopped", "restarted"} or self.stop_event.is_set():
                return
            if state == "result" and not self._wait_return_home():
                return
            if attack_result.get("attacked", False):
                self.attacks_since_wall_upgrade += 1
                if self._wall_upgrade_due():
                    wall_result = self._upgrade_walls()
                    if not wall_result["success"]:
                        self._backoff_wall_upgrade(str(wall_result["reason"]))

    def _ensure_main_village(self) -> bool:
        if not hasattr(self, "village_vision"):
            return True
        png = self._screencap_png()
        state = self.village_vision.classify(png)
        if state == BuilderScreen.MAIN_HOME:
            return True
        if state == BuilderScreen.BUILDER_HOME:
            return self._travel_to_main_village(png)
        if state == BuilderScreen.RESULT:
            self.log("[HOME] Đang ở kết quả Làng đêm. Về nhà trước.")
            point = self.config.get("builder_base", {}).get("coords", {}).get("return_home", [800, 760])
            self._tap(point, jitter=0)
            self._sleep(float(self.config.get("builder_base", {}).get("timing", {}).get("result_wait_seconds", 12)))
            return False
        if state in {BuilderScreen.STAGE_PREP, BuilderScreen.BATTLE}:
            self.log("[HOME] Trận Làng đêm chưa kết thúc. Chờ về nhà rồi mới chạy Làng chính.")
            return False
        return True

    def _travel_to_main_village(self, png: bytes = b"") -> bool:
        entry = self.config.get("builder_base", {}).get("entry", {})
        self.log("[HOME] Đang ở Làng đêm. Tìm thuyền về Làng chính.")
        for _ in range(max(0, int(entry.get("return_zoom_out_count", 4)))):
            if self.stop_event.is_set():
                return False
            if not self._ldplayer_zoom_out():
                self._shell("input", "keyevent", "KEYCODE_ZOOM_OUT", timeout=5)
            self._sleep(0.25)
        for swipe in entry.get("return_camera_swipes", [[950, 350, 650, 650, 500]]):
            self._swipe(swipe)
            self._sleep(0.8)

        attempts = max(1, int(entry.get("boat_search_attempts", 3)))
        last_png = png
        moved_from_stage2 = False
        for attempt in range(1, attempts + 1):
            last_png = self._screencap_png()
            if self.village_vision.classify(last_png) == BuilderScreen.MAIN_HOME:
                return True
            boat = self.village_vision.find_return_boat(last_png)
            if boat is None:
                if not moved_from_stage2:
                    self.log("[HOME] Chưa thấy thuyền. Có thể đang ở map 2 Làng đêm; kéo về map 1.")
                    for swipe in entry.get(
                        "stage2_to_stage1_swipes",
                        [[1200, 700, 400, 200, 700]] * 3,
                    ):
                        self._swipe(swipe)
                        self._sleep(0.6)
                    for swipe in entry.get("return_camera_swipes", []):
                        self._swipe(swipe)
                        self._sleep(0.6)
                    moved_from_stage2 = True
                    continue
                self.log(f"[HOME] Chưa thấy thuyền về Làng chính ({attempt}/{attempts}).")
                self._sleep(1)
                continue

            x, y, score = boat
            self.log(f"[HOME] Bấm thuyền về Làng chính tại {x},{y} (score={score:.2f}).")
            self._tap([x, y], jitter=0)
            self._sleep(2)
            focused_png = self._screencap_png()
            if self.village_vision.classify(focused_png) == BuilderScreen.MAIN_HOME:
                return True
            focused_boat = self.village_vision.find_return_boat(focused_png)
            if focused_boat is not None:
                self._tap([focused_boat[0], focused_boat[1]], jitter=0)
            self._sleep(float(entry.get("travel_wait_seconds", 8)))
            arrived_png = self._screencap_png()
            if self.village_vision.classify(arrived_png) == BuilderScreen.MAIN_HOME:
                self.log("[HOME] Đã về Làng chính.")
                return True
            last_png = arrived_png

        self._dump_debug_png("main-village-return-failed", last_png)
        self.log("[HOME][WARN] Không thể về Làng chính bằng thuyền.")
        return False

    def _too_many_cycle_errors(self, cycle_errors: int, max_cycle_errors: int) -> bool:
        if max_cycle_errors <= 0 or cycle_errors < max_cycle_errors:
            return False
        self.log(
            f"[ERROR] Quá nhiều lỗi cycle liên tiếp ({cycle_errors}/{max_cycle_errors}). "
            "Tự động dừng bot."
        )
        self._notify_lifecycle("error", "Quá nhiều lỗi cycle liên tiếp.")
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
                self._shell("input", "keyevent", "KEYCODE_ZOOM_OUT", timeout=5)
            self._sleep(0.2)

    def _ldplayer_zoom_out(self) -> bool:
        adb_path = Path(self.config.get("adb", {}).get("path", ""))
        ldconsole = adb_path.with_name("ldconsole.exe") if adb_path.name else Path()
        if not ldconsole.exists():
            return False
        index = str(int(self.config.get("game", {}).get("ldplayer_index", 0)))
        self._pause_gate()
        if self.stop_event.is_set():
            return False
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
            png = self._screencap_png()
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

        png = self._screencap_png()
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
            self._notify_lifecycle("error", "Quá nhiều lần restart home thất bại.")
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
                self.search_ocr_restarts = 0
                self.log(f"[SEARCH] Loot: gold={loot['gold']:,} | elixir={loot['elixir']:,}")
                if self._should_attack(loot):
                    self.log("[SEARCH] Base matched. Deploy troops.")
                    return True

                self.stats["next"] += 1
                self._publish_stats()
                self.log(f"[SEARCH] Base low. Next ({index + 1}/{max_next}).")
                self._tap_coord("next")
                self._sleep(self.config["timing"]["after_next"])
            else:
                if self.vision.has_battle_started(png):
                    self.search_ocr_restarts = 0
                    self.log("[SEARCH] Da vao battle screen. Continue deploy.")
                    return True
                if ocr_fail_started_at is None:
                    ocr_fail_started_at = self._active_time()
                fail_seconds = int(self._active_time() - ocr_fail_started_at)
                self.log(f"[SEARCH] OCR could not read loot ({fail_seconds}s), wait.")
                if fail_seconds >= ocr_fail_restart_seconds:
                    self._dump_debug_png("loot_ocr_fail_restart", png)
                    self.search_ocr_restarts += 1
                    max_restarts = max(1, int(self.config["farm"].get("max_ocr_restarts", 3)))
                    if self.search_ocr_restarts >= max_restarts:
                        self.log(
                            f"[ERROR] OCR loot loi lien tiep {self.search_ocr_restarts}/{max_restarts} lan. Dung bot."
                        )
                        self._notify_lifecycle("error", "OCR loot lỗi liên tiếp.")
                        self.stop_event.set()
                        return False
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
        self._force_stop_app(package)
        self._sleep(1)
        if self.stop_event.is_set():
            return
        self._start_app(package)
        self._sleep(wait_seconds)

    def _attack_base(self) -> dict[str, Any]:
        self.current_attack_view = self._selected_attack_view()
        self.manual_slot_counts = self._manual_army_counts()
        self._prepare_camera()
        if self.stop_event.is_set():
            return {"state": "stopped", "attacked": False}
        self._scan_runtime_slots()

        attack_start = self._active_time()
        deploy_result = self._deploy_troops()
        if deploy_result.get("reason") == "stopped":
            return {"state": "stopped", "attacked": bool(deploy_result.get("deployed", False))}
        if not deploy_result["deployed"]:
            reason = deploy_result["reason"]
            if reason == "missing_zone":
                self.log("[ATTACK] Không thả được lính vì thiếu vùng polygon. End battle.")
            elif reason == "unknown_counts":
                self.log("[ATTACK] Không thả được lính vì không đọc được số quân/slot. End battle.")
                self._dump_debug_png("deploy-slot-count-unknown")
            elif reason == "empty_slots":
                self.log("[ATTACK] Không thả được lính vì các slot đều hết hoặc bằng 0. End battle.")
            else:
                self.log("[ATTACK] Không thả được lính. End battle.")
            if self.stop_event.is_set() or reason == "stopped":
                return {"state": "stopped", "attacked": False}
            self._tap_coord("end_battle")
            self._sleep(1)
            self._tap_coord("end_battle_okay")
            return {"state": "result", "attacked": False}
        self.stats["attacks"] += 1
        self._publish_stats()
        deploy_finished = self._active_time()
        self._cast_spells(deploy_finished)
        if self.stop_event.is_set():
            return {"state": "stopped", "attacked": True}
        self._activate_post_deploy_slots(deploy_finished)
        if self.stop_event.is_set():
            return {"state": "stopped", "attacked": True}
        state = self._monitor_battle(attack_start)
        return {"state": state, "attacked": True}

    def _prepare_camera(self) -> None:
        deploy = self.active_deploy
        zoom_count = int(deploy.get("zoom_out_keyevents", 0))
        if zoom_count > 0:
            self.log(f"[CAMERA] Zoom out x{zoom_count}.")
            for _ in range(zoom_count):
                self._pause_gate()
                if self.stop_event.is_set():
                    return
                self._shell("input", "keyevent", "169", timeout=5)
                self._sleep(0.2)

        swipes = self._camera_swipes_for_current_view()
        if swipes:
            self.log(f"[CAMERA] Move camera {self.current_attack_view or 'default'} x{len(swipes)}.")
        for swipe in swipes:
            self._pause_gate()
            if self.stop_event.is_set():
                return
            self._swipe(swipe)
            self._sleep(0.35)

        for swipe in deploy.get("pre_attack_swipes", []):
            self._pause_gate()
            if self.stop_event.is_set():
                return
            self._swipe(swipe)
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
        if not detector.has_any_template(active_kinds):
            self.log(f"[SLOT] Chưa có mẫu icon cho combo {self.active_combo}: {', '.join(active_kinds)}.")
            return

        try:
            png = self._screencap_png()
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
        for group in self.config.get("deploy", {}).get("spell_groups", []):
            if not group.get("enabled", True):
                continue
            for slot in group.get("slots", []):
                add(str(slot))
        return wanted

    def _manual_army_enabled(self) -> bool:
        return bool(self.config.get("manual_army", {}).get("enabled", False))

    def _active_manual_army_kinds(self) -> list[str]:
        wanted: list[str] = []

        def add(slot: str) -> None:
            if slot and slot not in wanted:
                wanted.append(slot)

        for step in self.active_deploy.get("sequence", []):
            add(str(step.get("slot", "")))
        for group in self.config.get("deploy", {}).get("spell_groups", []):
            if not group.get("enabled", True):
                continue
            for slot in group.get("slots", []):
                add(str(slot))
        return wanted

    def _slot_inputs_ready_or_stop(self) -> bool:
        detection_enabled = bool(self.config.get("slot_detection", {}).get("enabled", False))
        fallback_slots = self.config.get("coords", {}).get("slots", {})
        required: list[str] = []

        def add(kind: str) -> None:
            if kind and kind not in required:
                required.append(kind)

        for step in self.active_deploy.get("sequence", []):
            if self._tap_limit(step.get("count", 0), int(step.get("max_taps", 0))) > 0:
                add(str(step.get("slot", "")))
        for group in self.config.get("deploy", {}).get("spell_groups", []):
            if not group.get("enabled", True) or int(group.get("max_casts", 0)) <= 0:
                continue
            for slot in group.get("slots", []):
                add(str(slot))

        missing: list[str] = []
        for kind in required:
            coords = fallback_slots.get(kind) if isinstance(fallback_slots, dict) else None
            has_fallback = isinstance(coords, list) and len(coords) >= 2
            has_template = detection_enabled and self.slot_detector.has_usable_template(kind)
            if not has_fallback and not has_template:
                missing.append(kind)
        if not missing:
            return True

        details = ", ".join(missing)
        self.log(
            f"[ERROR] Combo {self.active_combo} thiếu cách chọn slot: {details}. "
            "Mỗi slot cần template nhận diện hợp lệ hoặc tọa độ fallback."
        )
        self._notify_lifecycle("error", f"Thiếu template/tọa độ slot: {details}.")
        self.stop_event.set()
        return False

    def _manual_army_counts(self) -> dict[str, int]:
        if not self._manual_army_enabled():
            return {}
        raw_counts = self.config.get("manual_army", {}).get("counts", {})
        allowed = set(self._active_manual_army_kinds())
        counts: dict[str, int] = {}
        if isinstance(raw_counts, dict):
            for kind, value in raw_counts.items():
                kind = str(kind)
                if allowed and kind not in allowed:
                    continue
                try:
                    counts[kind] = max(0, int(value))
                except (TypeError, ValueError):
                    counts[kind] = 0
        details = " | ".join(f"{kind}={count}" for kind, count in counts.items() if count > 0)
        self.log(f"[ARMY] Manual counts for combo {self.active_combo}: {details or 'empty'}.")
        return counts

    def _manual_detection_count(self, kind: str, remaining: dict[str, int]) -> int:
        count = max(0, int(remaining.get(kind, 0)))
        if count <= 0:
            if kind != "hero" and self.manual_slot_counts.get(kind, 0) > 0:
                self.log(f"[SLOT] Bỏ qua slot {kind} trùng/ngoài số lượng thủ công.")
            return 0
        if kind == "hero":
            remaining[kind] = count - 1
            return 1
        remaining[kind] = 0
        return count

    def _deploy_troops(self) -> dict[str, Any]:
        if self.stop_event.is_set():
            return {"deployed": False, "reason": "stopped"}
        points = self._deploy_points()
        if not points:
            self.log("[ATTACK] Chưa có vùng thả lính hợp lệ, skip thả lính.")
            return {"deployed": False, "reason": "missing_zone"}
        slot_counts = self._read_deploy_slot_counts()
        deployed_any = False
        unknown_slots: list[str] = []
        zero_slots: list[str] = []
        for step in self.active_deploy["sequence"]:
            self._pause_gate()
            if self.stop_event.is_set():
                return {"deployed": deployed_any, "reason": "stopped"}
            slot = step["slot"]
            if slot_counts.get(slot, -1) < 0 and self.active_deploy.get("strict_slot_counts", True):
                unknown_slots.append(slot)
            count = self._deploy_count_for_step(step, slot_counts)
            if count <= 0:
                if slot not in unknown_slots:
                    zero_slots.append(slot)
                self.log(f"[ATTACK] Skip {slot}, slot empty or count unknown.")
                continue
            label = "all" if self._is_all(step.get("count")) else str(count)
            self.log(f"[ATTACK] Select {slot}, deploy {label} (max {count}).")
            select_each_tap = self._select_slot_before_each_tap(slot)
            if not select_each_tap and not self._tap_slot(slot):
                self.log(f"[ATTACK] Khong co vi tri slot {slot}, skip.")
                unknown_slots.append(slot)
                continue
            delay = self._troop_delay_seconds(float(step.get("delay", 0.2)))
            deployed_for_step = 0
            for i in range(count):
                self._pause_gate()
                if self.stop_event.is_set():
                    return {"deployed": deployed_any, "reason": "stopped"}
                if self._slot_check_due(step, i) and not self._slot_available(slot):
                    self.log(f"[ATTACK] Slot {slot} looks empty, stop deploy.")
                    break
                if select_each_tap and not self._tap_slot(slot):
                    self.log(f"[ATTACK] Khong con vi tri slot {slot}, stop deploy.")
                    break
                x, y = points[i % len(points)]
                self._tap([x, y])
                self._consume_runtime_slot(slot)
                deployed_any = True
                deployed_for_step += 1
                self._optimized_action_pause()
                self._sleep(delay)
            if slot_counts.get(slot, -1) > 0:
                slot_counts[slot] = max(0, int(slot_counts[slot]) - deployed_for_step)
        if deployed_any:
            return {"deployed": True, "reason": ""}
        if unknown_slots:
            self.log(f"[ATTACK] Slot không đọc được số lượng: {', '.join(unknown_slots)}.")
            return {"deployed": False, "reason": "unknown_counts"}
        if zero_slots:
            return {"deployed": False, "reason": "empty_slots"}
        return {"deployed": False, "reason": "no_sequence"}

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
                png = self._screencap_png()
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
        spell_groups = self.config.get("deploy", {}).get("spell_groups", [])
        if not spell_groups:
            self.log("[SPELL] Chưa cấu hình spell_groups, skip thả thuốc.")
            return
        self._cast_spell_groups(spell_groups, deploy_finished)

    def _cast_spell_groups(self, spell_groups: list[dict[str, Any]], deploy_finished: float) -> None:
        for group in spell_groups:
            if not group.get("enabled", True):
                continue
            slots = group.get("slots", [])
            if not slots:
                continue
            delay = float(group.get("delay_after_deploy", 0))
            while self._active_time() - deploy_finished < delay and not self.stop_event.is_set():
                self._pause_gate()
                self._sleep(0.1)

            max_casts = self._tap_limit(group.get("max_casts", 0), 0)
            points = self._spell_zone_points(group, max_casts)
            if not points:
                self.log(f"[SPELL] Skip group {group.get('name', 'spell')}, chưa có vùng thả spell.")
                continue
            delay_between = float(group.get("delay_between_casts", 0.18))
            self.log(f"[SPELL] Group {group.get('name', 'spell')} max {max_casts}.")
            if len(points) < max_casts:
                self.log(
                    f"[SPELL] Chỉ tạo được {len(points)}/{max_casts} điểm đủ khoảng cách, "
                    "giảm khoảng cách hoặc mở rộng vùng nếu muốn cast nhiều hơn."
                )
            for i, point in enumerate(points[:max_casts]):
                self._pause_gate()
                if self.stop_event.is_set():
                    return
                slot = self._first_available_slot(slots)
                if not slot:
                    self.log(f"[SPELL] No available slot in {slots}, skip group.")
                    break
                x, y = point
                self.log(f"[SPELL] Cast {slot} at {int(x)},{int(y)}.")
                if not self._tap_slot(slot):
                    self.log(f"[SPELL] Khong co vi tri slot {slot}, dung group.")
                    break
                self._spell_random_delay(slot)
                self._tap([int(x), int(y)])
                self._consume_runtime_slot(slot)
                self._optimized_action_pause()
                self._sleep(delay_between)

    def _spell_zone_points(self, item: dict[str, Any], count: int) -> list[list[int]]:
        view = self.current_attack_view or self._selected_attack_view()
        zones = item.get("zones", {})
        zone = zones.get(view, []) if isinstance(zones, dict) else []
        if len(zone) < 3:
            return []
        min_distance = int(self._attack_timing().get("spell_min_point_distance_px", 0))
        return self._random_points_in_polygon(zone, max(1, int(count)), min_distance_px=min_distance)

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
            while self._active_time() - deploy_finished < delay and not self.stop_event.is_set():
                self._pause_gate()
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
                        self._pause_gate()
                        if self.stop_event.is_set():
                            return
                        x, y = item.get("center", [0, 0])
                        self._tap([int(x), int(y)])
                        self._optimized_action_pause()
                        self._sleep(0.18)
                    continue
            self.log(f"[SKILL] Activate {label} ({slot}).")
            self._tap_slot(slot)

    def _monitor_battle(self, attack_start: float) -> str:
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
        last_damage_changed_at = self._active_time()
        pending_damage: dict[str, int] = {"value": -1, "reads": 0}
        max_jump = int(surrender.get("damage_jump_confirm_percent", 40))
        max_pending_reads = int(surrender.get("damage_jump_max_pending_reads", 3))
        damage_stall_seconds = max(0, int(surrender.get("damage_stall_seconds", 20)))
        damage_unknown_restart_seconds = max(0, int(surrender.get("damage_unknown_restart_seconds", 20)))
        max_damage_ocr_restarts = max(1, int(surrender.get("max_damage_ocr_restarts", 3)))
        damage_unknown_started_at: float | None = None
        read_battle_loot = bool(surrender.get("when_low_loot", False)) and not bool(
            surrender.get("never_surrender", False)
        )

        self.log(f"[BATTLE] Monitor. time={target_time}s, damage={target_damage}%.")
        while not self.stop_event.is_set():
            self._pause_gate()
            if self.stop_event.is_set():
                return "stopped"
            now = self._active_time()
            elapsed = int(now - attack_start)
            png = self._screencap_png()
            raw_damage = self.vision.read_damage_percent(png)
            if raw_damage < 0:
                if damage_unknown_started_at is None:
                    damage_unknown_started_at = now
                unknown_seconds = int(now - damage_unknown_started_at)
                if damage_unknown_restart_seconds > 0 and unknown_seconds >= damage_unknown_restart_seconds:
                    self._dump_debug_png("damage_ocr_unknown_restart", png)
                    self.log(
                        f"[BATTLE] Damage OCR '?' quá {unknown_seconds}s. Restart game."
                    )
                    self.damage_ocr_restarts += 1
                    if self.damage_ocr_restarts >= max_damage_ocr_restarts:
                        self.log(
                            f"[ERROR] Damage OCR loi lien tiep "
                            f"{self.damage_ocr_restarts}/{max_damage_ocr_restarts} lan. Dung bot."
                        )
                        self._notify_lifecycle("error", "Damage OCR lỗi liên tiếp.")
                        self.stop_event.set()
                        return "stopped"
                    self._restart_game_from_search()
                    return "restarted"
            else:
                damage_unknown_started_at = None
                self.damage_ocr_restarts = 0
            best_damage, pending_damage = self._filter_damage_reading(
                raw_damage,
                best_damage,
                pending_damage,
                max_jump,
                max_pending_reads,
            )
            damage = best_damage
            loot = self.vision.read_loot(png) if read_battle_loot and self.vision.available else {}
            if damage >= 0 and damage != last_damage:
                last_damage = damage
                last_damage_changed_at = now

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
                return "result"

            if (
                damage_stall_seconds > 0
                and damage >= 0
                and now - last_damage_changed_at >= damage_stall_seconds
            ):
                self.log(f"[BATTLE] Damage đứng ở {damage}% quá {damage_stall_seconds}s. End battle.")
                self._tap_coord("end_battle")
                self._sleep(1)
                self._tap_coord("end_battle_okay")
                return "result"

            if elapsed >= max_seconds:
                self.log("[BATTLE] Max battle wait reached.")
                if not surrender["never_surrender"]:
                    self._tap_coord("end_battle")
                    self._sleep(1)
                    self._tap_coord("end_battle_okay")
                return "result"

            shown_damage = "?" if damage < 0 else f"{damage}%"
            self.log(f"[BATTLE] {elapsed}s | damage={shown_damage}")
            self._sleep(3)
        return "stopped"

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
        if raw_damage - baseline > max_jump:
            pending_value = int(pending_damage.get("value", -1))
            pending_reads = int(pending_damage.get("reads", 0))
            same_cluster = pending_value >= 0 and abs(raw_damage - pending_value) <= 5
            if same_cluster:
                pending_reads += 1
                self.log(f"[BATTLE] Confirm OCR damage jump {best_damage}% -> {raw_damage}%.")
                return raw_damage, {"value": -1, "reads": 0}
            pending_reads = 1
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

    def _wait_return_home(self) -> bool:
        self.log("[RESULT] Wait result screen.")
        wait_seconds = max(1.0, float(self.config.get("game", {}).get("result_wait_seconds", 15)))
        deadline = self._active_time() + wait_seconds
        result_png = b""
        while self._active_time() < deadline and not self.stop_event.is_set():
            self._pause_gate()
            if self.stop_event.is_set():
                return False
            result_png = self._screencap_png()
            if self.vision.has_return_home_button(result_png):
                break
            self._sleep(0.8)
        else:
            if self.stop_event.is_set():
                return False
            self._dump_debug_png("result_screen_timeout", result_png)
            self.log("[RESULT] Khong thay nut Return Home. Restart game.")
            self._restart_game_from_search()
            return False

        self._record_result_loot(result_png)
        self.log("[RESULT] Tap Return Home.")
        self._tap_coord("return_home")
        self._sleep(self.config["timing"]["after_return_home"])
        if self.stop_event.is_set():
            return False
        home_png = self._screencap_png()
        if not self.vision.has_home_attack_button(home_png):
            self._dump_debug_png("return_home_not_confirmed", home_png)
            self.log("[RESULT] Chua ve lang thanh cong. Thu lai o cycle sau.")
            return False
        self._next_battle_random_delay()
        return True

    def _record_result_loot(self, png: bytes = b"") -> None:
        if not self.vision.available or not self.config.get("game", {}).get("resource_stats", True):
            return
        gold, elixir = self._read_result_loot_stable(png)
        if gold < 0 and elixir < 0:
            self.log("[RESULT] Kết quả OCR không ổn định, bỏ qua thống kê trận này.")
            return
        self.stats["gold_seen"] += max(gold, 0)
        self.stats["elixir_seen"] += max(elixir, 0)
        self._publish_stats()
        gold_label = "?" if gold < 0 else f"{gold:,}"
        elixir_label = "?" if elixir < 0 else f"{elixir:,}"
        self.log(f"[RESULT] Loot thực nhận: gold={gold_label} | elixir={elixir_label}.")

    def _read_result_loot_stable(self, png: bytes = b"") -> tuple[int, int]:
        settings = self.config.get("ocr", {}).get("result_stats", {})
        attempts = max(2, int(settings.get("read_attempts", 3)))
        delay = max(0.0, float(settings.get("read_delay_seconds", 0.3)))
        samples: list[dict[str, int]] = []

        for attempt in range(attempts):
            if self.stop_event.is_set():
                break
            try:
                current_png = png if attempt == 0 and png else self._screencap_png()
            except ADBError as exc:
                self.log(f"[RESULT] Chụp mẫu OCR lỗi ({attempt + 1}/{attempts}): {exc}")
                continue
            loot = self.vision.read_result_loot(current_png)
            samples.append(
                {
                    "gold": int(loot.get("gold", -1)),
                    "elixir": int(loot.get("elixir", -1)),
                }
            )
            if attempt < attempts - 1:
                self._sleep(delay)

        gold = self._stable_number([sample["gold"] for sample in samples])
        elixir = self._stable_number([sample["elixir"] for sample in samples])
        gold_max = max(1, int(settings.get("gold_max", 10_000_000)))
        elixir_max = max(1, int(settings.get("elixir_max", 10_000_000)))

        if gold > gold_max:
            self.log(f"[RESULT][WARN] OCR vàng vượt cap: {gold:,} > {gold_max:,}; bỏ qua.")
            gold = -1
        if elixir > elixir_max:
            self.log(f"[RESULT][WARN] OCR dầu vượt cap: {elixir:,} > {elixir_max:,}; bỏ qua.")
            elixir = -1
        return gold, elixir

    def _wall_upgrade_due(self) -> bool:
        settings = self.config.get("wall_upgrade", {})
        if not settings.get("enabled", False):
            return False

        if self.attacks_since_wall_upgrade < 0:
            return False

        if bool(settings.get("run_after_attacks_enabled", True)):
            every = int(settings.get("run_every_n_attacks", 20))
            if every > 0 and self.attacks_since_wall_upgrade >= every:
                return True

        resources = self._read_home_resources_stable(settings)
        if not resources:
            return False
        threshold = max(0.0, float(settings.get("trigger_percent", 95))) / 100.0
        gold_capacity = max(1.0, float(settings.get("gold_capacity", 1)))
        elixir_capacity = max(1.0, float(settings.get("elixir_capacity", 1)))
        gold_full = resources.get("gold", -1) >= threshold * gold_capacity
        elixir_full = resources.get("elixir", -1) >= threshold * elixir_capacity
        return gold_full or elixir_full

    def _wall_upgrade_budget(self) -> tuple[str, int, str, dict[str, int] | None]:
        settings = self.config.get("wall_upgrade", {})
        resources = self._read_home_resources_stable(settings)
        if not resources:
            return "", 0, "read_resources_failed", None
        selected = self._select_wall_payment_from_resources(settings, resources)
        if not selected:
            return "", 0, "budget_unavailable", resources
        pay_with, budget = selected
        return pay_with, budget, "", resources

    def _select_wall_payment_from_resources(
        self,
        settings: dict[str, Any],
        resources: dict[str, int],
        costs: dict[str, int] | None = None,
    ) -> tuple[str, int] | None:
        gold = int(resources.get("gold", -1))
        elixir = int(resources.get("elixir", -1))
        if gold < 0 or elixir < 0:
            self.log("[WALL] Khong doc duoc vang/dau o lang, bo qua lan nay.")
            return None

        budgets = {
            "gold": max(0, gold - int(settings.get("reserve_gold", 0))),
            "elixir": max(0, elixir - int(settings.get("reserve_elixir", 0))),
        }
        pay_with = str(settings.get("pay_with", "auto")).lower()
        order = [pay_with] if pay_with in {"gold", "elixir"} else sorted(
            budgets,
            key=lambda kind: budgets[kind],
            reverse=True,
        )
        for kind in order:
            budget = budgets[kind]
            if budget <= 0:
                continue
            if costs is not None and int(costs.get(kind, -1)) > budget:
                continue
            return kind, budget
        return None

    def _wall_result(self, success: bool, reason: str = "") -> dict[str, Any]:
        return {"success": success, "reason": reason}

    def _backoff_wall_upgrade(self, reason: str) -> None:
        settings = self.config.get("wall_upgrade", {})
        temporary_reasons = {
            "read_cost_failed",
            "rollback_read_failed",
            "read_resources_failed",
            "confirmation_read_failed",
            "confirmation_mismatch",
            "upgrade_verify_failed",
        }
        key = "temporary_retry_backoff_attacks" if reason in temporary_reasons else "retry_backoff_attacks"
        retry_after = max(1, int(settings.get(key, 20)))
        self.attacks_since_wall_upgrade = -retry_after
        self.log(f"[WALL] Nang tuong that bai ({reason or 'unknown'}), nghi thu lai sau {retry_after} tran.")

    def _upgrade_walls(self) -> dict[str, Any]:
        settings = self.config.get("wall_upgrade", {})
        coords = settings.get("coords", {})
        pay_with, budget, budget_reason, resources_before = self._wall_upgrade_budget()
        if not pay_with or budget <= 0:
            self.log("[WALL] Khong du ngan sach sau khi tru du tru, bo qua.")
            return self._wall_result(False, budget_reason or "budget_unavailable")

        self.log(f"[WALL] Bat dau nang tuong. Ngan sach: {budget:,} {pay_with}.")
        self._tap(coords["builder_icon"])
        self._sleep(1.4)

        wall_pos = self._find_wall_row(settings)
        if not wall_pos:
            self.log("[WALL] Khong tim thay dong Wall trong danh sach nang cap.")
            self._close_wall_popup()
            return self._wall_result(False, "wall_not_found")

        self.log(f"[WALL] Chon dong Wall tai {wall_pos[0]},{wall_pos[1]}.")
        self._tap([int(wall_pos[0]), int(wall_pos[1])])
        self._sleep(0.8)

        self._tap(coords["upgrade_more_button"])
        self._sleep(1.0)

        upgrade_button = coords["upgrade_gold_button"] if pay_with == "gold" else coords["upgrade_elixir_button"]
        use_add10 = bool(settings.get("use_add10", False))
        add_button = coords["add10_button"] if use_add10 else coords["add1_button"]
        add_label = "+10" if use_add10 else "+1"
        max_rounds = max(
            1,
            int(settings.get("max_add_rounds" if use_add10 else "add1_rounds", 60 if use_add10 else 1)),
        )
        self.log(f"[WALL] Dung nut {add_label}, toi da {max_rounds} lan bam.")
        rounds = 0
        while rounds < max_rounds and not self.stop_event.is_set():
            self._tap(add_button)
            self._sleep(0.5)
            rounds += 1

        if self.stop_event.is_set():
            return self._wall_result(False, "stopped")

        # The price text on the wall toolbar is highly stylized and proved
        # unreliable in live OCR. Open the confirmation first, then validate
        # its wall label, currency and total before any irreversible tap.
        self._tap(upgrade_button)
        self._sleep(1.0)
        confirmation = self._read_wall_confirmation_stable(settings, pay_with)
        if confirmation is None:
            self.log("[WALL] Hop xac nhan khong dat dong thuan an toan, huy.")
            self._tap(coords["confirm_cancel_button"])
            self._sleep(0.4)
            return self._wall_result(False, "confirmation_read_failed")
        confirmation_cost = int(confirmation.get("cost", -1))
        if not confirmation.get("is_wall_upgrade") or confirmation.get("currency") != pay_with or confirmation_cost <= 0:
            self.log(
                f"[WALL] Hop xac nhan khong khop: "
                f"wall={bool(confirmation.get('is_wall_upgrade'))} | "
                f"currency={confirmation.get('currency') or '?'} | "
                f"cost={confirmation_cost:,}. Huy de tranh tieu nham."
            )
            self._tap(coords["confirm_cancel_button"])
            self._sleep(0.4)
            return self._wall_result(False, "confirmation_mismatch")
        if confirmation_cost > budget:
            self.log(
                f"[WALL] Gia xac nhan {confirmation_cost:,} vuot ngan sach "
                f"{budget:,} {pay_with}, huy."
            )
            self._tap(coords["confirm_cancel_button"])
            self._sleep(0.4)
            return self._wall_result(False, "cost_over_budget")
        if settings.get("dry_run", False):
            self.log(
                f"[WALL] Dry-run hop le: {confirmation_cost:,} {pay_with}; "
                "da huy truoc nut Okay."
            )
            self._tap(coords["confirm_cancel_button"])
            self._sleep(0.4)
            self.attacks_since_wall_upgrade = 0
            return self._wall_result(True)

        self.log(f"[WALL] Xac nhan nang tuong: {confirmation_cost:,} {pay_with}.")
        self._tap(coords["confirm_okay_button"])
        self._sleep(1.2)
        if self.stop_event.is_set():
            return self._wall_result(False, "stopped")
        resources_after = self._read_home_resources_stable(settings)
        if not resources_before or not resources_after:
            self.log("[WALL] Khong xac minh duoc tai nguyen sau khi nang.")
            return self._wall_result(False, "upgrade_verify_failed")
        before_value = int(resources_before.get(pay_with, -1))
        after_value = int(resources_after.get(pay_with, -1))
        if before_value < 0 or after_value < 0:
            self.log("[WALL] Du lieu xac minh tai nguyen khong hop le.")
            return self._wall_result(False, "upgrade_verify_failed")
        if after_value >= before_value:
            self.log(
                f"[WALL] Khong thay {pay_with} giam sau xac nhan "
                f"({before_value:,} -> {after_value:,})."
            )
            return self._wall_result(False, "upgrade_not_confirmed")
        spent = before_value - after_value
        spend_tolerance = max(
            max(0, int(settings.get("spend_verify_tolerance_absolute", 1_000))),
            int(
                confirmation_cost
                * max(0.0, float(settings.get("spend_verify_tolerance_percent", 0.1)))
                / 100.0
            ),
        )
        if spent > budget or abs(spent - confirmation_cost) > spend_tolerance:
            message = (
                f"Chi tieu nang tuong bat thuong: modal={confirmation_cost:,} | "
                f"thuc_te={spent:,} | ngan_sach={budget:,} {pay_with}. Bot da dung."
            )
            self.log(f"[WALL][CRITICAL] {message}")
            self._notify_lifecycle("error", message)
            self.stop_event.set()
            return self._wall_result(False, "unsafe_spend_detected")
        self.log(f"[WALL] Da xac minh {pay_with} giam {spent:,}.")
        self.attacks_since_wall_upgrade = 0
        return self._wall_result(True)

    def _read_wall_confirmation_stable(
        self,
        settings: dict[str, Any],
        expected_currency: str,
    ) -> dict[str, Any] | None:
        attempts = max(3, int(settings.get("confirmation_read_attempts", 3)))
        min_agree = max(2, int(settings.get("confirmation_min_agree", 2)))
        delay = max(0.0, float(settings.get("confirmation_read_delay", 0.35)))
        valid: list[tuple[bool, str, int]] = []
        details: list[str] = []
        for attempt in range(attempts):
            self._pause_gate()
            if self.stop_event.is_set():
                return None
            try:
                png = self._screencap_png()
            except ADBError as exc:
                details.append(f"adb={exc}")
            else:
                sample = self.vision.read_wall_confirmation(png, settings)
                wall_ok = bool(sample.get("is_wall_upgrade"))
                currency = str(sample.get("currency", ""))
                cost = int(sample.get("cost", -1))
                text_cost = int(sample.get("text_cost", -1))
                region_cost = int(sample.get("region_cost", -1))
                sources_match = bool(sample.get("sources_match", False))
                details.append(
                    f"wall={wall_ok},currency={currency or '?'},"
                    f"text={text_cost},region={region_cost}"
                )
                if wall_ok and currency == expected_currency and sources_match and cost > 0:
                    valid.append((wall_ok, currency, cost))
            if attempt < attempts - 1:
                self._sleep(delay)

        self.log(f"[WALL] Mau hop xac nhan: {' | '.join(details)}.")
        if not valid or min_agree > attempts:
            return None
        candidate, count = Counter(valid).most_common(1)[0]
        if count < min_agree:
            return None
        return {
            "is_wall_upgrade": candidate[0],
            "currency": candidate[1],
            "cost": candidate[2],
        }

    def _find_wall_row(self, settings: dict[str, Any]) -> list[int] | None:
        search_region = settings.get("search_region", [560, 100, 500, 600])
        scroll_swipe = settings.get("list_scroll_swipe", [820, 650, 820, 220, 500])
        max_scrolls = max(0, int(settings.get("max_wall_search_scrolls", 6)))
        for attempt in range(max_scrolls + 1):
            self._pause_gate()
            if self.stop_event.is_set():
                return None
            try:
                png = self._screencap_png()
            except ADBError as exc:
                self.log(f"[WALL] Khong chup duoc danh sach nang cap: {exc}")
                return None
            wall_pos = self.vision.find_wall_row(png, search_region)
            if wall_pos:
                row_tap_x = int(settings.get("wall_row_tap_x", search_region[0] + search_region[2] // 2))
                wall_pos = [row_tap_x, int(wall_pos[1])]
                if attempt > 0:
                    self.log(f"[WALL] Tim thay Wall sau {attempt} lan cuon.")
                return wall_pos
            if attempt < max_scrolls:
                self.log(f"[WALL] Chua thay Wall, cuon danh sach ({attempt + 1}/{max_scrolls}).")
                self._swipe(scroll_swipe)
                self._sleep(0.9)
        return None

    def _read_home_resources_stable(self, settings: dict[str, Any]) -> dict[str, int] | None:
        if not self.vision.available:
            return None
        attempts = max(1, int(settings.get("resource_read_attempts", 3)))
        delay = max(0.0, float(settings.get("read_attempt_delay", 0.45)))
        samples: list[dict[str, int]] = []
        for attempt in range(attempts):
            self._pause_gate()
            if self.stop_event.is_set():
                return None
            try:
                png = self._screencap_png()
            except ADBError as exc:
                self.log(f"[WALL] Khong doc duoc tai nguyen o lang: {exc}")
                return None
            value = self.vision.read_home_resources(png)
            samples.append(value)
            if attempt < attempts - 1:
                self._sleep(delay)
        tolerance_percent = max(0.0, float(settings.get("stable_read_tolerance_percent", 0.1)))
        tolerance_absolute = max(0, int(settings.get("stable_read_tolerance_absolute", 1_000)))
        gold = self._stable_number(
            [int(item.get("gold", -1)) for item in samples],
            tolerance_percent,
            tolerance_absolute,
        )
        elixir = self._stable_number(
            [int(item.get("elixir", -1)) for item in samples],
            tolerance_percent,
            tolerance_absolute,
        )
        details = " | ".join(f"{item.get('gold', -1):,}/{item.get('elixir', -1):,}" for item in samples)
        self.log(f"[WALL] Mau tai nguyen gold/elixir: {details}.")
        if gold < 0 or elixir < 0:
            return None
        gold_cap = max(1, int(settings.get("gold_capacity", 1)))
        elixir_cap = max(1, int(settings.get("elixir_capacity", 1)))
        if gold > int(gold_cap * 1.2) or elixir > int(elixir_cap * 1.2):
            self.log(
                f"[WALL] OCR tai nguyen vuot gioi han hop ly "
                f"({gold:,}/{gold_cap:,} | {elixir:,}/{elixir_cap:,}), bo qua."
            )
            return None
        return {"gold": gold, "elixir": elixir}

    def _read_wall_cost_stable(self, settings: dict[str, Any], button_center: list[int]) -> int:
        attempts = max(1, int(settings.get("cost_read_attempts", 3)))
        delay = max(0.0, float(settings.get("read_attempt_delay", 0.45)))
        values: list[int] = []
        for attempt in range(attempts):
            self._pause_gate()
            if self.stop_event.is_set():
                return -1
            try:
                png = self._screencap_png()
            except ADBError as exc:
                self.log(f"[WALL] Khong chup duoc gia nang tuong: {exc}")
                return -1
            values.append(int(self.vision.read_wall_upgrade_cost(png, button_center)))
            if attempt < attempts - 1:
                self._sleep(delay)
        self.log(f"[WALL] Mau gia nang: {', '.join(str(value) for value in values)}.")
        return self._stable_number(
            values,
            max(0.0, float(settings.get("stable_read_tolerance_percent", 0.1))),
            max(0, int(settings.get("stable_read_tolerance_absolute", 1_000))),
        )

    def _stable_number(
        self,
        values: list[int],
        tolerance_percent: float = 0.1,
        tolerance_absolute: int = 1_000,
    ) -> int:
        valid = sorted(value for value in values if value >= 0)
        if len(valid) < 2:
            return -1
        counts = {value: valid.count(value) for value in set(valid)}
        best_value, best_count = max(counts.items(), key=lambda item: item[1])
        if best_count >= 2:
            return best_value

        best_cluster: list[int] = []
        for start_index, start in enumerate(valid):
            cluster = [start]
            for candidate in valid[start_index + 1 :]:
                tolerance = max(
                    max(0, int(tolerance_absolute)),
                    int(max(candidate, 1) * max(0.0, float(tolerance_percent)) / 100.0),
                )
                if candidate - start <= tolerance:
                    cluster.append(candidate)
                else:
                    break
            if len(cluster) > len(best_cluster):
                best_cluster = cluster

        if len(best_cluster) < 2:
            return -1
        return best_cluster[len(best_cluster) // 2]

    def _rollback_wall_selection_to_budget(
        self,
        settings: dict[str, Any],
        coords: dict[str, Any],
        upgrade_button: list[int],
        budget: int,
        use_add10: bool,
    ) -> int:
        rollback_clicks = 10 if use_add10 else 1
        for _ in range(rollback_clicks):
            self._tap(coords["remove_button"])
            self._sleep(0.5)
            cost = self._read_wall_cost_stable(settings, upgrade_button)
            if 0 < cost <= budget:
                return cost
        return 0

    def _close_wall_popup(self) -> None:
        try:
            self._shell("input", "keyevent", "KEYCODE_BACK", timeout=5)
            self._sleep(0.3)
        except ADBError as exc:
            self.log(f"[WALL] Khong dong duoc popup nang tuong: {exc}")

    def _read_loot(self) -> dict[str, int]:
        return self._read_loot_frame()[1]

    def _read_loot_frame(self) -> tuple[bytes, dict[str, int]]:
        if not self.vision.available:
            raise RuntimeError("OCR is not ready, cannot read loot.")
        png = self._screencap_png()
        return png, self.vision.read_loot(png)

    def _loot_is_valid(self, loot: dict[str, int]) -> bool:
        if loot["gold"] < 0 or loot["elixir"] < 0:
            return False
        farm = self.config.get("farm", {})
        gold_max = int(farm.get("loot_gold_max", 0))
        elixir_max = int(farm.get("loot_elixir_max", 0))
        if gold_max > 0 and loot["gold"] > gold_max:
            self.log(f"[SEARCH] Gold OCR {loot['gold']:,} vượt cap {gold_max:,}, bỏ qua base.")
            return False
        if elixir_max > 0 and loot["elixir"] > elixir_max:
            self.log(f"[SEARCH] Elixir OCR {loot['elixir']:,} vượt cap {elixir_max:,}, bỏ qua base.")
            return False
        return True

    def _should_attack(self, loot: dict[str, int]) -> bool:
        if not self._loot_is_valid(loot):
            return False
        farm = self.config["farm"]
        mode = farm.get("threshold_mode", "any")
        if mode == "total":
            total_min = int(farm.get("total_min", 0))
            return total_min > 0 and self._loot_total(loot) >= total_min

        thresholds = (
            (int(farm.get("gold_min", 0)), loot["gold"]),
            (int(farm.get("elixir_min", 0)), loot["elixir"]),
            (int(farm.get("total_min", 0)), self._loot_total(loot)),
        )
        conditions = [value >= minimum for minimum, value in thresholds if minimum > 0]
        if not conditions:
            return False
        return all(conditions) if mode == "all" else any(conditions)

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
        zone = self._deploy_zone_for_view(view)
        if len(zone) >= 3:
            self.log(f"[ZONE] Deploy random in zone: {view} (global deploy).")
            return self._random_points_in_polygon(
                zone,
                int(deploy.get("zone_random_points", 48)),
            )
        self.log(f"[ZONE] Missing global deploy zone for {view or 'unknown view'}.")
        return []

    def _deploy_zone_for_view(self, view: str) -> list[list[int]]:
        return self._valid_polygon(self.config.get("deploy", {}).get("deploy_zones", {}).get(view, []))

    def _valid_polygon(self, points: Any) -> list[list[int]]:
        if not isinstance(points, list):
            return []
        normalized = [[int(point[0]), int(point[1])] for point in points if isinstance(point, list) and len(point) >= 2]
        return normalized if len(normalized) >= 3 else []

    def _random_points_in_polygon(
        self,
        polygon: list[list[int]],
        count: int,
        min_distance_px: int = 0,
    ) -> list[list[int]]:
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
        min_distance = max(0, int(min_distance_px))
        max_attempts = target_count * (180 if min_distance > 0 else 80)
        while len(points) < target_count and attempts < max_attempts:
            attempts += 1
            candidate = [random.randint(min_x, max_x), random.randint(min_y, max_y)]
            if self._point_in_polygon(candidate, normalized) and self._point_far_enough(candidate, points, min_distance):
                points.append(candidate)
        return points or normalized

    def _point_far_enough(self, point: list[int], points: list[list[int]], min_distance_px: int) -> bool:
        if min_distance_px <= 0:
            return True
        min_distance_sq = min_distance_px * min_distance_px
        x, y = point
        for other_x, other_y in points:
            dx = x - other_x
            dy = y - other_y
            if dx * dx + dy * dy < min_distance_sq:
                return False
        return True

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

    def _selected_attack_view(self) -> str:
        valid_views = tuple(
            view
            for view in ("trenbenphai", "trenbentrai", "duoibenphai", "duoibentrai")
            if len(self._deploy_zone_for_view(view)) >= 3
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

    def _stop_requested(self) -> bool:
        stop_event = getattr(self, "stop_event", None)
        return bool(stop_event and stop_event.is_set())

    def _active_time(self) -> float:
        return time.time() - float(getattr(self, "_paused_seconds_total", 0.0))

    def _tap(self, point: list[int] | tuple[int, int], jitter: int = 4) -> None:
        self._pause_gate()
        if self._stop_requested():
            return
        self.adb.tap(int(point[0]), int(point[1]), jitter=jitter)

    def _swipe(self, values: list[int] | tuple[int, int, int, int, int]) -> None:
        self._pause_gate()
        if self._stop_requested():
            return
        self.adb.swipe(*[int(value) for value in values])

    def _shell(self, *args: str, timeout: float = 5) -> Any:
        self._pause_gate()
        if self._stop_requested():
            return None
        return self.adb.shell(*args, timeout=timeout)

    def _screencap_png(self) -> bytes:
        self._pause_gate()
        if self._stop_requested():
            return b""
        return self.adb.screencap_png()

    def _force_stop_app(self, package: str) -> None:
        self._pause_gate()
        if self._stop_requested():
            return
        self.adb.force_stop_app(package)

    def _start_app(self, package: str) -> None:
        self._pause_gate()
        if self._stop_requested():
            return
        self.adb.start_app(package)

    def _tap_coord(self, name: str) -> None:
        x, y = self.config["coords"][name]
        self._tap([int(x), int(y)])
        self._optimized_action_pause()
        self._sleep(self._after_click_seconds())

    def _tap_slot(self, name: str) -> bool:
        runtime_slot = self._runtime_slot(name)
        if runtime_slot:
            x, y = runtime_slot["center"]
        else:
            coords = self.config.get("coords", {}).get("slots", {}).get(name)
            if not coords:
                self.log(f"[WARN] Khong co toa do fallback cho slot '{name}'.")
                return False
            x, y = coords
        self._tap([int(x), int(y)])
        self._optimized_action_pause()
        self._sleep(0.18)
        return True

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
            png = self._screencap_png()
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
        end = self._active_time() + self._jittered_sleep_seconds(seconds)
        while self._active_time() < end:
            self._pause_gate()
            if self._stop_requested():
                return
            time.sleep(max(0.0, min(0.1, end - self._active_time())))

    def _jittered_sleep_seconds(self, seconds: float) -> float:
        base = max(0.0, float(seconds))
        timing = self.config.get("timing", {})
        min_seconds = float(timing.get("sleep_jitter_min_seconds", 0.25))
        jitter_percent = max(0.0, float(timing.get("sleep_jitter_percent", 0.15)))
        if base < min_seconds or jitter_percent <= 0:
            return base
        delta = base * jitter_percent
        return max(0.0, random.uniform(base - delta, base + delta))

    def _pause_gate(self) -> float:
        pause_event = getattr(self, "pause_event", None)
        stop_event = getattr(self, "stop_event", None)
        if pause_event is None or stop_event is None:
            return 0.0
        pause_started_at = 0.0
        while pause_event.is_set() and not stop_event.is_set():
            if pause_started_at <= 0:
                pause_started_at = time.time()
            time.sleep(0.2)
        if pause_started_at <= 0:
            return 0.0
        paused_seconds = time.time() - pause_started_at
        self._paused_seconds_total = float(getattr(self, "_paused_seconds_total", 0.0)) + paused_seconds
        if getattr(self, "auto_stop_at", 0.0) > 0:
            self.auto_stop_at += paused_seconds
        if getattr(self, "next_periodic_restart_at", 0.0) > 0:
            self.next_periodic_restart_at += paused_seconds
        self.log(f"[SCHEDULE] Pause {int(paused_seconds)}s, lịch chạy được dời lại.")
        return paused_seconds

    def _load_total_stats(self) -> dict[str, int]:
        return load_total_stats(self.stats_path)

    def _publish_stats(self) -> None:
        payload = self._stats_payload()
        self.stats_callback(self._save_stats(payload))

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

    def _save_stats(self, payload: dict[str, Any]) -> dict[str, Any]:
        merged = merge_existing_stats(self.stats_path, payload)
        try:
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            with self.stats_path.open("w", encoding="utf-8") as file:
                json.dump(merged, file, ensure_ascii=True, indent=2)
        except OSError as exc:
            self.log(f"[WARN] Không ghi được stats.json: {exc}")
            return payload
        return merged

    def _dump_debug_png(self, reason: str, png: bytes = b"") -> None:
        if not png:
            try:
                png = self._screencap_png()
            except ADBError as exc:
                self.log(f"[WARN] Khong chup duoc debug screencap: {exc}")
                return
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
