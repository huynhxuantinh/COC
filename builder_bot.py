from __future__ import annotations

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
from polygon_utils import normalize_polygon
from stats_store import STAT_KEYS, atomic_write_json, load_total_stats, merge_existing_stats


class BuilderBaseBot:
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
        resolution = tuple(config.get("game", {}).get("resolution", [1600, 900]))
        self.adb = ADBClient(config["adb"]["path"], config["adb"]["device"], log=log, resolution=resolution)
        self.vision = BuilderBaseVision(config, log=log)
        self.builder = config.get("builder_base", {})
        self.stats = {key: 0 for key in self.STAT_KEYS}
        self.stats_callback = stats_callback or (lambda stats: None)
        self.lifecycle_callback = lifecycle_callback or (lambda event, detail="": None)
        self.stats_path = Path(config.get("runtime", {}).get("stats_path", "stats.json"))
        self.base_total_stats = self._load_total_stats()
        self.session_started_at = datetime.now().isoformat(timespec="seconds")
        self.debug_dir = Path("debug")
        self.safe_device = self._safe_name(config["adb"]["device"])
        self._state_failures = 0
        self._watchdog_restarts = 0
        self._hero_deployed_at = 0.0
        self._hero_last_skill_at = 0.0
        self._hero_last_ready_check_at = 0.0
        self._expected_stage = 1
        self.attacks_since_wall_upgrade = 0
        self._elixir_cart_pending = False
        self.run_started_at = 0.0
        self.auto_stop_at = 0.0
        self.next_periodic_restart_at = 0.0
        self._paused_seconds_total = 0.0

    def run(self) -> None:
        try:
            if self.config.get("adb", {}).get("connect_on_start", True):
                self.adb.connect()
            if not self.vision.available:
                self.log("[ERROR] OCR chưa sẵn sàng cho chế độ Làng đêm.")
                self._notify_lifecycle("error", "OCR chưa sẵn sàng cho chế độ Làng đêm.")
                self.stop_event.set()
                return

            self._publish_stats()
            self.log("[BUILDER] Bắt đầu chế độ Làng đêm.")
            self._notify_lifecycle("running")
            self.run_started_at = time.time()
            auto_stop_after = self._auto_stop_after_seconds()
            self.auto_stop_at = self.run_started_at + auto_stop_after if auto_stop_after > 0 else 0.0
            self.next_periodic_restart_at = self._next_periodic_restart_at(self.run_started_at)
            errors = 0
            max_errors = max(1, int(self.config.get("game", {}).get("max_consecutive_cycle_errors", 8)))
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
                    errors = 0
                except ADBError as exc:
                    errors += 1
                    self.log(f"[BUILDER][WARN] Lỗi ADB ({errors}/{max_errors}): {exc}")
                    try:
                        self.adb.connect()
                    except ADBError as reconnect_error:
                        self.log(f"[BUILDER][WARN] Kết nối lại thất bại: {reconnect_error}")
                except Exception as exc:
                    errors += 1
                    self.log(f"[BUILDER][WARN] Lỗi cycle ({errors}/{max_errors}): {exc}")
                if errors >= max_errors:
                    self.log("[BUILDER][ERROR] Quá nhiều lỗi liên tiếp. Dừng bot.")
                    self._notify_lifecycle("error", "Quá nhiều lỗi cycle liên tiếp.")
                    self.stop_event.set()
                    break
                self._sleep(1.0 if errors else 0.2)
        except ADBError as exc:
            self.log(f"[BUILDER][ERROR] Lỗi ADB: {exc}")
            self._notify_lifecycle("error", str(exc))
            self.stop_event.set()
        except Exception as exc:
            self.log(f"[BUILDER][ERROR] Bot dừng do lỗi: {exc}")
            self._notify_lifecycle("error", str(exc))
            self.stop_event.set()
        finally:
            self._publish_stats()
            self.log("[BUILDER] Đã dừng chế độ Làng đêm.")
            self._notify_lifecycle("stopped")

    def _notify_lifecycle(self, event: str, detail: str = "") -> None:
        try:
            self.lifecycle_callback(event, detail)
        except Exception:
            pass

    def _run_cycle(self) -> None:
        if not self._ensure_builder_home():
            return

        if self._elixir_cart_due():
            self._collect_elixir_cart()
        if self.stop_event.is_set():
            return

        if self._builder_wall_upgrade_due():
            result = self._upgrade_builder_walls()
            if not result["success"]:
                if not self.stop_event.is_set():
                    self._backoff_builder_wall_upgrade(result["reason"])
                return
            if not result.get("continue_cycle", False):
                return

        coords = self.builder.get("coords", {})
        self.log("[BUILDER] Mở tìm trận.")
        self._tap(coords.get("attack", [105, 795]))
        self._sleep(float(self.builder.get("timing", {}).get("after_attack_seconds", 1.5)))

        state, dialog_png = self._wait_for_states({BuilderScreen.START_DIALOG}, timeout=12)
        if state != BuilderScreen.START_DIALOG:
            self.log("[BUILDER][WARN] Không thấy cửa sổ Start Attack.")
            self._record_state_failure("builder-start-dialog-missing", dialog_png)
            return
        if not self.vision.find_now_available(dialog_png):
            self._close_start_dialog(cooldown=True)
            return

        self._tap(coords.get("find_now", [1190, 592]))
        self.log("[BUILDER] Find Now.")
        self._sleep(float(self.builder.get("timing", {}).get("after_find_now_seconds", 6.0)))

        state, png = self._wait_for_states(
            {BuilderScreen.STAGE_PREP, BuilderScreen.BATTLE, BuilderScreen.RESULT},
            timeout=float(self.builder.get("timing", {}).get("prep_timeout_seconds", 70)),
        )
        if state not in {BuilderScreen.STAGE_PREP, BuilderScreen.BATTLE, BuilderScreen.RESULT}:
            self.log("[BUILDER][WARN] Không vào được Làng 1.")
            self._record_state_failure("builder-stage1-not-found", png)
            return

        self.stats["builder_attacks"] += 1
        self.attacks_since_wall_upgrade += 1
        self._expected_stage = 1
        self._publish_stats()
        if state == BuilderScreen.RESULT:
            self._handle_result(png)
            return

        self._clear_state_failures()
        self._run_match_from_stage(stage=1, state=state, png=png, deploy_current=True)

    def _run_match_from_stage(
        self,
        stage: int,
        state: str,
        png: bytes,
        deploy_current: bool,
    ) -> bool:
        current_stage = 2 if int(stage) == 2 else 1
        current_state = state
        current_png = png
        should_deploy = deploy_current

        while not self.stop_event.is_set():
            self._expected_stage = current_stage
            if current_state == BuilderScreen.RESULT:
                self._handle_result(current_png)
                self._clear_state_failures()
                return True

            if current_state not in {BuilderScreen.STAGE_PREP, BuilderScreen.BATTLE}:
                self._record_state_failure(f"builder-stage{current_stage}-invalid-state", current_png)
                return False

            if should_deploy:
                current_png = self._prepare_stage_camera(stage=current_stage)
                if not self._deploy_stage(stage=current_stage, png=current_png):
                    self._record_state_failure(
                        f"builder-stage{current_stage}-deploy-failed",
                        current_png,
                        restart=False,
                    )
                    return False

            current_state, current_png = self._monitor_stage(
                stage=current_stage,
                initial_state=current_state,
            )
            if current_state in {BuilderScreen.INTERRUPTED, BuilderScreen.RESTARTED}:
                return False
            if current_state == BuilderScreen.RESULT:
                self._handle_result(current_png)
                self._clear_state_failures()
                return True

            if current_stage == 1 and current_state == BuilderScreen.STAGE_PREP:
                self.log("[BUILDER] Đã xác nhận Làng 2. Quét quân sống trước, sau đó quân tiếp viện.")
                current_stage = 2
                self._expected_stage = 2
                should_deploy = True
                continue

            self._record_state_failure(
                f"builder-stage{current_stage}-transition-failed",
                current_png,
            )
            return False

        return False

    def _ensure_builder_home(self) -> bool:
        png = self._screencap_png()
        state = self.vision.classify(png)
        if state == BuilderScreen.BUILDER_HOME:
            self._expected_stage = 1
            return True
        if state == BuilderScreen.ELIXIR_CART:
            self._collect_elixir_cart(png)
            return False
        if state == BuilderScreen.STAR_BONUS:
            self._dismiss_star_bonus(png)
            return False
        if state == BuilderScreen.START_DIALOG:
            self._expected_stage = 1
            self._close_start_dialog(cooldown=not self.vision.find_now_available(png))
            return False
        if state == BuilderScreen.MAIN_HOME:
            self._expected_stage = 1
            return self._travel_to_builder_base()
        if state == BuilderScreen.RESULT:
            self._handle_result(png)
            self._clear_state_failures()
            return False
        if state in {BuilderScreen.STAGE_PREP, BuilderScreen.BATTLE}:
            expected_stage = 2 if int(getattr(self, "_expected_stage", 1)) == 2 else 1
            stage = expected_stage
            if state == BuilderScreen.STAGE_PREP and expected_stage != 2:
                stage = 2 if self._stage_two_ready(png) else 1
            deploy_current = state == BuilderScreen.STAGE_PREP
            if state == BuilderScreen.BATTLE and expected_stage != 2:
                stage = 2 if self._stage_two_visible(png) else 1
            self.log(
                f"[BUILDER][WARN] Phát hiện trận cũ ở Làng {stage}. "
                "Tiếp tục xử lý thay vì mở trận mới."
            )
            self._run_match_from_stage(stage, state, png, deploy_current=deploy_current)
            return False

        self.log("[BUILDER][WARN] Không nhận diện được màn hình hiện tại. Khởi động lại game.")
        self._record_state_failure("builder-home-unknown", png)
        return False

    def _travel_to_builder_base(self) -> bool:
        entry = self.builder.get("entry", {})
        self.log("[BUILDER] Đang ở Làng chính. Zoom nhỏ để tìm thuyền.")
        self._zoom_out(int(entry.get("zoom_out_count", 4)))
        for swipe in entry.get("camera_swipes", [[650, 650, 950, 350, 500]]):
            self._swipe(swipe)
            self._sleep(0.8)

        attempts = max(1, int(entry.get("boat_search_attempts", 3)))
        last_png = b""
        for attempt in range(1, attempts + 1):
            self._pause_gate()
            last_png = self._screencap_png()
            if self.vision.is_builder_home(last_png):
                return True
            boat = self.vision.find_boat(last_png)
            if boat is None:
                self.log(f"[BUILDER] Chưa thấy thuyền ({attempt}/{attempts}), zoom/kéo lại.")
                self._zoom_out(1)
                for swipe in entry.get("camera_swipes", []):
                    self._swipe(swipe)
                self._sleep(1.0)
                continue

            x, y, score = boat
            self.log(f"[BUILDER] Thấy thuyền tại {x},{y} (score={score:.2f}).")
            self._tap([x, y], jitter=0)
            self._sleep(2.0)

            focused_png = self._screencap_png()
            if self.vision.is_builder_home(focused_png):
                self.log("[BUILDER] Đã sang Làng đêm.")
                return True
            focused_boat = self.vision.find_boat(focused_png)
            if focused_boat is not None:
                focused_x, focused_y, focused_score = focused_boat
                self.log(f"[BUILDER] Xác nhận đi thuyền tại {focused_x},{focused_y} (score={focused_score:.2f}).")
                self._tap([focused_x, focused_y], jitter=0)
                self._sleep(float(entry.get("travel_wait_seconds", 8.0)))
                arrived_png = self._screencap_png()
                if self.vision.is_builder_home(arrived_png):
                    self.log("[BUILDER] Đã sang Làng đêm.")
                    return True
                last_png = arrived_png

        self.log("[BUILDER][WARN] Đã bấm thuyền nhưng chưa vào được Làng đêm.")
        self._record_state_failure("builder-boat-travel-failed", last_png)
        return False

    def _collect_elixir_cart(self, png: bytes = b"") -> bool:
        cart = self.builder.get("elixir_cart", {})
        current = png or self._screencap_png()
        if not cart.get("enabled", True):
            if self.vision.is_elixir_cart_popup(current):
                self.log("[BUILDER] Tự nhận dầu đang tắt; đóng popup Elixir Cart.")
                self._tap(cart.get("close_button", [1342, 88]), jitter=0)
                self._sleep(float(cart.get("open_wait_seconds", 1.0)))
            return False

        if self.vision.is_elixir_cart_popup(current):
            self.log("[BUILDER] Elixir Cart đang mở; đóng để đọc dầu trước khi nhận.")
            self._tap(cart.get("close_button", [1342, 88]), jitter=0)
            self._sleep(float(cart.get("open_wait_seconds", 1.0)))
            current = self._screencap_png()
            if self.vision.is_elixir_cart_popup(current):
                self.log("[BUILDER][WARN] Không đóng được Elixir Cart; chưa nhận dầu.")
                return False

        home_resources = self.vision.read_home_resources(current)
        home_elixir_before = int(home_resources.get("elixir", -1))
        if home_elixir_before < 0:
            self.log("[BUILDER][WARN] Không đọc được dầu trước khi mở Elixir Cart; chưa bấm Collect.")
            return False

        icon = None
        attempts = max(1, int(cart.get("icon_search_attempts", 3)))
        for attempt in range(1, attempts + 1):
            icon = self.vision.find_elixir_cart(current)
            if icon is not None:
                break
            if attempt < attempts:
                self.log(f"[BUILDER] Chưa thấy Elixir Cart ({attempt}/{attempts}), zoom tìm lại.")
                self._zoom_out(1)
                self._sleep(0.8)
                current = self._screencap_png()
        if icon is None:
            self.log("[BUILDER][WARN] Đã đến hạn nhận dầu nhưng chưa tìm thấy Elixir Cart; sẽ thử lại sau trận kế tiếp.")
            self._dump_debug("builder-elixir-cart-not-found", current)
            return False
        self.log(f"[BUILDER] Mở Elixir Cart tại {icon[0]},{icon[1]}.")
        self._tap([icon[0], icon[1]], jitter=0)
        self._sleep(float(cart.get("open_wait_seconds", 1.0)))
        current = self._screencap_png()
        if not self.vision.is_elixir_cart_popup(current):
            self.log("[BUILDER][WARN] Không mở được Elixir Cart.")
            return False

        reward = self.vision.read_elixir_cart_reward(current)
        if reward < 0:
            self.log("[BUILDER][WARN] Không đọc được lượng dầu trong Elixir Cart; sẽ thử lại sau trận kế tiếp.")
            self._tap(cart.get("close_button", [1342, 88]), jitter=0)
            return False
        if reward == 0:
            self._tap(cart.get("close_button", [1342, 88]), jitter=0)
            self._elixir_cart_pending = False
            self.log("[BUILDER] Elixir Cart hiện không có dầu để nhận.")
            return True

        self.log(f"[BUILDER] Elixir Cart có {reward:,} dầu. Bấm Collect.")
        self._tap(cart.get("collect_button", [1175, 760]), jitter=0)
        self._sleep(float(cart.get("collect_wait_seconds", 1.0)))
        after_png = self._screencap_png()
        popup_still_open = self.vision.is_elixir_cart_popup(after_png)
        collected = 0
        if popup_still_open:
            remaining = self.vision.read_elixir_cart_reward(after_png)
            if remaining >= 0:
                collected = max(0, reward - remaining)
            else:
                self.log(
                    "[BUILDER][WARN] Popup Elixir Cart con mo nhung OCR khong doc duoc "
                    "so dau con lai; chua xac nhan Collect."
                )
        else:
            home_resources_after = self.vision.read_home_resources(after_png)
            home_elixir_after = int(home_resources_after.get("elixir", -1))
            if home_elixir_after > home_elixir_before:
                collected = min(reward, home_elixir_after - home_elixir_before)
            else:
                self.log(
                    "[BUILDER][WARN] Popup Elixir Cart da dong nhung tai nguyen lang "
                    "khong tang; chua xac nhan Collect."
                )
        if collected > 0:
            self.stats["builder_elixir"] += collected
            self._elixir_cart_pending = False
            self._publish_stats()
            self.log(f"[BUILDER] Đã nhận {collected:,} dầu Làng đêm.")
        else:
            self.log("[BUILDER][WARN] Collect chưa thành công; không cộng thống kê.")
        if popup_still_open:
            self._tap(cart.get("close_button", [1342, 88]), jitter=0)
        return collected > 0

    def _elixir_cart_due(self) -> bool:
        cart = self.builder.get("elixir_cart", {})
        if not cart.get("enabled", True):
            return False
        every = max(1, int(cart.get("collect_every_n_attacks", 1)))
        total_attacks = int(self.base_total_stats.get("builder_attacks", 0)) + int(
            self.stats.get("builder_attacks", 0)
        )
        if every == 1 or (total_attacks > 0 and total_attacks % every == 0):
            self._elixir_cart_pending = True
        return bool(getattr(self, "_elixir_cart_pending", False))

    def _dismiss_star_bonus(self, png: bytes = b"") -> bool:
        current = png or self._screencap_png()
        if not self.vision.is_star_bonus_popup(current):
            return True
        coords = self.builder.get("coords", {})
        wait_seconds = float(self.builder.get("timing", {}).get("star_bonus_wait_seconds", 1.5))
        for attempt in range(1, 3):
            self.log(f"[BUILDER] Nhận Star Bonus, bấm Okay ({attempt}/2).")
            self._tap(coords.get("star_bonus_okay", [800, 700]), jitter=0)
            self._sleep(wait_seconds)
            current = self._screencap_png()
            if not self.vision.is_star_bonus_popup(current):
                return True
        self.log("[BUILDER][WARN] Popup Star Bonus chưa đóng.")
        self._dump_debug("builder-star-bonus-not-closed", current)
        return False

    def _close_start_dialog(self, cooldown: bool) -> None:
        coords = self.builder.get("coords", {})
        if cooldown:
            self.log("[BUILDER] Trận trước bị gián đoạn; Find Now đang cooldown. Đóng cửa sổ và chờ.")
        else:
            self.log("[BUILDER] Đóng cửa sổ Start Attack còn sót lại.")
        self._tap(coords.get("start_dialog_close", [1360, 165]), jitter=0)
        self._sleep(1.0)
        if cooldown:
            retry = float(self.builder.get("timing", {}).get("attack_cooldown_retry_seconds", 15.0))
            self._sleep(max(1.0, retry))

    def _prepare_stage_camera(self, stage: int) -> bytes:
        deploy = self.builder.get("deploy", {})
        zoom_count = max(0, int(deploy.get(f"stage{stage}_zoom_out_count", 3)))
        if zoom_count:
            self.log(f"[BUILDER] Làng {stage}: zoom nhỏ x{zoom_count} trước khi thả quân.")
            self._zoom_out(zoom_count)
            self._sleep(max(0.0, float(deploy.get("camera_settle_seconds", 0.8))))
        return self._screencap_png()

    def _deploy_stage(self, stage: int, png: bytes) -> bool:
        deploy = self.builder.get("deploy", {})
        zone_name = "stage1_zone" if stage == 1 else "stage2_zone"
        zone = self._valid_polygon(deploy.get(zone_name, []))
        if not zone:
            self.log(f"[BUILDER][ERROR] Chưa thiết lập polygon Làng {stage}.")
            self._notify_lifecycle("error", f"Chưa thiết lập polygon Làng {stage}.")
            self.stop_event.set()
            return False

        coords = self.builder.get("coords", {})
        hero = coords.get("hero_slot", [162, 812])
        regular = coords.get("troop_slots", [])
        reinforcements = coords.get("reinforcement_slots", []) if stage == 2 else []
        hero_available, surviving_slots, reinforcement_slots = self._scan_stage_army(
            stage,
            png,
            hero,
            regular,
            reinforcements,
        )
        ordered_slots = surviving_slots + reinforcement_slots

        if not hero_available and not ordered_slots:
            self.log(f"[BUILDER][WARN] Làng {stage}: không còn slot quân có thể thả.")
            return False

        hero_attempts = max(1, int(deploy.get("hero_deploy_attempts", 2))) if hero_available else 0
        points = self._clustered_points(zone, hero_attempts + len(ordered_slots))
        point_index = 0
        hero_deployed_at = 0.0
        troop_skill_jobs: list[tuple[float, list[int]]] = []

        if hero_available:
            verify_delay = max(0.2, float(deploy.get("hero_deploy_verify_seconds", 0.8)))
            for attempt in range(1, hero_attempts + 1):
                self._deploy_slot(hero, points[point_index])
                point_index += 1
                self._sleep(verify_delay)
                verify_png = self._screencap_png()
                if self.vision.hero_deployed(verify_png, hero):
                    hero_deployed_at = self._active_time()
                    self.log(f"[BUILDER] Làng {stage}: đã xác nhận thả tướng.")
                    break
                self.log(f"[BUILDER][WARN] Làng {stage}: thả tướng chưa thành công ({attempt}/{hero_attempts}).")

        delay = max(0.0, float(deploy.get("troop_delay_seconds", 0.5)))
        skill_delay = max(0.0, float(deploy.get("troop_skill_delay_seconds", 3.0)))
        for slot in ordered_slots:
            if self.stop_event.is_set():
                return False
            self._deploy_slot(slot, points[point_index])
            deployed_at = self._active_time()
            troop_skill_jobs.append((deployed_at + skill_delay, slot))
            point_index += 1
            self._sleep(delay)

        self.log(
            f"[BUILDER] Làng {stage}: đã thả {len(surviving_slots)} slot chính"
            f" và {len(reinforcement_slots)} slot tiếp viện."
        )
        self._run_troop_skill_jobs(troop_skill_jobs)
        self._hero_deployed_at = hero_deployed_at
        self._hero_last_skill_at = 0.0
        self._hero_last_ready_check_at = 0.0
        return True

    def _scan_stage_army(
        self,
        stage: int,
        first_png: bytes,
        hero: list[int],
        regular: list[list[int]],
        reinforcements: list[list[int]],
    ) -> tuple[bool, list[list[int]], list[list[int]]]:
        deploy = self.builder.get("deploy", {})
        attempts = max(1, int(deploy.get("slot_scan_attempts", 3)))
        delay = max(0.0, float(deploy.get("slot_scan_delay_seconds", 0.35)))
        labels: list[tuple[str, list[int]]] = [("hero", hero)]
        labels.extend((f"regular:{index}", slot) for index, slot in enumerate(regular, start=1))
        labels.extend((f"reinforcement:{index}", slot) for index, slot in enumerate(reinforcements, start=1))
        votes = {label: 0 for label, _slot in labels}

        for attempt in range(attempts):
            if self.stop_event.is_set():
                break
            if attempt == 0 and first_png:
                png = first_png
            else:
                self._sleep(delay)
                png = self._screencap_png()
            for label, slot in labels:
                if self.vision.slot_available(png, slot):
                    votes[label] += 1

        required = attempts // 2 + 1
        hero_available = votes.get("hero", 0) >= required
        surviving = [
            slot
            for index, slot in enumerate(regular, start=1)
            if votes.get(f"regular:{index}", 0) >= required
        ]
        reinforcement = [
            slot
            for index, slot in enumerate(reinforcements, start=1)
            if votes.get(f"reinforcement:{index}", 0) >= required
        ]
        survivor_indexes = [str(index) for index, slot in enumerate(regular, start=1) if slot in surviving]
        reinforcement_indexes = [
            str(index) for index, slot in enumerate(reinforcements, start=1) if slot in reinforcement
        ]
        self.log(
            f"[BUILDER] Làng {stage}: tướng={'có' if hero_available else 'không'} | "
            f"quân sống={','.join(survivor_indexes) or 'không'} | "
            f"tiếp viện={','.join(reinforcement_indexes) or 'không'}."
        )
        return hero_available, surviving, reinforcement

    def _stage_two_ready(self, png: bytes) -> bool:
        reinforcements = self.builder.get("coords", {}).get("reinforcement_slots", [])
        return bool(reinforcements) and any(self.vision.slot_available(png, slot) for slot in reinforcements)

    def _stage_two_visible(self, png: bytes) -> bool:
        return self._stage_two_ready(png)

    def _deploy_slot(self, slot: list[int], point: list[int]) -> None:
        self._tap(slot, jitter=0)
        self._sleep(0.12)
        self._tap(point, jitter=3)

    def _run_troop_skill_jobs(self, jobs: list[tuple[float, list[int]]]) -> None:
        pending = list(jobs)
        while pending and not self.stop_event.is_set():
            self._pause_gate()
            if self.stop_event.is_set():
                return
            now = self._active_time()
            due = [job for job in pending if job[0] <= now]
            for job in due:
                self._tap(job[1], jitter=0)
                pending.remove(job)
                self._sleep(0.12)
            if pending:
                self._sleep(min(0.15, max(0.01, min(job[0] for job in pending) - self._active_time())))

    def _monitor_stage(self, stage: int, initial_state: str = BuilderScreen.STAGE_PREP) -> tuple[str, bytes]:
        timing = self.builder.get("timing", {})
        timeout = float(timing.get("battle_timeout_seconds", 150))
        transition_timeout = max(0.0, float(timing.get("stage_transition_timeout_seconds", 25)))
        confirmations = max(1, int(timing.get("state_confirmations", 2)))
        damage_unknown_timeout = max(0.0, float(timing.get("damage_unknown_restart_seconds", 20)))
        damage_stall_timeout = max(0.0, float(timing.get("damage_stall_seconds", 20)))
        unknown_state_timeout = max(0.0, float(timing.get("unknown_state_restart_seconds", 12)))
        frame_difference_threshold = max(0.0, float(timing.get("frozen_frame_min_difference", 1.5)))
        started = self._active_time()
        # Làng 2 hiển thị tổng phá hủy của cả hai làng, nên luôn bắt đầu từ 100%.
        last_damage = 100 if stage == 2 else -1
        last_log_at = 0.0
        last_damage_changed_at = started
        last_visual_change_at = started
        damage_unknown_started_at: float | None = None
        unknown_state_started_at: float | None = None
        previous_battle_png = b""
        last_png = b""
        battle_seen = initial_state == BuilderScreen.BATTLE
        candidate_state = BuilderScreen.UNKNOWN
        candidate_reads = 0
        home_state_started_at: float | None = None
        home_state_reads = 0
        stage_transition_started_at: float | None = None
        stage_completion_reads = 0
        while not self.stop_event.is_set() and self._active_time() - started < timeout:
            self._pause_gate()
            if self.stop_event.is_set():
                break
            last_png = self._screencap_png()
            state = self.vision.classify(last_png)
            now = self._active_time()

            if state == BuilderScreen.START_DIALOG:
                self.log(f"[BUILDER][WARN] Làng {stage} bị gián đoạn và đã quay về Start Attack.")
                self._close_start_dialog(cooldown=not self.vision.find_now_available(last_png))
                self._record_state_failure(f"builder-stage{stage}-interrupted", last_png, restart=False)
                return BuilderScreen.INTERRUPTED, last_png
            if state in {BuilderScreen.BUILDER_HOME, BuilderScreen.MAIN_HOME}:
                if home_state_started_at is None:
                    home_state_started_at = now
                    home_state_reads = 1
                else:
                    home_state_reads += 1
                grace = (
                    max(0.0, float(timing.get("result_transition_grace_seconds", 8)))
                    if stage == 2 and last_damage >= 100
                    else 0.0
                )
                if now - home_state_started_at < grace or home_state_reads < confirmations:
                    self._sleep(float(timing.get("screen_poll_seconds", 1.0)))
                    continue
                self.log(f"[BUILDER][WARN] Làng {stage} bị gián đoạn và đã quay về màn hình làng.")
                self._record_state_failure(f"builder-stage{stage}-returned-home", last_png, restart=False)
                return BuilderScreen.INTERRUPTED, last_png
            home_state_started_at = None
            home_state_reads = 0

            if state == BuilderScreen.UNKNOWN:
                if unknown_state_started_at is None:
                    unknown_state_started_at = now
                unknown_seconds = now - unknown_state_started_at
                if unknown_state_timeout > 0 and unknown_seconds >= unknown_state_timeout:
                    self._restart_stage_watchdog(
                        f"builder-stage{stage}-unknown-screen",
                        last_png,
                        f"Làng {stage}: màn hình không nhận diện được quá {int(unknown_seconds)}s.",
                    )
                    return BuilderScreen.RESTARTED, last_png
            else:
                unknown_state_started_at = None

            if state == BuilderScreen.BATTLE:
                battle_seen = True
                if previous_battle_png:
                    difference = self.vision.battle_frame_difference(previous_battle_png, last_png)
                    if difference >= frame_difference_threshold:
                        last_visual_change_at = now
                previous_battle_png = last_png

            terminal_state = BuilderScreen.UNKNOWN
            if state == BuilderScreen.RESULT:
                terminal_state = BuilderScreen.RESULT
            elif stage == 1 and battle_seen and state == BuilderScreen.STAGE_PREP:
                terminal_state = BuilderScreen.STAGE_PREP

            if terminal_state != BuilderScreen.UNKNOWN:
                if terminal_state == candidate_state:
                    candidate_reads += 1
                else:
                    candidate_state = terminal_state
                    candidate_reads = 1
                if candidate_reads >= confirmations:
                    return terminal_state, last_png
            else:
                candidate_state = BuilderScreen.UNKNOWN
                candidate_reads = 0

            if state == BuilderScreen.BATTLE:
                self._maybe_activate_hero(last_png)
                if now - last_log_at >= 5:
                    damage = self.vision.read_damage(last_png, stage=stage)
                    if stage == 2:
                        if damage >= 0 and not 100 <= damage <= 200:
                            damage = last_damage
                    elif stage == 1 and not 0 <= damage <= 100:
                        damage = -1
                    if damage < 0:
                        if damage_unknown_started_at is None:
                            damage_unknown_started_at = now
                        unknown_seconds = now - damage_unknown_started_at
                        if damage_unknown_timeout > 0 and unknown_seconds >= damage_unknown_timeout:
                            self._restart_stage_watchdog(
                                f"builder-stage{stage}-damage-unknown",
                                last_png,
                                f"Làng {stage}: damage '?' liên tục quá {int(unknown_seconds)}s.",
                            )
                            return BuilderScreen.RESTARTED, last_png
                    else:
                        damage_unknown_started_at = None
                    if damage > last_damage:
                        last_damage = damage
                        last_damage_changed_at = now
                    if stage == 1:
                        if damage == 100:
                            stage_completion_reads += 1
                        else:
                            stage_completion_reads = 0
                        if stage_completion_reads >= 2 and stage_transition_started_at is None:
                            stage_transition_started_at = now
                    label = f"{last_damage}%" if last_damage >= 0 else "?"
                    self.log(f"[BUILDER] Làng {stage}: damage={label}.")
                    last_log_at = now

                    damage_stalled = now - last_damage_changed_at >= damage_stall_timeout
                    frame_frozen = now - last_visual_change_at >= damage_stall_timeout
                    if (
                        damage_stall_timeout > 0
                        and last_damage >= 0
                        and damage_stalled
                        and frame_frozen
                    ):
                        self._restart_stage_watchdog(
                            f"builder-stage{stage}-battle-frozen",
                            last_png,
                            f"Làng {stage}: damage đứng ở {last_damage}% và khung hình đứng "
                            f"quá {int(damage_stall_timeout)}s.",
                        )
                        return BuilderScreen.RESTARTED, last_png
            if (
                stage == 1
                and stage_transition_started_at is not None
                and transition_timeout > 0
                and now - stage_transition_started_at >= transition_timeout
            ):
                self._restart_stage_watchdog(
                    "builder-stage1-transition-timeout",
                    last_png,
                    f"Làng 1 đạt 100% nhưng chưa chuyển Làng 2 sau {int(transition_timeout)}s.",
                )
                return BuilderScreen.RESTARTED, last_png
            self._sleep(float(timing.get("screen_poll_seconds", 1.0)))
        self.log(f"[BUILDER][WARN] Làng {stage} vượt thời gian theo dõi.")
        return BuilderScreen.UNKNOWN, last_png

    def _restart_stage_watchdog(self, reason: str, png: bytes, message: str) -> None:
        self._watchdog_restarts = int(getattr(self, "_watchdog_restarts", 0)) + 1
        maximum = max(1, int(self.builder.get("timing", {}).get("max_watchdog_restarts", 3)))
        self.log(f"[BUILDER][WARN] {message} Restart game ({self._watchdog_restarts}/{maximum}).")
        self._record_state_failure(reason, png, restart=False)
        if self.stop_event.is_set():
            return
        if self._watchdog_restarts >= maximum:
            self.log("[BUILDER][ERROR] Watchdog Làng đêm lỗi liên tiếp. Dừng bot.")
            self._notify_lifecycle("error", "Watchdog Làng đêm lỗi liên tiếp.")
            self.stop_event.set()
            return
        self._restart_game()

    def _maybe_activate_hero(self, png: bytes) -> None:
        deployed_at = float(getattr(self, "_hero_deployed_at", 0.0))
        if deployed_at <= 0:
            return
        deploy = self.builder.get("deploy", {})
        now = self._active_time()
        first_delay = max(0.0, float(deploy.get("hero_first_skill_delay_seconds", 28.0)))
        last_skill = float(getattr(self, "_hero_last_skill_at", 0.0))
        if last_skill <= 0 and now - deployed_at < first_delay:
            return
        if last_skill > 0:
            if not deploy.get("hero_repeat_skill", True):
                return
            minimum = max(1.0, float(deploy.get("hero_repeat_min_seconds", 15.0)))
            if now - last_skill < minimum:
                return

        poll_seconds = max(0.1, float(deploy.get("hero_ready_poll_seconds", 2.0)))
        last_check = float(getattr(self, "_hero_last_ready_check_at", 0.0))
        if last_check > 0 and now - last_check < poll_seconds:
            return
        self._hero_last_ready_check_at = now

        hero = self.builder.get("coords", {}).get("hero_slot", [162, 812])
        if not self.vision.hero_ability_ready(png, hero):
            return
        self._tap(hero, jitter=0)
        self._hero_last_skill_at = now
        self.log("[BUILDER] Kích hoạt kỹ năng tướng.")

    def _handle_result(self, png: bytes) -> None:
        self._watchdog_restarts = 0
        self._expected_stage = 1
        result = self._read_result_stable(png)
        raw_damage = int(result.get("damage", -1))
        raw_gold = int(result.get("gold", -1))
        raw_trophies = int(result.get("trophies", -1))
        damage = max(0, raw_damage)
        gold = max(0, raw_gold)
        trophies = max(0, raw_trophies)
        missing = [name for name, value in (("damage", raw_damage), ("vàng", raw_gold), ("cúp", raw_trophies)) if value < 0]
        if missing:
            self.log(f"[BUILDER][WARN] Không đọc được kết quả: {', '.join(missing)}.")
        self.stats["builder_damage"] += damage
        self.stats["builder_gold"] += gold
        self.stats["builder_trophies"] += trophies
        self._publish_stats()
        self.log(f"[BUILDER] Kết quả: damage={damage}% | vàng={gold:,} | cúp={trophies}.")
        self._tap(self.builder.get("coords", {}).get("return_home", [800, 760]))
        self._sleep(float(self.builder.get("timing", {}).get("result_wait_seconds", 12.0)))
        after_return = self._screencap_png()
        if self.vision.classify(after_return) == BuilderScreen.STAR_BONUS:
            self._dismiss_star_bonus(after_return)

    def _read_result_stable(self, png: bytes = b"") -> dict[str, int]:
        settings = self.builder.get("result_stats", {})
        attempts = max(2, int(settings.get("read_attempts", 3)))
        delay = max(0.0, float(settings.get("read_delay_seconds", 0.3)))
        samples: list[dict[str, int]] = []

        for attempt in range(attempts):
            if self.stop_event.is_set():
                break
            try:
                current_png = png if attempt == 0 and png else self._screencap_png()
            except ADBError as exc:
                self.log(f"[BUILDER][RESULT] Chụp mẫu OCR lỗi ({attempt + 1}/{attempts}): {exc}")
                continue
            result = self.vision.read_result(current_png)
            samples.append(
                {
                    "damage": int(result.get("damage", -1)),
                    "gold": int(result.get("gold", -1)),
                    "trophies": int(result.get("trophies", -1)),
                }
            )
            if attempt < attempts - 1:
                self._sleep(delay)

        values = {
            "damage": self._builder_result_number([item["damage"] for item in samples], 1),
            "gold": self._builder_result_number([item["gold"] for item in samples], 1_000),
            "trophies": self._builder_result_number([item["trophies"] for item in samples], 1),
        }
        caps = {
            "damage": max(1, int(settings.get("damage_max", 200))),
            "gold": max(1, int(settings.get("gold_max", 2_000_000))),
            "trophies": max(1, int(settings.get("trophies_max", 100))),
        }
        for name, value in tuple(values.items()):
            if value > caps[name]:
                self.log(
                    f"[BUILDER][RESULT][WARN] OCR {name} vượt cap: "
                    f"{value:,} > {caps[name]:,}; bỏ qua."
                )
                values[name] = -1
        return values

    def _builder_wall_upgrade_due(self) -> bool:
        settings = self.builder.get("wall_upgrade", {})
        if not settings.get("enabled", False) or self.attacks_since_wall_upgrade < 0:
            return False
        if settings.get("run_after_attacks_enabled", True):
            every = max(1, int(settings.get("run_every_n_attacks", 10)))
            if self.attacks_since_wall_upgrade >= every:
                return True

        resources = self._read_builder_resources_stable(settings)
        if not resources:
            return False
        threshold = max(1.0, min(100.0, float(settings.get("trigger_percent", 90)))) / 100.0
        gold_capacity = max(1, int(settings.get("gold_capacity", 6000000)))
        elixir_capacity = max(1, int(settings.get("elixir_capacity", 6000000)))
        return (
            resources["gold"] >= gold_capacity * threshold
            or resources["elixir"] >= elixir_capacity * threshold
        )

    def _upgrade_builder_walls(self) -> dict[str, Any]:
        settings = self.builder.get("wall_upgrade", {})
        coords = settings.get("coords", {})
        resources = self._read_builder_resources_stable(settings)
        if not resources:
            return {"success": False, "reason": "read_resources_failed"}

        self.log(
            f"[BUILDER][WALL] Bắt đầu. Vàng={resources['gold']:,} | "
            f"dầu={resources['elixir']:,}."
        )
        self._tap(coords.get("builder_icon", [840, 50]), jitter=0)
        self._sleep(0.8)
        wall_position = self._find_builder_wall_row(settings)
        if not wall_position:
            self.log("[BUILDER][WALL] Không tìm thấy Wall trong danh sách.")
            self._close_builder_wall_ui()
            return {"success": False, "reason": "wall_not_found"}

        self._tap(wall_position, jitter=0)
        self._sleep(0.8)
        add_rounds = max(1, int(settings.get("add1_rounds", 1)))
        for _ in range(add_rounds):
            if self.stop_event.is_set():
                self._close_builder_wall_ui()
                return {"success": False, "reason": "stopped"}
            self._tap(coords.get("add1_button", [800, 700]), jitter=0)
            self._sleep(0.25)
        self.log(f"[BUILDER][WALL] Đã bấm +1 {add_rounds} lần.")

        costs = self._read_builder_wall_costs(settings, coords)
        payment = self._select_builder_wall_payment(settings, resources, costs)
        if not payment:
            if not any(cost > 0 for cost in costs.values()):
                self.log("[BUILDER][WALL] Không đọc ổn định được giá nâng tường.")
                self._close_builder_wall_ui()
                return {"success": False, "reason": "read_cost_failed"}
            payment, add_rounds, rollback_reason = self._rollback_builder_wall_selection_to_budget(
                settings,
                coords,
                resources,
                add_rounds,
            )
            if not payment:
                self._close_builder_wall_ui()
                return {"success": False, "reason": rollback_reason}
            self.log(f"[BUILDER][WALL] Giữ lại {add_rounds} tường trong ngân sách.")
        pay_with, cost = payment
        if settings.get("dry_run", False):
            retry = max(1, int(settings.get("dry_run_retry_attacks", 10)))
            self.log(
                f"[BUILDER][WALL] Mô phỏng: sẽ trả {cost:,} bằng {pay_with}; "
                f"thử lại sau {retry} trận."
            )
            self._close_builder_wall_ui()
            self.attacks_since_wall_upgrade = -retry
            return {"success": True, "reason": "dry_run", "continue_cycle": True}

        button_key = "upgrade_gold_button" if pay_with == "gold" else "upgrade_elixir_button"
        default_button = [980, 700] if pay_with == "gold" else [1155, 700]
        self._tap(coords.get(button_key, default_button), jitter=0)
        self._sleep(0.8)
        confirmation = self._read_builder_wall_confirmation_stable(settings, pay_with, cost)
        if confirmation is None:
            self.log(
                "[BUILDER][WALL] Hộp xác nhận không đạt đồng thuận giá/loại tiền, hủy."
            )
            self._tap(coords.get("confirm_cancel_button", [622, 580]), jitter=0)
            self._sleep(0.5)
            self._close_builder_wall_ui()
            return {"success": False, "reason": "confirmation_mismatch"}

        self._tap(coords.get("confirm_okay_button", [973, 580]), jitter=0)
        self._sleep(1.2)
        after: dict[str, int] | None = None
        for verify_attempt in range(2):
            after = self._read_builder_resources_stable(settings)
            if after and int(after.get(pay_with, -1)) >= 0:
                break
            if verify_attempt == 0:
                self.log("[BUILDER][WALL] Hậu kiểm tài nguyên lỗi, đang đọc lại.")
                self._sleep(0.5)
        if not after or int(after.get(pay_with, -1)) < 0:
            message = (
                "Không thể xác minh chi tiêu Builder Wall sau khi đã bấm Okay. "
                "Bot đã dừng để tránh tiếp tục khi ngân sách không rõ ràng."
            )
            self.log(f"[BUILDER][WALL][CRITICAL] {message}")
            self._close_builder_wall_ui()
            self._notify_lifecycle("error", message)
            self.stop_event.set()
            return {"success": False, "reason": "upgrade_verify_failed"}
        if after[pay_with] >= resources[pay_with]:
            self.log("[BUILDER][WALL] Không thấy tài nguyên giảm sau khi nâng.")
            self._close_builder_wall_ui()
            return {"success": False, "reason": "upgrade_not_confirmed"}

        spent = resources[pay_with] - after[pay_with]
        budget = max(0, resources[pay_with] - int(settings.get(f"reserve_{pay_with}", 0)))
        spend_tolerance = max(
            max(0, int(settings.get("spend_verify_tolerance_absolute", 1_000))),
            int(
                max(cost, 1)
                * max(0.0, float(settings.get("spend_verify_tolerance_percent", 0.1)))
                / 100.0
            ),
        )
        if spent > budget or abs(spent - cost) > spend_tolerance:
            message = (
                f"Chi tiêu Builder Wall bất thường: modal={cost:,} | "
                f"thực tế={spent:,} | ngân sách={budget:,} {pay_with}. Bot đã dừng."
            )
            self.log(f"[BUILDER][WALL][CRITICAL] {message}")
            self._close_builder_wall_ui()
            self._notify_lifecycle("error", message)
            self.stop_event.set()
            return {"success": False, "reason": "unsafe_spend_detected"}
        self.attacks_since_wall_upgrade = 0
        self.log(f"[BUILDER][WALL] Nâng thành công, đã dùng {spent:,} {pay_with}.")
        self._close_builder_wall_ui()
        return {"success": True, "reason": ""}

    def _read_builder_wall_confirmation_stable(
        self,
        settings: dict[str, Any],
        expected_currency: str,
        expected_cost: int,
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
                sample = self.vision.read_wall_confirmation(self._screencap_png())
            except ADBError as exc:
                details.append(f"adb={exc}")
            else:
                wall_ok = bool(sample.get("is_wall_upgrade"))
                currency = str(sample.get("currency", ""))
                cost = int(sample.get("cost", -1))
                details.append(f"wall={wall_ok},currency={currency or '?'},cost={cost}")
                if wall_ok and currency == expected_currency and cost == expected_cost:
                    valid.append((wall_ok, currency, cost))
            if attempt < attempts - 1:
                self._sleep(delay)

        self.log(f"[BUILDER][WALL] Mẫu hộp xác nhận: {' | '.join(details)}.")
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

    def _select_builder_wall_payment(
        self,
        settings: dict[str, Any],
        resources: dict[str, int],
        costs: dict[str, int],
    ) -> tuple[str, int] | None:
        budgets = {
            "gold": max(0, resources["gold"] - int(settings.get("reserve_gold", 0))),
            "elixir": max(0, resources["elixir"] - int(settings.get("reserve_elixir", 0))),
        }
        for kind in sorted(budgets, key=budgets.get, reverse=True):
            cost = int(costs.get(kind, -1))
            if cost > 0 and cost <= budgets[kind]:
                return kind, cost
        return None

    def _read_builder_wall_costs(
        self,
        settings: dict[str, Any],
        coords: dict[str, Any],
    ) -> dict[str, int]:
        return {
            "gold": self._read_builder_wall_cost_stable(
                settings, coords.get("upgrade_gold_button", [980, 700])
            ),
            "elixir": self._read_builder_wall_cost_stable(
                settings, coords.get("upgrade_elixir_button", [1155, 700])
            ),
        }

    def _rollback_builder_wall_selection_to_budget(
        self,
        settings: dict[str, Any],
        coords: dict[str, Any],
        resources: dict[str, int],
        selected_walls: int,
    ) -> tuple[tuple[str, int] | None, int, str]:
        remaining = max(1, int(selected_walls))
        remove_button = coords.get("remove_button", [446, 700])
        while remaining > 1 and not self.stop_event.is_set():
            self._tap(remove_button, jitter=0)
            self._sleep(0.25)
            remaining -= 1
            costs = self._read_builder_wall_costs(settings, coords)
            if not any(cost > 0 for cost in costs.values()):
                self.log("[BUILDER][WALL] Không đọc ổn định giá sau khi giảm số tường.")
                return None, remaining, "rollback_read_failed"
            payment = self._select_builder_wall_payment(settings, resources, costs)
            self.log(
                f"[BUILDER][WALL] Đã bỏ 1 tường; còn {remaining}, "
                f"giá vàng/dầu={costs['gold']:,}/{costs['elixir']:,}."
            )
            if payment:
                return payment, remaining, ""

        if self.stop_event.is_set():
            return None, remaining, "stopped"
        self.log("[BUILDER][WALL] Một tường vẫn vượt ngân sách.")
        return None, remaining, "budget_unavailable"

    def _find_builder_wall_row(self, settings: dict[str, Any]) -> list[int] | None:
        maximum = max(0, int(settings.get("max_wall_search_scrolls", 9)))
        region = settings.get("search_region", [720, 120, 420, 580])
        swipe = settings.get("list_scroll_swipe", [930, 650, 930, 250, 500])
        for attempt in range(maximum + 1):
            png = self._screencap_png()
            position = self.vision.find_wall_row(png, region)
            if position:
                if attempt:
                    self.log(f"[BUILDER][WALL] Tìm thấy Wall sau {attempt} lần cuộn.")
                return position
            if attempt < maximum:
                self.log(f"[BUILDER][WALL] Cuộn tìm Wall ({attempt + 1}/{maximum}).")
                self._swipe(swipe)
                self._sleep(0.7)
        return None

    def _read_builder_resources_stable(self, settings: dict[str, Any]) -> dict[str, int] | None:
        attempts = max(2, int(settings.get("resource_read_attempts", 3)))
        delay = max(0.0, float(settings.get("read_attempt_delay", 0.45)))
        samples: list[dict[str, int]] = []
        for attempt in range(attempts):
            self._pause_gate()
            if self.stop_event.is_set():
                return None
            samples.append(self.vision.read_home_resources(self._screencap_png()))
            if attempt < attempts - 1:
                self._sleep(delay)
        tolerance_percent = max(0.0, float(settings.get("stable_read_tolerance_percent", 0.1)))
        tolerance_absolute = max(0, int(settings.get("stable_read_tolerance_absolute", 1_000)))
        gold = self._builder_stable_number(
            [int(item.get("gold", -1)) for item in samples],
            tolerance_percent,
            tolerance_absolute,
        )
        elixir = self._builder_stable_number(
            [int(item.get("elixir", -1)) for item in samples],
            tolerance_percent,
            tolerance_absolute,
        )
        if gold < 0 or elixir < 0:
            self.log("[BUILDER][WALL] Không đọc ổn định được vàng/dầu.")
            return None
        if gold > int(settings.get("gold_capacity", 1) * 1.2) or elixir > int(
            settings.get("elixir_capacity", 1) * 1.2
        ):
            self.log("[BUILDER][WALL] OCR tài nguyên vượt sức chứa hợp lý, bỏ qua.")
            return None
        return {"gold": gold, "elixir": elixir}

    def _read_builder_wall_cost_stable(self, settings: dict[str, Any], button: list[int]) -> int:
        attempts = max(2, int(settings.get("cost_read_attempts", 3)))
        delay = max(0.0, float(settings.get("read_attempt_delay", 0.45)))
        values: list[int] = []
        for attempt in range(attempts):
            values.append(self.vision.read_wall_upgrade_cost(self._screencap_png(), button))
            if attempt < attempts - 1:
                self._sleep(delay)
        return self._builder_stable_number(
            values,
            max(0.0, float(settings.get("stable_read_tolerance_percent", 0.1))),
            max(0, int(settings.get("stable_read_tolerance_absolute", 1_000))),
        )

    def _builder_stable_number(
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

    def _builder_result_number(self, values: list[int], tolerance_absolute: int) -> int:
        valid = sorted(value for value in values if value >= 0)
        if len(valid) < 2:
            return -1
        counts = {value: valid.count(value) for value in set(valid)}
        best, count = max(counts.items(), key=lambda item: item[1])
        if count >= 2:
            return best

        tolerance = max(0, int(tolerance_absolute))
        for index, start in enumerate(valid):
            close = [start]
            for candidate in valid[index + 1 :]:
                if candidate - start <= tolerance:
                    close.append(candidate)
                else:
                    break
            if len(close) >= 2:
                return close[len(close) // 2]
        return -1

    def _backoff_builder_wall_upgrade(self, reason: str) -> None:
        retry = max(1, int(self.builder.get("wall_upgrade", {}).get("retry_backoff_attacks", 10)))
        self.attacks_since_wall_upgrade = -retry
        self.log(f"[BUILDER][WALL] Thất bại ({reason}), thử lại sau {retry} trận.")

    def _close_builder_wall_ui(self) -> None:
        for _ in range(2):
            if self.stop_event.is_set():
                return
            self._shell("input", "keyevent", "KEYCODE_BACK", timeout=5)
            self._sleep(0.3)

    def _wait_for_states(self, states: set[str], timeout: float) -> tuple[str, bytes]:
        deadline = self._active_time() + max(0.1, timeout)
        confirmations = max(1, int(self.builder.get("timing", {}).get("state_confirmations", 2)))
        last_png = b""
        candidate_state = BuilderScreen.UNKNOWN
        candidate_reads = 0
        while not self.stop_event.is_set() and self._active_time() < deadline:
            self._pause_gate()
            if self.stop_event.is_set():
                break
            last_png = self._screencap_png()
            state = self.vision.classify(last_png)
            if state in states:
                if state == candidate_state:
                    candidate_reads += 1
                else:
                    candidate_state = state
                    candidate_reads = 1
                if candidate_reads >= confirmations:
                    return state, last_png
            else:
                candidate_state = BuilderScreen.UNKNOWN
                candidate_reads = 0
            self._sleep(float(self.builder.get("timing", {}).get("screen_poll_seconds", 1.0)))
        return BuilderScreen.UNKNOWN, last_png

    def _zoom_out(self, count: int) -> None:
        for _ in range(max(0, count)):
            self._pause_gate()
            if self.stop_event.is_set():
                return
            if not self._ldplayer_zoom_out():
                self._shell("input", "keyevent", "KEYCODE_ZOOM_OUT", timeout=5)
            self._sleep(0.25)

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

    def _restart_game(self) -> None:
        package = self.config.get("adb", {}).get("package", "com.supercell.clashofclans")
        self._pause_gate()
        if self.stop_event.is_set():
            return
        self.adb.force_stop_app(package)
        self._sleep(1)
        if self.stop_event.is_set():
            return
        self._pause_gate()
        if self.stop_event.is_set():
            return
        self.adb.start_app(package)
        self._sleep(float(self.config.get("game", {}).get("restart_wait_seconds", 18)))

    def _auto_stop_after_seconds(self) -> int:
        game = self.config.get("game", {})
        if not game.get("auto_stop", False):
            return 0
        return max(0, int(game.get("auto_restart_after_seconds", 0)))

    def _auto_stop_due(self) -> bool:
        if self.auto_stop_at <= 0 or time.time() < self.auto_stop_at:
            return False
        elapsed = int(time.time() - self.run_started_at)
        self.log(f"[SCHEDULE] Tự dừng Làng đêm sau {elapsed}s.")
        self.stop_event.set()
        return True

    def _next_periodic_restart_at(self, now: float) -> float:
        game = self.config.get("game", {})
        if not game.get("periodic_restart_game", False):
            return 0.0
        minimum = max(1, int(game.get("periodic_restart_min_seconds", 3600)))
        maximum = max(minimum, int(game.get("periodic_restart_max_seconds", minimum)))
        delay = random.randint(minimum, maximum)
        self.log(f"[SCHEDULE] Restart Làng đêm tiếp theo sau {delay}s.")
        return now + delay

    def _periodic_restart_game(self) -> None:
        self.log("[SCHEDULE] Restart game định kỳ ở chế độ Làng đêm.")
        self._restart_game()

    def _shift_schedules_after_pause(self, paused_seconds: float) -> None:
        if paused_seconds <= 0:
            return
        if self.auto_stop_at > 0:
            self.auto_stop_at += paused_seconds
        if self.next_periodic_restart_at > 0:
            self.next_periodic_restart_at += paused_seconds

    def _record_state_failure(self, reason: str, png: bytes = b"", restart: bool = True) -> None:
        if self.stop_event.is_set():
            return
        self._state_failures = int(getattr(self, "_state_failures", 0)) + 1
        timing = self.builder.get("timing", {})
        maximum = max(1, int(timing.get("max_state_failures", 5)))
        restart_after = max(1, int(timing.get("restart_after_state_failures", 2)))
        self.log(
            f"[BUILDER][WARN] Lỗi trạng thái {self._state_failures}/{maximum}: {reason}."
        )
        self._dump_debug(reason, png)
        if self._state_failures >= maximum:
            self.log("[BUILDER][ERROR] Không thể phục hồi trạng thái Làng đêm. Dừng bot.")
            self._notify_lifecycle("error", "Không thể phục hồi trạng thái Làng đêm.")
            self.stop_event.set()
            return
        if restart and self._state_failures % restart_after == 0:
            self.log("[BUILDER] Khởi động lại game để phục hồi trạng thái.")
            self._restart_game()

    def _clear_state_failures(self) -> None:
        self._state_failures = 0

    def _clustered_points(self, polygon: list[list[int]], count: int) -> list[list[int]]:
        polygon = self._valid_polygon(polygon)
        if not polygon:
            raise ValueError("Builder deploy polygon không hợp lệ hoặc không có diện tích.")
        deploy = self.builder.get("deploy", {})
        candidates = self._random_points_in_polygon(polygon, max(32, int(deploy.get("random_points", 64))))
        anchor = random.choice(candidates)
        minimum = max(0, int(deploy.get("point_spacing_min_px", 20)))
        maximum = max(minimum, int(deploy.get("point_spacing_max_px", 45)))
        points = [anchor]
        attempts = 0
        while len(points) < count and attempts < count * 120:
            attempts += 1
            distance = random.randint(minimum, maximum)
            candidate = [
                anchor[0] + random.randint(-distance, distance),
                anchor[1] + random.randint(-distance, distance),
            ]
            if self._point_in_polygon(candidate, polygon) and self._far_enough(candidate, points, minimum):
                points.append(candidate)
        while len(points) < count:
            points.append(random.choice(candidates))
        return points

    def _random_points_in_polygon(self, polygon: list[list[int]], count: int) -> list[list[int]]:
        min_x = min(point[0] for point in polygon)
        max_x = max(point[0] for point in polygon)
        min_y = min(point[1] for point in polygon)
        max_y = max(point[1] for point in polygon)
        points: list[list[int]] = []
        for _ in range(max(100, count * 80)):
            candidate = [random.randint(min_x, max_x), random.randint(min_y, max_y)]
            if self._point_in_polygon(candidate, polygon):
                points.append(candidate)
                if len(points) >= count:
                    break
        return points or polygon

    def _point_in_polygon(self, point: list[int], polygon: list[list[int]]) -> bool:
        x, y = point
        inside = False
        previous = len(polygon) - 1
        for current in range(len(polygon)):
            xi, yi = polygon[current]
            xj, yj = polygon[previous]
            if ((yi > y) != (yj > y)) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
                inside = not inside
            previous = current
        return inside

    def _far_enough(self, point: list[int], points: list[list[int]], minimum: int) -> bool:
        return all((point[0] - other[0]) ** 2 + (point[1] - other[1]) ** 2 >= minimum**2 for other in points)

    def _valid_polygon(self, points: Any) -> list[list[int]]:
        return normalize_polygon(points)

    def _active_time(self) -> float:
        return time.time() - float(getattr(self, "_paused_seconds_total", 0.0))

    def _stop_requested(self) -> bool:
        stop_event = getattr(self, "stop_event", None)
        return bool(stop_event and stop_event.is_set())

    def _tap(self, point: list[int], jitter: int = 4) -> None:
        self._pause_gate()
        if self._stop_requested():
            return
        self.adb.tap(int(point[0]), int(point[1]), jitter=jitter)

    def _swipe(self, values: list[int]) -> None:
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

    def _sleep(self, seconds: float) -> None:
        deadline = self._active_time() + max(0.0, float(seconds))
        while not self._stop_requested() and self._active_time() < deadline:
            self._pause_gate()
            if self._stop_requested():
                return
            remaining = deadline - self._active_time()
            if remaining > 0:
                time.sleep(min(0.1, remaining))

    def _pause_gate(self) -> float:
        pause_event = getattr(self, "pause_event", None)
        if pause_event is None:
            return 0.0
        pause_started_at = 0.0
        while pause_event.is_set() and not self._stop_requested():
            if pause_started_at <= 0:
                pause_started_at = time.time()
            time.sleep(0.2)
        if pause_started_at <= 0:
            return 0.0
        paused_seconds = time.time() - pause_started_at
        self._paused_seconds_total = float(getattr(self, "_paused_seconds_total", 0.0)) + paused_seconds
        self._shift_schedules_after_pause(paused_seconds)
        self.log(f"[SCHEDULE] Pause {int(paused_seconds)}s, lịch Làng đêm được dời lại.")
        return paused_seconds

    def _load_total_stats(self) -> dict[str, int]:
        return load_total_stats(self.stats_path)

    def _publish_stats(self) -> None:
        total = {key: self.base_total_stats.get(key, 0) + self.stats.get(key, 0) for key in self.STAT_KEYS}
        payload = {
            "session_started_at": self.session_started_at,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
            "current_session": dict(self.stats),
            "total": total,
        }
        merged = merge_existing_stats(self.stats_path, payload)
        try:
            atomic_write_json(self.stats_path, merged)
        except OSError as exc:
            self.log(f"[BUILDER][WARN] Không lưu được thống kê: {exc}")
            self.stats_callback(payload)
            return
        self.stats_callback(merged)

    def _dump_debug(self, reason: str, png: bytes = b"") -> None:
        if not png:
            try:
                png = self._screencap_png()
            except ADBError:
                return
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.debug_dir / f"{self.safe_device}-{timestamp}-{self._safe_name(reason)}.png"
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
            self.log(f"[BUILDER][DEBUG] Đã lưu ảnh: {path}")
        except OSError:
            return

    def _safe_name(self, value: str) -> str:
        return "".join(character if character.isalnum() or character in ("-", "_") else "_" for character in value)
