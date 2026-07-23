from __future__ import annotations

import random
import threading
import time
from typing import Any

from adb_client import ADBClient, ADBError
from vision import Vision


class FarmBot:
    def __init__(
        self,
        config: dict[str, Any],
        log,
        stop_event: threading.Event,
        pause_event: threading.Event,
    ) -> None:
        self.config = config
        self.log = log
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.adb = ADBClient(config["adb"]["path"], config["adb"]["device"], log=log)
        self.vision = Vision(config, log=log)
        self.stats = {"attacks": 0, "next": 0, "gold_seen": 0, "elixir_seen": 0, "dark_seen": 0}

    def run(self) -> None:
        try:
            if self.config["adb"]["connect_on_start"]:
                self.adb.connect()
            if not self.config["game"]["skip_restart_game"]:
                self.log("[GAME] Start Clash of Clans.")
                self.adb.start_app(self.config["adb"]["package"])
                self._sleep(10)

            self.log("[INFO] Bot started.")
            cycle_errors = 0
            while not self.stop_event.is_set():
                self._pause_gate()
                try:
                    self._run_cycle()
                    cycle_errors = 0
                except ADBError as exc:
                    cycle_errors += 1
                    self.log(f"[WARN] Cycle ADB error ({cycle_errors}): {exc}. Retry next cycle.")
                    try:
                        self.adb.connect()
                    except ADBError as reconnect_exc:
                        self.log(f"[WARN] ADB reconnect failed: {reconnect_exc}")
                    self._sleep(3)
                except Exception as exc:
                    cycle_errors += 1
                    self.log(f"[WARN] Cycle error ({cycle_errors}): {exc}. Retry next cycle.")
                    self._sleep(3)
                self._sleep(self.config["timing"]["loop_sleep"])
        except ADBError as exc:
            self.log(f"[ERROR] {exc}")
        except Exception as exc:
            self.log(f"[ERROR] Bot stopped by error: {exc}")
        finally:
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

    def _ensure_home_attack_visible(self) -> bool:
        game = self.config["game"]
        if not game.get("restart_if_attack_missing", True):
            return True

        retries = int(game.get("attack_missing_retries", 3))
        for attempt in range(1, retries + 1):
            self._pause_gate()
            if self.stop_event.is_set():
                return False
            png = self.adb.screencap_png()
            if self.vision.has_home_attack_button(png):
                if attempt > 1:
                    self.log("[HOME] Attack button found.")
                return True
            self.log(f"[HOME] Khong thay nut Attack ({attempt}/{retries}).")
            self._sleep(1)

        package = self.config["adb"]["package"]
        wait_seconds = float(game.get("restart_wait_seconds", 18))
        self.log("[HOME] Khong thay nut Attack. Restart game...")
        self.adb.restart_app(package, wait_seconds=wait_seconds)

        png = self.adb.screencap_png()
        if self.vision.has_home_attack_button(png):
            self.log("[HOME] Restart xong, da thay nut Attack.")
            return True

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

            loot = self._read_loot()
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
                    self.log("[SEARCH] Base matched. Deploy troops.")
                    return True

                self.stats["next"] += 1
                self.log(f"[SEARCH] Base low. Next ({index + 1}/{max_next}).")
                self._tap_coord("next")
                self._sleep(self.config["timing"]["after_next"])
            else:
                if ocr_fail_started_at is None:
                    ocr_fail_started_at = time.time()
                fail_seconds = int(time.time() - ocr_fail_started_at)
                self.log(f"[SEARCH] OCR could not read loot ({fail_seconds}s), wait.")
                if fail_seconds >= ocr_fail_restart_seconds:
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
        deploy = self.config["deploy"]
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
        for step in self.config["deploy"]["sequence"]:
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
        for spell in self.config["deploy"]["spells"]:
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
        if not self.vision.available:
            raise RuntimeError("OCR is not ready, cannot read loot.")
        png = self.adb.screencap_png()
        return self.vision.read_loot(png)

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
        deploy = self.config["deploy"]
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
        end = time.time() + float(seconds)
        while time.time() < end:
            if self.stop_event.is_set():
                return
            time.sleep(min(0.1, end - time.time()))

    def _pause_gate(self) -> None:
        while self.pause_event.is_set() and not self.stop_event.is_set():
            time.sleep(0.2)
