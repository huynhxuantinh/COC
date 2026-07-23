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
        self.adb = ADBClient(config["adb"]["path"], config["adb"]["device"], log=log)
        self.vision = Vision(config, log=log)
        self.stats = {key: 0 for key in self.STAT_KEYS}
        self.stats_callback = stats_callback or (lambda stats: None)
        self.stats_path = Path(config.get("runtime", {}).get("stats_path", "stats.json"))
        self.debug_dir = Path("debug")
        self.session_started_at = datetime.now().isoformat(timespec="seconds")
        self.base_total_stats = self._load_total_stats()
        self.run_started_at = 0.0
        self.auto_stop_at = 0.0
        self.active_combo = self._select_active_combo()
        self.active_deploy = self._active_deploy()

    def run(self) -> None:
        try:
            if self.config["adb"]["connect_on_start"]:
                self.adb.connect()
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
        self.adb.restart_app(package, wait_seconds=wait_seconds)

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
                return True
            self.log(f"[HOME] Khong thay nut Attack ({attempt}/{retries}).")
            self._sleep(1)

        self._dump_debug_png("home_attack_missing_before_restart", last_png)
        package = self.config["adb"]["package"]
        wait_seconds = float(game.get("restart_wait_seconds", 18))
        self.log("[HOME] Khong thay nut Attack. Restart game...")
        self.adb.restart_app(package, wait_seconds=wait_seconds)

        png = self.adb.screencap_png()
        if self.vision.has_home_attack_button(png):
            self.log("[HOME] Restart xong, da thay nut Attack.")
            return True

        self._dump_debug_png("home_attack_missing_after_restart", png)
        self.log("[HOME] Restart xong nhung van khong thay nut Attack.")
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
        self.adb.restart_app(package, wait_seconds=wait_seconds)

    def _attack_base(self) -> None:
        self._prepare_camera()

        attack_start = time.time()
        self._deploy_troops()
        deploy_finished = time.time()
        self._cast_spells(deploy_finished)
        self._monitor_battle(attack_start)

    def _prepare_camera(self) -> None:
        deploy = self.active_deploy
        zoom_count = int(deploy.get("zoom_out_keyevents", 0))
        if zoom_count > 0:
            self.log(f"[CAMERA] Zoom out x{zoom_count}.")
            for _ in range(zoom_count):
                self.adb.shell("input", "keyevent", "169", timeout=5)
                self._sleep(0.2)

        swipes = deploy.get("camera_swipes", [])
        if swipes:
            self.log(f"[CAMERA] Move camera x{len(swipes)}.")
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
            count = int(step["count"])
            if count <= 0:
                continue
            self.log(f"[ATTACK] Select {slot}, deploy {count}.")
            self._tap_slot(slot)
            for i in range(count):
                x, y = points[i % len(points)]
                self.adb.tap(x, y)
                self._sleep(float(step.get("delay", 0.2)))

    def _cast_spells(self, deploy_finished: float) -> None:
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
                self.adb.tap(int(x), int(y))
                self._sleep(0.18)

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
        max_seconds = int(surrender["max_battle_seconds"])
        best_damage = -1

        self.log(f"[BATTLE] Monitor. time={target_time}s, damage={target_damage}%.")
        while not self.stop_event.is_set():
            self._pause_gate()
            elapsed = int(time.time() - attack_start)
            png = self.adb.screencap_png()
            raw_damage = self.vision.read_damage_percent(png)
            if raw_damage >= 0:
                if raw_damage >= best_damage:
                    best_damage = raw_damage
                else:
                    self.log(f"[BATTLE] Ignore OCR damage drop {best_damage}% -> {raw_damage}%.")
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

    def _wait_return_home(self) -> None:
        self.log("[RESULT] Wait result screen.")
        self._sleep(6)
        if self.stop_event.is_set():
            return
        self.log("[RESULT] Tap Return Home.")
        self._tap_coord("return_home")
        self._sleep(self.config["timing"]["after_return_home"])

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
        dark_ok = loot["dark"] >= int(farm["dark_min"])
        total_ok = (max(loot["gold"], 0) + max(loot["elixir"], 0)) >= int(farm["total_min"])
        mode = farm.get("threshold_mode", "any")
        if mode == "all":
            return gold_ok and elixir_ok and dark_ok and total_ok
        if mode == "total":
            return total_ok or dark_ok
        return gold_ok or elixir_ok or dark_ok or total_ok

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
            total = max(loot.get("gold", -1), 0) + max(loot.get("elixir", -1), 0)
            if total < int(surrender["total_remaining_less_than"]):
                return f"remaining loot {total:,} < {int(surrender['total_remaining_less_than']):,}"
        return ""

    def _deploy_points(self) -> list[list[int]]:
        mode = self.config["farm"]["deploy_mode"]
        deploy = self.active_deploy
        if mode == "one_edge":
            return deploy["one_edge_points"]
        if mode == "four_corner":
            return deploy["four_corner_points"]
        if mode == "random":
            x1, y1, x2, y2 = deploy["random_area"]
            return [[random.randint(x1, x2), random.randint(y1, y2)] for _ in range(12)]
        return deploy["line_points"]

    def _tap_coord(self, name: str) -> None:
        x, y = self.config["coords"][name]
        self.adb.tap(int(x), int(y))
        self._sleep(self.config["timing"]["after_click"])

    def _tap_slot(self, name: str) -> None:
        x, y = self.config["coords"]["slots"][name]
        self.adb.tap(int(x), int(y))
        self._sleep(0.18)

    def _sleep(self, seconds: float) -> None:
        end = time.time() + self._jittered_sleep_seconds(seconds)
        while time.time() < end:
            if self.stop_event.is_set() or self._auto_stop_due():
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
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.2)

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
        safe_reason = "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in reason)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = self.debug_dir / f"{timestamp}-{safe_reason}.png"
        try:
            self.debug_dir.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
            self.log(f"[DEBUG] Saved screencap: {path}")
        except OSError as exc:
            self.log(f"[WARN] Khong ghi duoc debug screencap: {exc}")
