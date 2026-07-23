from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from adb_client import ADBClient, ADBError
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

    def run(self) -> None:
        try:
            if self.config["adb"]["connect_on_start"]:
                self.adb.connect()
            if not self._ocr_ready_or_stop():
                return
            self.log(f"[COMBO] Dang dung: {self.active_combo}.")
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
            f"[ERROR] Qua nhieu loi cycle lien tiep ({cycle_errors}/{max_cycle_errors}). "
            "Tu dong dung bot."
        )
        self.stop_event.set()
        return True

    def _ocr_ready_or_stop(self) -> bool:
        if self.vision.available:
            return True
        tesseract_path = self.config.get("ocr", {}).get("tesseract_path") or "PATH/default Windows path"
        self.log(
            "[ERROR] OCR chua san sang. Kiem tra ocr.tesseract_path, cai Tesseract OCR, "
            f"va cai Pillow/pytesseract. Hien tai tesseract_path={tesseract_path!r}."
        )
        self.stop_event.set()
        return False

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
            self.log(f"[HOME] Khong thay nut Attack ({attempt}/{retries}).")
            self._sleep(1)

        self._dump_debug_png("home_attack_missing_before_restart", last_png)
        package = self.config["adb"]["package"]
        wait_seconds = float(game.get("restart_wait_seconds", 18))
        self.log("[HOME] Khong thay nut Attack. Restart game...")
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
            f"[HOME] Restart xong nhung van khong thay nut Attack "
            f"({self.home_restart_failures}/{max_failures})."
        )
        if max_failures > 0 and self.home_restart_failures >= max_failures:
            self.log("[ERROR] Qua nhieu lan restart home that bai. Tu dong dung bot.")
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
                self.log(
                    f"[SEARCH] Loot: gold={loot['gold']:,} | elixir={loot['elixir']:,} | "
                    f"dark={loot['dark']:,}"
                )
                if self._should_attack(loot):
                    self.stats["attacks"] += 1
                    self.stats["gold_seen"] += max(loot["gold"], 0)
                    self.stats["elixir_seen"] += max(loot["elixir"], 0)
                    self.stats["dark_seen"] += max(loot["dark"], 0)
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
        self._prepare_camera()

        attack_start = time.time()
        self._deploy_troops()
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

    def _deploy_troops(self) -> None:
        points = self._deploy_points()
        for step in self.active_deploy["sequence"]:
            slot = step["slot"]
            count = self._tap_limit(step.get("count", 0), int(step.get("max_taps", 0)))
            if count <= 0:
                continue
            label = "all" if self._is_all(step.get("count")) else str(count)
            self.log(f"[ATTACK] Select {slot}, deploy {label} (max {count}).")
            self._tap_slot(slot)
            delay = self._troop_delay_seconds(float(step.get("delay", 0.2)))
            for i in range(count):
                if self._slot_check_due(step, i) and not self._slot_available(slot):
                    self.log(f"[ATTACK] Slot {slot} looks empty, stop deploy.")
                    break
                x, y = points[i % len(points)]
                self.adb.tap(x, y)
                self._optimized_action_pause()
                self._sleep(delay)

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
            self.log(f"[SPELL] Cast {spell_name} ({spell['slot']}).")
            self._tap_slot(spell["slot"])
            points = spell.get("points", [])
            max_casts = int(spell.get("max_casts", len(points)))
            for x, y in points[:max_casts]:
                self._spell_random_delay(spell["slot"])
                self.adb.tap(int(x), int(y))
                self._optimized_action_pause()
                self._sleep(0.18)

    def _cast_spell_groups(self, spell_groups: list[dict[str, Any]], deploy_finished: float) -> None:
        for group in spell_groups:
            if not group.get("enabled", True):
                continue
            points = group.get("points", [])
            slots = group.get("slots", [])
            if not points or not slots:
                continue
            delay = float(group.get("delay_after_deploy", 0))
            while time.time() - deploy_finished < delay and not self.stop_event.is_set():
                self._sleep(0.1)

            max_casts = self._tap_limit(group.get("max_casts", len(points)), len(points))
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
                self._optimized_action_pause()
                self._sleep(delay_between)

    def _activate_post_deploy_slots(self, deploy_finished: float) -> None:
        if not self._custom_attack_timing_enabled():
            return

        activations = [
            ("hero", "hero_skill_min_ms", "hero_skill_max_ms", "Skill tuong"),
            ("siege", "siege_activation_min_ms", "siege_activation_max_ms", "Quan giao"),
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
        pending_damage: dict[str, int] = {"value": -1, "reads": 0}
        max_jump = int(surrender.get("damage_jump_confirm_percent", 40))
        max_pending_reads = int(surrender.get("damage_jump_max_pending_reads", 3))

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
        self.log("[RESULT] Tap Return Home.")
        self._tap_coord("return_home")
        self._sleep(self.config["timing"]["after_return_home"])
        self._next_battle_random_delay()

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
        mode = self.config["farm"]["deploy_mode"]
        deploy = self.active_deploy
        if mode == "one_edge":
            view = self.current_attack_view or self._selected_attack_view()
            view_points = deploy.get("view_points", {})
            if view in view_points and view_points[view]:
                self.log(f"[VIEW] Deploy view: {view}.")
                return view_points[view]
            edge = self._selected_attack_edge()
            edge_points = deploy.get("edge_points", {})
            if edge in edge_points:
                self.log(f"[EDGE] Deploy edge: {edge}.")
                return edge_points[edge]
            return deploy["one_edge_points"]
        if mode == "four_corner":
            return deploy["four_corner_points"]
        if mode == "random":
            x1, y1, x2, y2 = deploy["random_area"]
            return [[random.randint(x1, x2), random.randint(y1, y2)] for _ in range(12)]
        return deploy["line_points"]

    def _selected_attack_edge(self) -> str:
        edge = self.config["farm"].get("attack_edge", "top")
        valid_edges = ("top", "bottom", "left", "right")
        if edge == "random":
            chosen = random.choice(valid_edges)
            self.log(f"[EDGE] Random edge: {chosen}.")
            return chosen
        if edge == "auto":
            fallback = self.active_deploy.get("auto_edge_fallback", "top")
            self.log(f"[EDGE] Auto edge chua bat vision kho, fallback {fallback}.")
            return fallback
        if edge in valid_edges:
            return edge
        return "top"

    def _selected_attack_view(self) -> str:
        deploy = self.active_deploy
        view_points = deploy.get("view_points", {})
        valid_views = tuple(
            view
            for view in ("trenbenphai", "trenbentrai", "duoibenphai", "duoibentrai")
            if view_points.get(view)
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
            self.log(f"[VIEW] Auto view chua bat vision, fallback {fallback}.")
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
            self.log(f"[SCHEDULE] Pause {int(paused_seconds)}s, auto-stop duoc doi lai.")

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
            self.log(f"[WARN] Khong ghi duoc stats.json: {exc}")

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
            self.log(f"[WARN] Khong ghi duoc debug screencap: {exc}")

    def _safe_name(self, value: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in value)
