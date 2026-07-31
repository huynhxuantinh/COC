from __future__ import annotations

import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from adb_client import ADBClient, ADBError
from bot import FarmBot
from config_manager import normalize_config


class _TapRecorder:
    def __init__(self) -> None:
        self.taps: list[tuple[int, int]] = []

    def tap(self, x: int, y: int) -> None:
        self.taps.append((x, y))


class _ScreenshotADB(_TapRecorder):
    def __init__(self, png: bytes) -> None:
        super().__init__()
        self.png = png

    def screencap_png(self) -> bytes:
        return self.png


class SafetyRegressionTests(unittest.TestCase):
    def _bare_bot(self) -> FarmBot:
        bot = FarmBot.__new__(FarmBot)
        bot.log_messages = []
        bot.log = bot.log_messages.append
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        bot.runtime_slots = {}
        bot.manual_slot_counts = {}
        bot.config = {
            "coords": {"slots": {}},
            "attack_timing": {"use_default": True},
            "manual_army": {"enabled": False},
        }
        bot.active_deploy = {}
        return bot

    def test_adb_nonzero_exit_raises(self) -> None:
        client = ADBClient.__new__(ADBClient)
        client.adb_path = "adb.exe"
        failed = subprocess.CompletedProcess(
            ["adb.exe", "devices"],
            1,
            stdout=b"",
            stderr=b"device offline",
        )
        with patch("adb_client.subprocess.run", return_value=failed):
            with self.assertRaisesRegex(ADBError, "device offline"):
                client._run(["devices"])

    def test_missing_custom_slot_fallback_is_skipped(self) -> None:
        bot = self._bare_bot()
        bot.adb = _TapRecorder()

        self.assertFalse(bot._tap_slot("custom_troop"))
        self.assertEqual(bot.adb.taps, [])
        self.assertTrue(any("custom_troop" in message for message in bot.log_messages))

    def test_initial_damage_outlier_requires_confirmation(self) -> None:
        bot = self._bare_bot()
        pending = {"value": -1, "reads": 0}

        best, pending = bot._filter_damage_reading(91, -1, pending, 40, 3)
        self.assertEqual(best, -1)
        self.assertEqual(pending["value"], 91)

        best, pending = bot._filter_damage_reading(90, best, pending, 40, 3)
        self.assertEqual(best, 90)
        self.assertEqual(pending, {"value": -1, "reads": 0})

    def test_debug_dump_can_capture_its_own_screenshot(self) -> None:
        bot = self._bare_bot()
        bot.adb = _ScreenshotADB(b"png-bytes")
        bot.safe_device = "device_5555"
        with tempfile.TemporaryDirectory() as directory:
            bot.debug_dir = Path(directory)
            bot._dump_debug_png("slot_unknown")
            files = list(Path(directory).glob("device_5555-*-slot_unknown.png"))
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].read_bytes(), b"png-bytes")

    def test_old_config_receives_new_safety_defaults(self) -> None:
        config = normalize_config({"game": {}, "farm": {}, "surrender": {}})
        self.assertEqual(config["game"]["result_wait_seconds"], 15)
        self.assertEqual(config["farm"]["max_ocr_restarts"], 3)
        self.assertEqual(config["surrender"]["max_damage_ocr_restarts"], 3)

    def test_restart_state_does_not_enter_result_flow(self) -> None:
        bot = self._bare_bot()
        bot.config["timing"] = {
            "after_home_attack": 0,
            "after_find_match": 0,
            "after_my_army_attack": 0,
        }
        bot._ensure_home_attack_visible = lambda: True
        bot._zoom_out_home = lambda: None
        bot._tap_coord = lambda _name: None
        bot._sleep = lambda _seconds: None
        bot._search_base = lambda: True
        bot._attack_base = lambda: {"state": "restarted", "attacked": True}
        bot._wait_return_home = lambda: self.fail("result flow must not run after restart")

        bot._run_cycle()


if __name__ == "__main__":
    unittest.main()
