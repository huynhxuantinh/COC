from __future__ import annotations

import copy
import json
import queue
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image
from fastapi import HTTPException
from pydantic import ValidationError

from adb_client import ADBClient, ADBError
from backend.models.schemas import ConfigPayload, SavePointsPayload
from backend.routers import bot as bot_router
from backend.routers import config as config_router
from backend.routers import coordinates as coordinates_router
from backend.services.bot_service import BotService
from bot import FarmBot
from config_manager import DEFAULT_CONFIG, load_config, normalize_config, save_config
from slot_detector import SlotDetector
from stats_store import atomic_write_json
from vision import Vision


class _TapRecorder:
    def __init__(self) -> None:
        self.taps: list[tuple[int, int]] = []

    def tap(self, x: int, y: int, jitter: int = 4) -> None:
        self.taps.append((x, y))


class _ScreenshotADB(_TapRecorder):
    def __init__(self, png: bytes) -> None:
        super().__init__()
        self.png = png

    def screencap_png(self) -> bytes:
        return self.png


class _WallVision:
    available = True

    def __init__(self, confirmation: dict[str, object] | list[dict[str, object]]) -> None:
        self.confirmations = confirmation if isinstance(confirmation, list) else [confirmation]
        self.index = 0

    def read_wall_confirmation(self, _png: bytes, _settings: dict[str, object]) -> dict[str, object]:
        sample = dict(self.confirmations[min(self.index, len(self.confirmations) - 1)])
        self.index += 1
        cost = int(sample.get("cost", -1))
        sample.setdefault("text_cost", cost)
        sample.setdefault("region_cost", cost)
        sample.setdefault("sources_match", cost > 0)
        return sample


class SafetyRegressionTests(unittest.TestCase):
    def _bare_bot(self) -> FarmBot:
        bot = FarmBot.__new__(FarmBot)
        bot.log_messages = []
        bot.log = bot.log_messages.append
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        bot.runtime_slots = {}
        bot.manual_slot_counts = {}
        bot.deployed_hero_centers = []
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

    def test_save_points_schema_rejects_invalid_point_shape(self) -> None:
        with self.assertRaises(ValidationError):
            SavePointsPayload(target="zone_trenbenphai", points=[[]])

        with self.assertRaises(ValidationError):
            SavePointsPayload(target="zone_trenbenphai", points=[[1, 2, 3]])

    def test_save_points_service_rejects_invalid_point_shape(self) -> None:
        service = BotService.__new__(BotService)

        with self.assertRaisesRegex(ValueError, "đúng hai tọa độ"):
            service.save_points("zone_trenbenphai", [[]])

    def test_missing_custom_slot_fallback_is_skipped(self) -> None:
        bot = self._bare_bot()
        bot.adb = _TapRecorder()

        self.assertFalse(bot._tap_slot("custom_troop"))
        self.assertEqual(bot.adb.taps, [])
        self.assertTrue(any("custom_troop" in message for message in bot.log_messages))

    def test_home_pause_blocks_coordinate_tap_and_freezes_active_time(self) -> None:
        bot = self._bare_bot()
        bot.pause_event.set()
        bot.auto_stop_at = 0.0
        bot.next_periodic_restart_at = 0.0
        bot._paused_seconds_total = 0.0
        bot.config["coords"]["find_match"] = [25, 50]
        bot._optimized_action_pause = lambda: None
        bot._after_click_seconds = lambda: 0.0
        bot._sleep = lambda _seconds: None
        taps: list[tuple[int, int, int]] = []
        bot.adb = type(
            "ADB",
            (),
            {"tap": lambda _self, x, y, jitter=4: taps.append((x, y, jitter))},
        )()

        def resume_after_wait(_seconds: float) -> None:
            self.assertEqual(taps, [])
            bot.pause_event.clear()

        with patch("bot.time.time", side_effect=[100.0, 105.0]), patch(
            "bot.time.sleep", side_effect=resume_after_wait
        ):
            bot._tap_coord("find_match")

        self.assertEqual(taps, [(25, 50, 4)])
        self.assertEqual(bot._paused_seconds_total, 5.0)
        with patch("bot.time.time", return_value=110.0):
            self.assertEqual(bot._active_time(), 105.0)

    def test_home_pause_blocks_ldconsole_zoom_until_resume(self) -> None:
        bot = self._bare_bot()
        bot.config["adb"] = {"path": "C:/LDPlayer/adb.exe"}
        bot.config["game"] = {"ldplayer_index": 0}
        bot.auto_stop_at = 0.0
        bot.next_periodic_restart_at = 0.0
        bot._paused_seconds_total = 0.0
        bot.pause_event.set()
        zoom_calls: list[list[str]] = []

        def resume_after_wait(_seconds: float) -> None:
            self.assertEqual(zoom_calls, [])
            bot.pause_event.clear()

        def record_zoom(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
            zoom_calls.append(command)
            return subprocess.CompletedProcess(command, 0)

        with patch("bot.Path.exists", return_value=True), patch(
            "bot.time.time", side_effect=[100.0, 105.0]
        ), patch("bot.time.sleep", side_effect=resume_after_wait), patch(
            "bot.subprocess.run", side_effect=record_zoom
        ):
            self.assertTrue(bot._ldplayer_zoom_out())

        self.assertEqual(len(zoom_calls), 1)
        self.assertEqual(bot._paused_seconds_total, 5.0)

    def test_home_stop_skips_ldconsole_zoom(self) -> None:
        bot = self._bare_bot()
        bot.config["adb"] = {"path": "C:/LDPlayer/adb.exe"}
        bot.config["game"] = {"ldplayer_index": 0}
        bot.stop_event.set()

        with patch("bot.Path.exists", return_value=True), patch("bot.subprocess.run") as run:
            self.assertFalse(bot._ldplayer_zoom_out())

        run.assert_not_called()

    def test_backend_rejects_active_slot_without_template_or_fallback(self) -> None:
        service = BotService.__new__(BotService)
        config = normalize_config({})
        kind = "custom_new_without_input"
        config["slot_detection"]["kinds"].append(kind)
        config["combos"]["Broken"] = {
            "deploy": {
                **config["deploy"],
                "sequence": [{"slot": kind, "count": "all", "max_taps": 10, "delay": 0.1}],
            }
        }

        with self.assertRaisesRegex(ValueError, "template nhận diện hợp lệ"):
            service._validate_config(config)

    def test_backend_accepts_active_slot_with_fallback_coordinate(self) -> None:
        service = BotService.__new__(BotService)
        config = normalize_config({})
        kind = "custom_new_with_fallback"
        config["slot_detection"]["kinds"].append(kind)
        config["coords"]["slots"][kind] = [500, 815]
        config["combos"]["Fallback"] = {
            "deploy": {
                **config["deploy"],
                "sequence": [{"slot": kind, "count": "all", "max_taps": 10, "delay": 0.1}],
            }
        }

        service._validate_config(config)

    def test_test_tap_is_rejected_while_bot_thread_is_running(self) -> None:
        service = BotService.__new__(BotService)
        service.lock = threading.RLock()
        service.bot_threads = [type("Thread", (), {"is_alive": lambda _self: True})()]
        service.config_data = normalize_config({})

        with patch("backend.services.bot_service.ADBClient") as client:
            with self.assertRaisesRegex(ValueError, "dừng bot"):
                service.test_tap(500, 500)

        client.assert_not_called()

    def test_adb_scan_discards_result_when_config_changes_concurrently(self) -> None:
        service = BotService.__new__(BotService)
        service.lock = threading.RLock()
        service.config_data = normalize_config({})
        service.config_revision = 4
        service.bot_threads = []
        service.adb_ready = True
        service.status = "ADB đã kết nối."
        service.log_queue = queue.Queue()

        def scan_then_concurrent_save(scan_config: dict[str, object], _log: object) -> None:
            scan_config["adb"]["path"] = "scanned-adb.exe"  # type: ignore[index]
            scan_config["adb"]["device"] = "scanned-device"  # type: ignore[index]
            with service.lock:
                replacement = normalize_config({})
                replacement["adb"]["path"] = "new-config-adb.exe"
                replacement["adb"]["device"] = "new-config-device"
                service.config_data = replacement
                service.config_revision += 1

        with patch("backend.services.bot_service.scan_adb_connection", side_effect=scan_then_concurrent_save):
            with patch("backend.services.bot_service.save_config") as save:
                with self.assertRaisesRegex(RuntimeError, "Cấu hình đã thay đổi"):
                    service.scan_adb()

        self.assertFalse(service.adb_ready)
        self.assertEqual(service.config_data["adb"]["path"], "new-config-adb.exe")
        self.assertEqual(service.config_data["adb"]["device"], "new-config-device")
        self.assertEqual(service.status, "Cấu hình đã thay đổi. Quét ADB lại.")
        save.assert_not_called()

    def test_save_config_data_keeps_runtime_state_when_disk_write_fails(self) -> None:
        service = BotService()
        original_config = service.get_config()
        original_revision = service.config_revision
        original_status = service.status
        service.adb_ready = True
        replacement = copy.deepcopy(original_config)
        replacement["farm"]["gold_min"] = int(original_config["farm"]["gold_min"]) + 1

        with patch("backend.services.bot_service.save_config", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                service.save_config_data(replacement)

        self.assertEqual(service.get_config(), original_config)
        self.assertEqual(service.config_revision, original_revision)
        self.assertTrue(service.adb_ready)
        self.assertEqual(service.status, original_status)

    def test_save_points_keeps_runtime_state_when_disk_write_fails(self) -> None:
        service = BotService()
        original_config = service.get_config()
        original_revision = service.config_revision
        original_status = service.status
        service.adb_ready = True

        with patch("backend.services.bot_service.save_config", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                service.save_points(
                    "zone_trenbenphai",
                    [[10, 10], [200, 10], [10, 200]],
                )

        self.assertEqual(service.get_config(), original_config)
        self.assertEqual(service.config_revision, original_revision)
        self.assertTrue(service.adb_ready)
        self.assertEqual(service.status, original_status)

    def test_adb_scan_keeps_config_when_result_cannot_be_persisted(self) -> None:
        service = BotService()
        original_config = service.get_config()
        original_revision = service.config_revision
        service.adb_ready = True
        service.status = "ADB đã kết nối."

        def successful_scan(candidate: dict[str, object], _log: object) -> None:
            candidate["adb"]["path"] = "scanned-adb.exe"  # type: ignore[index]
            candidate["adb"]["device"] = "scanned-device"  # type: ignore[index]

        with (
            patch("backend.services.bot_service.scan_adb_connection", side_effect=successful_scan),
            patch("backend.services.bot_service.save_config", side_effect=OSError("disk full")),
        ):
            with self.assertRaisesRegex(RuntimeError, "Không thể lưu kết quả quét ADB"):
                service.scan_adb()

        self.assertEqual(service.get_config(), original_config)
        self.assertEqual(service.config_revision, original_revision)
        self.assertFalse(service.adb_ready)
        self.assertEqual(service.status, "Không thể lưu kết quả quét ADB. Hãy quét lại.")

    def test_load_config_recovers_corrupt_primary_from_backup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            first = normalize_config({})
            first["farm"]["gold_min"] = 901_001
            second = copy.deepcopy(first)
            second["farm"]["gold_min"] = 902_002

            save_config(first, path)
            save_config(second, path)
            path.write_text('{"farm": ', encoding="utf-8")

            recovered = load_config(path)

            self.assertEqual(recovered["farm"]["gold_min"], 901_001)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["farm"]["gold_min"], 901_001)
            self.assertTrue(path.with_name("config.json.bak").exists())

    def test_load_config_recovers_when_atomic_primary_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            config = normalize_config({})
            config["farm"]["gold_min"] = 903_003
            save_config(config, path)
            path.unlink()

            recovered = load_config(path)

            self.assertEqual(recovered["farm"]["gold_min"], 903_003)
            self.assertTrue(path.exists())

    def test_normalize_config_replaces_user_managed_combo_collection(self) -> None:
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["combos"].pop("Valkyrie")

        normalized = normalize_config(config)

        self.assertNotIn("Valkyrie", normalized["combos"])
        self.assertEqual(normalize_config(normalized), normalized)

    def test_normalize_config_restores_legacy_king_role_to_hero(self) -> None:
        config = copy.deepcopy(DEFAULT_CONFIG)
        config["slot_detection"]["kinds"] = [
            "king" if kind == "hero" else kind
            for kind in config["slot_detection"]["kinds"]
        ]
        config["manual_army"]["counts"].pop("hero", None)
        config["manual_army"]["counts"]["king"] = 3
        config["coords"]["slots"]["king"] = config["coords"]["slots"].pop("hero")
        for step in config["deploy"]["sequence"]:
            if step.get("slot") == "hero":
                step["slot"] = "king"
        for combo in config["combos"].values():
            for step in combo["deploy"]["sequence"]:
                if step.get("slot") == "hero":
                    step["slot"] = "king"

        normalized = normalize_config(config)

        self.assertIn("hero", normalized["slot_detection"]["kinds"])
        self.assertNotIn("king", normalized["slot_detection"]["kinds"])
        self.assertEqual(normalized["manual_army"]["counts"]["hero"], 3)
        self.assertNotIn("king", normalized["manual_army"]["counts"])
        self.assertIn("hero", normalized["coords"]["slots"])
        self.assertNotIn("king", normalized["coords"]["slots"])
        self.assertNotIn("king", [step["slot"] for step in normalized["deploy"]["sequence"]])
        for combo in normalized["combos"].values():
            self.assertNotIn("king", [step["slot"] for step in combo["deploy"]["sequence"]])

    def test_start_bot_rolls_back_when_adb_disappears_after_scan(self) -> None:
        service = BotService()
        service.config_data = normalize_config({})
        service.config_data["deploy"]["deploy_zones"]["trenbenphai"] = [
            [0, 0],
            [10, 0],
            [0, 10],
        ]
        service.adb_ready = True
        service.status = "ADB đã kết nối."

        with patch("backend.services.bot_service.save_config"), patch(
            "backend.services.bot_service.start_farm_threads",
            side_effect=ADBError("Khong tim thay adb.exe"),
        ):
            with self.assertRaisesRegex(RuntimeError, "quét ADB lại"):
                service.start_bot()

        self.assertFalse(service.adb_ready)
        self.assertFalse(service.pause_event.is_set())
        self.assertTrue(service.stop_event.is_set())
        self.assertEqual(service.bot_threads, [])
        self.assertEqual(service.active_devices, [])
        self.assertEqual(service.stats_by_device, {})
        self.assertEqual(service.status, "Kết nối ADB thất bại khi khởi động. Hãy quét lại.")

    def test_start_route_returns_503_for_runtime_start_failure(self) -> None:
        with patch.object(
            bot_router.bot_service,
            "start_bot",
            side_effect=RuntimeError("Không thể khởi động bot"),
        ):
            with self.assertRaises(HTTPException) as raised:
                bot_router.start_bot()

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("Không thể khởi động bot", raised.exception.detail)

    def test_config_writing_routes_return_503_for_os_errors(self) -> None:
        cases = (
            (
                config_router.bot_service,
                "save_config_data",
                lambda: config_router.update_config(ConfigPayload(config={})),
            ),
            (
                coordinates_router.bot_service,
                "save_points",
                lambda: coordinates_router.save_points(
                    SavePointsPayload(target="zone_trenbenphai", points=[(0, 0), (10, 0), (0, 10)])
                ),
            ),
            (bot_router.bot_service, "start_bot", bot_router.start_bot),
        )

        for service, method, call_route in cases:
            with self.subTest(method=method):
                with patch.object(service, method, side_effect=OSError("disk full")):
                    with self.assertRaises(HTTPException) as raised:
                        call_route()

                self.assertEqual(raised.exception.status_code, 503)
                self.assertIn("Không thể lưu cấu hình", raised.exception.detail)

    def test_home_stats_preserve_builder_and_unknown_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stats_path = Path(directory) / "device.json"
            stats_path.write_text(
                json.dumps(
                    {
                        "current_session": {"builder_elixir": 131_000, "future_metric": 7},
                        "total": {"builder_elixir": 131_000, "future_metric": 99},
                    }
                ),
                encoding="utf-8",
            )
            bot = FarmBot.__new__(FarmBot)
            bot.stats_path = stats_path
            bot.base_total_stats = bot._load_total_stats()
            bot.stats = {key: 0 for key in bot.STAT_KEYS}
            bot.session_started_at = "test-session"
            bot.stats_callback = lambda _payload: None
            bot.log = lambda _message: None

            bot._publish_stats()

            saved = json.loads(stats_path.read_text(encoding="utf-8"))
            self.assertEqual(saved["total"]["builder_elixir"], 131_000)
            self.assertEqual(saved["total"]["future_metric"], 99)
            self.assertEqual(saved["current_session"]["future_metric"], 7)

    def test_atomic_stats_write_preserves_old_file_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stats_path = Path(directory) / "device.json"
            stats_path.write_text('{"total":{"attacks":9}}', encoding="utf-8")

            with patch("stats_store.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(OSError, "replace failed"):
                    atomic_write_json(stats_path, {"total": {"attacks": 10}})

            self.assertEqual(
                json.loads(stats_path.read_text(encoding="utf-8")),
                {"total": {"attacks": 9}},
            )
            self.assertEqual(list(Path(directory).glob(".device.json.*.tmp")), [])

    def test_runtime_preflight_stops_when_active_slot_has_no_input(self) -> None:
        bot = self._bare_bot()
        bot.active_combo = "Broken"
        bot.active_deploy = {
            "sequence": [{"slot": "custom_new", "count": "all", "max_taps": 10}],
        }
        bot.config["slot_detection"] = {"enabled": True}
        bot.slot_detector = type(
            "Detector",
            (),
            {"has_usable_template": lambda _self, _kind: False},
        )()

        self.assertFalse(bot._slot_inputs_ready_or_stop())
        self.assertTrue(bot.stop_event.is_set())
        self.assertTrue(any("custom_new" in message for message in bot.log_messages))

    def test_slot_detector_ignores_corrupt_template_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = normalize_config({})
            config["slot_detection"]["template_dir"] = directory
            config["slot_detection"]["kinds"] = ["custom"]
            template_dir = Path(directory) / "custom"
            template_dir.mkdir(parents=True)
            (template_dir / "broken.png").write_bytes(b"not-an-image")
            detector = SlotDetector(config)

            self.assertFalse(detector.has_usable_template("custom"))
            Image.new("RGB", (40, 40), "white").save(template_dir / "valid.png")
            self.assertTrue(detector.has_usable_template("custom"))

    def test_slot_template_mutations_are_blocked_while_bot_is_running(self) -> None:
        service = BotService()

        with (
            patch.object(service, "_bot_running_locked", return_value=True),
            patch.object(SlotDetector, "save_template_from_base64") as save_template,
            patch.object(SlotDetector, "delete_template") as delete_template,
        ):
            with self.assertRaisesRegex(ValueError, "dừng bot"):
                service.save_slot_template("dragon", "unused", 100, 100)
            with self.assertRaisesRegex(ValueError, "dừng bot"):
                service.delete_slot_template("dragon", "sample.png")

        save_template.assert_not_called()
        delete_template.assert_not_called()

    def test_slot_template_mutations_clear_detector_cache(self) -> None:
        service = BotService()

        SlotDetector._template_cache["stale-save"] = object()
        with (
            patch.object(
                SlotDetector,
                "save_template_from_base64",
                return_value=Path("saved.png"),
            ),
            patch.object(SlotDetector, "template_summary", return_value=[]),
        ):
            service.save_slot_template("dragon", "unused", 100, 100)
        self.assertEqual(SlotDetector._template_cache, {})

        SlotDetector._template_cache["stale-delete"] = object()
        with (
            patch.object(
                SlotDetector,
                "delete_template",
                return_value=Path("deleted.png"),
            ),
            patch.object(SlotDetector, "template_summary", return_value=[]),
        ):
            service.delete_slot_template("dragon", "deleted.png")
        self.assertEqual(SlotDetector._template_cache, {})

    def test_rename_slot_kind_moves_templates_and_all_config_references(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = normalize_config({})
            config["slot_detection"]["template_dir"] = directory
            config["slot_detection"]["kinds"].append("spvalkyrie")
            config["slot_detection"]["count_max_by_kind"]["spvalkyrie"] = 8
            config["slot_detection"]["count_corrections"]["spvalkyrie"] = {"7": 6}
            config["manual_army"]["counts"]["spvalkyrie"] = 6
            config["coords"]["slots"]["spvalkyrie"] = [170, 810]
            config["deploy"]["sequence"] = [
                {"slot": "spvalkyrie", "count": "all", "max_taps": 8, "delay": 0.1}
            ]
            config["combos"]["Custom"] = {
                "deploy": {
                    "sequence": [
                        {"slot": "spvalkyrie", "count": "all", "max_taps": 8, "delay": 0.1}
                    ]
                }
            }
            old_directory = Path(directory) / "spvalkyrie"
            old_directory.mkdir()
            (old_directory / "sample.png").write_bytes(b"template")
            service = BotService()
            service.config_data = config

            with patch("backend.services.bot_service.save_config"):
                updated = service.rename_slot_kind("spvalkyrie", "super_valkyrie")

            self.assertFalse(old_directory.exists())
            self.assertTrue((Path(directory) / "super_valkyrie" / "sample.png").exists())
            self.assertIn("super_valkyrie", updated["slot_detection"]["kinds"])
            self.assertNotIn("spvalkyrie", updated["slot_detection"]["kinds"])
            self.assertEqual(updated["slot_detection"]["count_max_by_kind"]["super_valkyrie"], 8)
            self.assertEqual(updated["slot_detection"]["count_corrections"]["super_valkyrie"], {"7": 6})
            self.assertNotIn("spvalkyrie", updated["slot_detection"]["count_corrections"])
            self.assertEqual(updated["manual_army"]["counts"]["super_valkyrie"], 6)
            self.assertEqual(updated["coords"]["slots"]["super_valkyrie"], [170, 810])
            self.assertEqual(updated["deploy"]["sequence"][0]["slot"], "super_valkyrie")
            self.assertEqual(
                updated["combos"]["Custom"]["deploy"]["sequence"][0]["slot"],
                "super_valkyrie",
            )

    def test_rename_slot_kind_rejects_reserved_hero_role(self) -> None:
        service = BotService()
        original = service.get_config()

        with self.assertRaisesRegex(ValueError, "hero.*hệ thống"):
            service.rename_slot_kind("hero", "king")

        self.assertEqual(service.get_config(), original)

    def test_backend_rejects_config_without_reserved_hero_role(self) -> None:
        service = BotService()
        config = service.get_config()
        config["slot_detection"]["kinds"] = [
            kind for kind in config["slot_detection"]["kinds"] if kind != "hero"
        ]

        with self.assertRaisesRegex(ValueError, "role hệ thống 'hero'"):
            service.save_config_data(config)

    def test_reserved_hero_role_uses_one_manual_count_per_detected_slot(self) -> None:
        bot = self._bare_bot()
        bot.manual_slot_counts = {"hero": 3}
        remaining = {"hero": 3}

        counts = [bot._manual_detection_count("hero", remaining) for _ in range(4)]

        self.assertEqual(counts, [1, 1, 1, 0])
        self.assertEqual(remaining["hero"], 0)

    def test_reserved_hero_role_activates_every_detected_hero(self) -> None:
        bot = self._bare_bot()
        bot.config["attack_timing"] = {
            "use_default": True,
            "activate_hero_skill": True,
            "hero_skill_min_ms": 0,
            "hero_skill_max_ms": 0,
            "hero_search_delay_seconds": 0,
        }
        bot.active_deploy = {
            "sequence": [{"slot": "hero", "count": "all", "max_taps": 4}],
        }
        bot.runtime_slots = {
            "hero": [
                {"center": [500, 810]},
                {"center": [620, 810]},
                {"center": [740, 810]},
            ]
        }
        bot.deployed_hero_centers = [[500, 810], [620, 810], [740, 810]]
        taps: list[list[int]] = []
        bot._active_time = lambda: 1.0
        bot._pause_gate = lambda: None
        bot._sleep = lambda _seconds: None
        bot._optimized_action_pause = lambda: None
        bot._tap = lambda point: taps.append(list(point))

        bot._activate_post_deploy_slots(0.0)

        self.assertEqual(taps, [[500, 810], [620, 810], [740, 810]])

    def test_manual_hero_deploy_skips_when_detected_icons_are_insufficient(self) -> None:
        bot = self._bare_bot()
        bot.config["manual_army"] = {"enabled": True}
        bot.manual_slot_counts = {"hero": 3}
        bot.active_deploy = {
            "strict_slot_counts": True,
            "sequence": [{"slot": "hero", "count": "all", "max_taps": 4}],
        }
        bot.runtime_slots = {"hero": [{"center": [500, 810], "count": 1}]}
        bot._deploy_points = lambda: [[100, 100]]
        bot._pause_gate = lambda: None
        taps: list[list[int]] = []
        bot._tap = lambda point: taps.append(list(point))

        result = bot._deploy_troops()

        self.assertFalse(result["deployed"])
        self.assertEqual(result["reason"], "unknown_counts")
        self.assertEqual(taps, [])
        self.assertEqual(bot.deployed_hero_centers, [])

    def test_hero_skill_only_activates_heroes_deployed_by_sequence_limit(self) -> None:
        bot = self._bare_bot()
        bot.config["manual_army"] = {"enabled": True}
        bot.config["attack_timing"] = {
            "activate_hero_skill": True,
            "hero_skill_min_ms": 0,
            "hero_skill_max_ms": 0,
            "hero_search_delay_seconds": 0,
        }
        bot.manual_slot_counts = {"hero": 3}
        bot.active_deploy = {
            "strict_slot_counts": True,
            "slot_check_every": 0,
            "sequence": [{"slot": "hero", "count": 1, "max_taps": 1, "delay": 0}],
        }
        bot.runtime_slots = {
            "hero": [
                {"center": [500, 810], "count": 1},
                {"center": [620, 810], "count": 1},
                {"center": [740, 810], "count": 1},
            ]
        }
        bot._deploy_points = lambda: [[100, 100]]
        bot._pause_gate = lambda: None
        bot._sleep = lambda _seconds: None
        bot._optimized_action_pause = lambda: None
        bot._active_time = lambda: 1.0
        taps: list[list[int]] = []
        bot._tap = lambda point: taps.append(list(point))

        result = bot._deploy_troops()
        bot._activate_post_deploy_slots(0.0)

        self.assertTrue(result["deployed"])
        self.assertEqual(bot.deployed_hero_centers, [[500, 810]])
        self.assertEqual(taps, [[500, 810], [100, 100], [500, 810]])

    def test_reserved_hero_skill_can_be_disabled_independently(self) -> None:
        bot = self._bare_bot()
        bot.config["attack_timing"] = {
            "use_default": False,
            "activate_hero_skill": False,
            "hero_skill_min_ms": 0,
            "hero_skill_max_ms": 0,
        }
        bot.active_deploy = {
            "sequence": [{"slot": "hero", "count": "all", "max_taps": 4}],
        }
        bot.runtime_slots = {"hero": [{"center": [500, 810]}]}
        taps: list[list[int]] = []
        bot._tap = lambda point: taps.append(list(point))

        bot._activate_post_deploy_slots(0.0)

        self.assertEqual(taps, [])

    def test_rename_slot_kind_rolls_back_template_directory_when_save_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            config = normalize_config({})
            config["slot_detection"]["template_dir"] = directory
            config["slot_detection"]["kinds"].append("spvalkyrie")
            config["coords"]["slots"]["spvalkyrie"] = [170, 810]
            old_directory = Path(directory) / "spvalkyrie"
            old_directory.mkdir()
            (old_directory / "sample.png").write_bytes(b"template")
            service = BotService()
            service.config_data = config

            with patch("backend.services.bot_service.save_config", side_effect=OSError("disk full")):
                with self.assertRaisesRegex(OSError, "disk full"):
                    service.rename_slot_kind("spvalkyrie", "super_valkyrie")

            self.assertTrue((old_directory / "sample.png").exists())
            self.assertFalse((Path(directory) / "super_valkyrie").exists())
            self.assertIn("spvalkyrie", service.config_data["slot_detection"]["kinds"])

    def test_attack_threshold_zero_is_ignored_in_any_mode(self) -> None:
        bot = self._bare_bot()
        bot.config["farm"] = {
            "gold_min": 0,
            "elixir_min": 900_000,
            "total_min": 1_700_000,
            "threshold_mode": "any",
        }

        self.assertFalse(bot._should_attack({"gold": 1, "elixir": 1}))
        self.assertTrue(bot._should_attack({"gold": 1, "elixir": 900_000}))

    def test_attack_threshold_all_mode_only_checks_enabled_thresholds(self) -> None:
        bot = self._bare_bot()
        bot.config["farm"] = {
            "gold_min": 500_000,
            "elixir_min": 0,
            "total_min": 0,
            "threshold_mode": "all",
        }

        self.assertFalse(bot._should_attack({"gold": 499_999, "elixir": 2_000_000}))
        self.assertTrue(bot._should_attack({"gold": 500_000, "elixir": 0}))

    def test_backend_rejects_main_village_without_active_threshold(self) -> None:
        service = BotService.__new__(BotService)
        config = normalize_config(
            {
                "farm": {
                    "village": "main",
                    "gold_min": 0,
                    "elixir_min": 0,
                    "total_min": 0,
                    "threshold_mode": "any",
                }
            }
        )

        with self.assertRaisesRegex(ValueError, "ít nhất một ngưỡng"):
            service._validate_config(config)

        config["farm"]["threshold_mode"] = "total"
        config["farm"]["gold_min"] = 900_000
        with self.assertRaisesRegex(ValueError, r"Tổng vàng \+ dầu"):
            service._validate_config(config)

    def test_low_loot_surrender_requires_valid_consecutive_frames(self) -> None:
        bot = self._bare_bot()
        bot.config["farm"] = {"loot_gold_max": 5_000_000, "loot_elixir_max": 5_000_000}
        bot.config["surrender"] = {
            "by_time": False,
            "by_destruction": False,
            "when_low_loot": True,
            "total_remaining_less_than": 200_000,
        }

        self.assertEqual(bot._loot_total({"gold": -1, "elixir": 100_000}), -1)
        self.assertEqual(bot._update_low_loot_confirmations({"gold": -1, "elixir": -1}, 0), 0)
        self.assertEqual(bot._update_low_loot_confirmations({"gold": 80_000, "elixir": 90_000}, 0), 1)
        self.assertEqual(bot._update_low_loot_confirmations({"gold": 70_000, "elixir": 80_000}, 1), 2)
        self.assertEqual(bot._update_low_loot_confirmations({"gold": 300_000, "elixir": 100_000}, 2), 0)

        self.assertEqual(bot._surrender_reason(10, 10, {"gold": 80_000, "elixir": 90_000}, 50, 50, 1), "")
        self.assertIn(
            "remaining loot",
            bot._surrender_reason(10, 10, {"gold": 70_000, "elixir": 80_000}, 50, 50, 2),
        )
        self.assertEqual(bot._surrender_reason(10, 10, {"gold": -1, "elixir": 80_000}, 50, 50, 2), "")

    def test_backend_rejects_unsafe_home_timing_and_damage_values(self) -> None:
        service = BotService.__new__(BotService)
        cases = (
            (("surrender", "time_min_seconds"), -1, "Thời gian đầu hàng"),
            (("surrender", "destruction_max_percent"), 101, "% phá hủy"),
            (("surrender", "max_battle_seconds"), 176, "1 đến 175"),
            (("farm", "gold_min"), -1, "Ngưỡng tài nguyên"),
            (("timing", "loop_sleep"), 0, "loop_sleep"),
        )

        for path, value, message in cases:
            with self.subTest(path=path, value=value):
                config = normalize_config({})
                config[path[0]][path[1]] = value
                with self.assertRaisesRegex(ValueError, message):
                    service._validate_config(config)

    def test_backend_rejects_zero_builder_polling_and_required_delays(self) -> None:
        service = BotService.__new__(BotService)
        for key in ("screen_poll_seconds", "after_attack_seconds", "after_find_now_seconds"):
            with self.subTest(key=key):
                config = normalize_config({})
                config["builder_base"]["timing"][key] = 0
                with self.assertRaisesRegex(ValueError, key):
                    service._validate_config(config)

    def test_backend_rejects_unsafe_builder_wall_confirmation_settings(self) -> None:
        service = BotService.__new__(BotService)
        cases = (
            ("confirmation_read_attempts", 2, "ít nhất 3 lần"),
            ("confirmation_min_agree", 1, "mẫu đồng thuận"),
            ("confirmation_read_delay", -1, "delay đọc hộp xác nhận"),
            ("spend_verify_tolerance_percent", -1, "tolerance chi tiêu phần trăm"),
            ("spend_verify_tolerance_absolute", -1, "tolerance chi tiêu tuyệt đối"),
        )
        for key, value, message in cases:
            with self.subTest(key=key):
                config = normalize_config({})
                config["builder_base"]["wall_upgrade"][key] = value
                with self.assertRaisesRegex(ValueError, message):
                    service._validate_config(config)

    def test_backend_requires_two_wall_consensus_reads(self) -> None:
        service = BotService.__new__(BotService)
        cases = (
            (("wall_upgrade", "resource_read_attempts"), "Nâng tường: số lần đọc tài nguyên"),
            (("builder_base", "wall_upgrade", "resource_read_attempts"), "Làng đêm: số lần đọc tài nguyên"),
            (("builder_base", "wall_upgrade", "cost_read_attempts"), "Làng đêm: số lần đọc giá"),
        )

        for path, message in cases:
            with self.subTest(path=path):
                config = normalize_config({})
                target = config
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = 1
                with self.assertRaisesRegex(ValueError, message):
                    service._validate_config(config)

    def test_config_payload_uses_nested_validation_models(self) -> None:
        with self.assertRaises(ValidationError):
            ConfigPayload(config={"surrender": {"max_battle_seconds": 176}})
        with self.assertRaises(ValidationError):
            ConfigPayload(config={"builder_base": {"timing": {"screen_poll_seconds": 0}}})

    def test_config_payload_rejects_invalid_game_recovery_counters(self) -> None:
        for key in ("max_consecutive_cycle_errors", "attack_missing_retries", "max_home_restart_failures"):
            with self.subTest(key=key):
                with self.assertRaises(ValidationError):
                    ConfigPayload(config={"game": {key: -1}})

    def test_backend_requires_positive_enabled_schedule_times(self) -> None:
        service = BotService.__new__(BotService)

        periodic = normalize_config({})
        periodic["game"].update(
            {
                "periodic_restart_game": True,
                "periodic_restart_min_seconds": 0,
                "periodic_restart_max_seconds": 0,
            }
        )
        with self.assertRaisesRegex(ValueError, "restart định kỳ"):
            service._validate_config(periodic)

        auto_stop = normalize_config({})
        auto_stop["game"].update({"auto_stop": True, "auto_restart_after_seconds": 0})
        with self.assertRaisesRegex(ValueError, "tự động dừng"):
            service._validate_config(auto_stop)

    def test_backend_requires_positive_game_recovery_counters(self) -> None:
        service = BotService.__new__(BotService)
        for key in ("max_consecutive_cycle_errors", "attack_missing_retries", "max_home_restart_failures"):
            with self.subTest(key=key):
                config = normalize_config({})
                config["game"][key] = -1
                with self.assertRaisesRegex(ValueError, key):
                    service._validate_config(config)

    def test_initial_damage_outlier_requires_confirmation(self) -> None:
        bot = self._bare_bot()
        pending = {"value": -1, "reads": 0}

        best, pending = bot._filter_damage_reading(91, -1, pending, 40, 3)
        self.assertEqual(best, -1)
        self.assertEqual(pending["value"], 91)

        best, pending = bot._filter_damage_reading(90, best, pending, 40, 3)
        self.assertEqual(best, 90)
        self.assertEqual(pending, {"value": -1, "reads": 0})

    def test_inconsistent_damage_outliers_do_not_confirm_each_other(self) -> None:
        bot = self._bare_bot()
        pending = {"value": -1, "reads": 0}
        best = -1

        for raw_damage in (91, 50, 99):
            best, pending = bot._filter_damage_reading(raw_damage, best, pending, 40, 3)

        self.assertEqual(best, -1)
        self.assertEqual(pending, {"value": 99, "reads": 1})

    def test_stable_number_rejects_three_disagreeing_ocr_samples(self) -> None:
        bot = self._bare_bot()

        self.assertEqual(bot._stable_number([500_000, 800_000, 5_000_000]), -1)

    def test_stable_number_accepts_two_close_samples(self) -> None:
        bot = self._bare_bot()

        self.assertEqual(
            bot._stable_number(
                [5_000_000, 5_001_000, -1],
                tolerance_percent=0.05,
                tolerance_absolute=1_000,
            ),
            5_001_000,
        )

    def test_result_loot_requires_consensus_and_rejects_values_over_cap(self) -> None:
        bot = self._bare_bot()
        bot.config.update(
            {
                "game": {"resource_stats": True},
                "ocr": {
                    "result_stats": {
                        "read_attempts": 3,
                        "read_delay_seconds": 0,
                        "gold_max": 10_000_000,
                        "elixir_max": 10_000_000,
                    }
                },
            }
        )
        readings = {
            b"first": {"gold": 98_000_000, "elixir": 700_000},
            b"second": {"gold": 98_000_000, "elixir": 700_000},
            b"third": {"gold": 98_000_000, "elixir": 701_000},
        }
        frames = iter((b"second", b"third"))
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: next(frames)})()
        bot.vision = type(
            "Vision",
            (),
            {
                "available": True,
                "read_result_loot": lambda _self, png: readings[png],
            },
        )()
        bot._sleep = lambda _seconds: None
        bot.stats = {"gold_seen": 10, "elixir_seen": 20}
        published: list[bool] = []
        bot._publish_stats = lambda: published.append(True)

        bot._record_result_loot(b"first")

        self.assertEqual(bot.stats["gold_seen"], 10)
        self.assertEqual(bot.stats["elixir_seen"], 700_020)
        self.assertEqual(published, [True])
        self.assertTrue(any("vượt cap" in message for message in bot.log_messages))

    def test_backend_rejects_unsafe_result_stat_limits(self) -> None:
        service = BotService.__new__(BotService)
        config = normalize_config({})
        config["ocr"]["result_stats"]["read_attempts"] = 1

        with self.assertRaisesRegex(ValueError, "số lần đọc"):
            service._validate_config(config)

    def test_home_wall_upgrade_cancels_mismatched_confirmation(self) -> None:
        bot = self._bare_bot()
        bot.config["wall_upgrade"] = {
            "use_add10": False,
            "add1_rounds": 1,
            "dry_run": False,
            "coords": {
                "builder_icon": [10, 10],
                "upgrade_more_button": [20, 20],
                "add1_button": [30, 30],
                "add10_button": [31, 31],
                "remove_button": [40, 40],
                "upgrade_gold_button": [50, 50],
                "upgrade_elixir_button": [60, 60],
                "confirm_okay_button": [70, 70],
                "confirm_cancel_button": [80, 80],
            },
        }
        bot.adb = _ScreenshotADB(b"confirmation")
        bot.vision = _WallVision(
            {"is_wall_upgrade": True, "currency": "gold", "cost": 5_000_000}
        )
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: 0
        close_calls: list[bool] = []
        bot._close_wall_popup = lambda: close_calls.append(True)
        bot._wall_upgrade_budget = lambda: ("gold", 1_000_000, "", {"gold": 6_000_000, "elixir": 0})
        bot._find_wall_row = lambda _settings: [100, 100]
        result = bot._upgrade_walls()

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "cost_over_budget")
        self.assertEqual(bot.adb.taps.count((40, 40)), 1)
        self.assertIn((80, 80), bot.adb.taps)
        self.assertNotIn((70, 70), bot.adb.taps)
        self.assertEqual(close_calls, [True])

    def test_home_wall_dry_run_opens_confirmation_then_cancels(self) -> None:
        bot = self._bare_bot()
        bot.config["wall_upgrade"] = {
            "use_add10": False,
            "add1_rounds": 2,
            "dry_run": True,
            "dry_run_retry_attacks": 6,
            "coords": {
                "builder_icon": [10, 10],
                "upgrade_more_button": [20, 20],
                "add1_button": [30, 30],
                "add10_button": [31, 31],
                "remove_button": [40, 40],
                "upgrade_gold_button": [50, 50],
                "upgrade_elixir_button": [60, 60],
                "confirm_okay_button": [70, 70],
                "confirm_cancel_button": [80, 80],
            },
        }
        bot.adb = _ScreenshotADB(b"confirmation")
        bot.vision = _WallVision(
            {"is_wall_upgrade": True, "currency": "gold", "cost": 800_000}
        )
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: 0
        close_calls: list[bool] = []
        bot._close_wall_popup = lambda: close_calls.append(True)
        bot._wall_upgrade_budget = lambda: ("gold", 1_000_000, "", {"gold": 6_000_000, "elixir": 0})
        bot._find_wall_row = lambda _settings: [100, 100]

        result = bot._upgrade_walls()

        self.assertTrue(result["success"])
        self.assertEqual(bot.adb.taps.count((30, 30)), 2)
        self.assertIn((50, 50), bot.adb.taps)
        self.assertIn((80, 80), bot.adb.taps)
        self.assertNotIn((70, 70), bot.adb.taps)
        self.assertEqual(close_calls, [True])
        self.assertEqual(bot.attacks_since_wall_upgrade, -6)

    def test_home_wall_rolls_back_one_wall_until_cost_fits_budget(self) -> None:
        bot = self._bare_bot()
        bot.config["wall_upgrade"] = {
            "use_add10": False,
            "add1_rounds": 3,
            "dry_run": True,
            "coords": {
                "builder_icon": [10, 10],
                "upgrade_more_button": [20, 20],
                "add1_button": [30, 30],
                "add10_button": [31, 31],
                "remove_button": [40, 40],
                "upgrade_gold_button": [50, 50],
                "upgrade_elixir_button": [60, 60],
                "confirm_okay_button": [70, 70],
                "confirm_cancel_button": [80, 80],
            },
        }
        bot.adb = _ScreenshotADB(b"confirmation")
        bot.vision = _WallVision(
            [
                *[
                    {"is_wall_upgrade": True, "currency": "gold", "cost": 12_000_000}
                    for _ in range(3)
                ],
                *[
                    {"is_wall_upgrade": True, "currency": "gold", "cost": 8_000_000}
                    for _ in range(3)
                ],
            ]
        )
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: 0
        bot._close_wall_popup = lambda: None
        bot._wall_upgrade_budget = lambda: (
            "gold",
            9_400_000,
            "",
            {"gold": 10_000_000, "elixir": 0},
        )
        bot._find_wall_row = lambda _settings: [100, 100]

        result = bot._upgrade_walls()

        self.assertTrue(result["success"])
        self.assertEqual(bot.adb.taps.count((30, 30)), 3)
        self.assertEqual(bot.adb.taps.count((40, 40)), 1)
        self.assertEqual(bot.adb.taps.count((50, 50)), 2)
        self.assertEqual(bot.adb.taps.count((80, 80)), 2)
        self.assertNotIn((70, 70), bot.adb.taps)

    def test_home_wall_add10_rolls_back_one_batch(self) -> None:
        bot = self._bare_bot()
        bot.config["wall_upgrade"] = {
            "use_add10": True,
            "max_add_rounds": 1,
            "dry_run": True,
            "coords": {
                "builder_icon": [10, 10],
                "upgrade_more_button": [20, 20],
                "add1_button": [30, 30],
                "add10_button": [31, 31],
                "remove_button": [40, 40],
                "upgrade_gold_button": [50, 50],
                "upgrade_elixir_button": [60, 60],
                "confirm_okay_button": [70, 70],
                "confirm_cancel_button": [80, 80],
            },
        }
        bot.adb = _ScreenshotADB(b"confirmation")
        bot.vision = _WallVision(
            [
                *[
                    {"is_wall_upgrade": True, "currency": "gold", "cost": 30_000_000}
                    for _ in range(3)
                ],
                *[
                    {"is_wall_upgrade": True, "currency": "gold", "cost": 8_000_000}
                    for _ in range(3)
                ],
            ]
        )
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: 0
        bot._close_wall_popup = lambda: None
        bot._wall_upgrade_budget = lambda: (
            "gold",
            9_400_000,
            "",
            {"gold": 10_000_000, "elixir": 0},
        )
        bot._find_wall_row = lambda _settings: [100, 100]

        result = bot._upgrade_walls()

        self.assertTrue(result["success"])
        self.assertEqual(bot.adb.taps.count((31, 31)), 1)
        self.assertEqual(bot.adb.taps.count((40, 40)), 10)
        self.assertEqual(bot.adb.taps.count((50, 50)), 2)
        self.assertNotIn((70, 70), bot.adb.taps)

    def test_home_wall_confirmation_requires_two_agreeing_samples(self) -> None:
        bot = self._bare_bot()
        bot.config["wall_upgrade"] = {
            "use_add10": False,
            "add1_rounds": 1,
            "dry_run": False,
            "coords": {
                "builder_icon": [10, 10],
                "upgrade_more_button": [20, 20],
                "add1_button": [30, 30],
                "add10_button": [31, 31],
                "upgrade_gold_button": [50, 50],
                "upgrade_elixir_button": [60, 60],
                "confirm_okay_button": [70, 70],
                "confirm_cancel_button": [80, 80],
            },
        }
        bot.adb = _ScreenshotADB(b"confirmation")
        bot.vision = _WallVision(
            [
                {"is_wall_upgrade": True, "currency": "gold", "cost": 700_000},
                {"is_wall_upgrade": True, "currency": "gold", "cost": 800_000},
                {"is_wall_upgrade": True, "currency": "gold", "cost": 900_000},
            ]
        )
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: 0
        close_calls: list[bool] = []
        bot._close_wall_popup = lambda: close_calls.append(True)
        bot._wall_upgrade_budget = lambda: ("gold", 1_000_000, "", {"gold": 6_000_000, "elixir": 0})
        bot._find_wall_row = lambda _settings: [100, 100]

        result = bot._upgrade_walls()

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "confirmation_read_failed")
        self.assertIn((80, 80), bot.adb.taps)
        self.assertNotIn((70, 70), bot.adb.taps)
        self.assertEqual(close_calls, [True])

    def test_home_wall_stops_when_actual_spend_exceeds_confirmed_cost(self) -> None:
        bot = self._bare_bot()
        bot.config["wall_upgrade"] = {
            "use_add10": False,
            "add1_rounds": 1,
            "dry_run": False,
            "coords": {
                "builder_icon": [10, 10],
                "upgrade_more_button": [20, 20],
                "add1_button": [30, 30],
                "add10_button": [31, 31],
                "upgrade_gold_button": [50, 50],
                "upgrade_elixir_button": [60, 60],
                "confirm_okay_button": [70, 70],
                "confirm_cancel_button": [80, 80],
            },
        }
        bot.adb = _ScreenshotADB(b"confirmation")
        bot.vision = _WallVision(
            {"is_wall_upgrade": True, "currency": "gold", "cost": 800_000}
        )
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: 0
        close_calls: list[bool] = []
        bot._close_wall_popup = lambda: close_calls.append(True)
        bot._wall_upgrade_budget = lambda: ("gold", 1_000_000, "", {"gold": 6_000_000, "elixir": 0})
        bot._find_wall_row = lambda _settings: [100, 100]
        bot._read_home_resources_stable = lambda _settings: {"gold": 1_000_000, "elixir": 0}

        result = bot._upgrade_walls()

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "unsafe_spend_detected")
        self.assertTrue(bot.stop_event.is_set())
        self.assertIn((70, 70), bot.adb.taps)
        self.assertTrue(any("[WALL][CRITICAL]" in message for message in bot.log_messages))
        self.assertEqual(close_calls, [True])

    def test_home_wall_stops_when_post_upgrade_resources_cannot_be_verified(self) -> None:
        bot = self._bare_bot()
        bot.config["wall_upgrade"] = {
            "use_add10": False,
            "add1_rounds": 1,
            "dry_run": False,
            "coords": {
                "builder_icon": [10, 10],
                "upgrade_more_button": [20, 20],
                "add1_button": [30, 30],
                "add10_button": [31, 31],
                "upgrade_gold_button": [50, 50],
                "upgrade_elixir_button": [60, 60],
                "confirm_okay_button": [70, 70],
                "confirm_cancel_button": [80, 80],
            },
        }
        bot.adb = _ScreenshotADB(b"confirmation")
        bot.vision = _WallVision(
            {"is_wall_upgrade": True, "currency": "gold", "cost": 800_000}
        )
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: 0
        bot._close_wall_popup = lambda: None
        bot._wall_upgrade_budget = lambda: ("gold", 1_000_000, "", {"gold": 6_000_000, "elixir": 0})
        bot._find_wall_row = lambda _settings: [100, 100]
        bot._read_home_resources_stable = Mock(return_value=None)
        lifecycle: list[tuple[str, str]] = []
        bot._notify_lifecycle = lambda event, detail="": lifecycle.append((event, detail))

        result = bot._upgrade_walls()

        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "upgrade_verify_failed")
        self.assertEqual(bot._read_home_resources_stable.call_count, 2)
        self.assertTrue(bot.stop_event.is_set())
        self.assertEqual(lifecycle[0][0], "error")

    def test_home_wall_row_uses_safe_horizontal_tap_position(self) -> None:
        bot = self._bare_bot()
        bot.adb = _ScreenshotADB(b"builder-list")
        bot.vision = type(
            "WallRowVision",
            (),
            {"find_wall_row": lambda _self, _png, _region: [617, 558]},
        )()
        bot._pause_gate = lambda: 0

        position = bot._find_wall_row(
            {
                "search_region": [560, 100, 500, 600],
                "wall_row_tap_x": 780,
                "max_wall_search_scrolls": 0,
            }
        )

        self.assertEqual(position, [780, 558])

    def test_wall_row_detection_requires_price_on_same_line(self) -> None:
        vision = Vision.__new__(Vision)
        vision.available = True
        vision.image_from_png = lambda _png: type("Image", (), {"crop": lambda _self, _box: object()})()
        data = {
            "text": ["Wall", "Wall-x283", "@2", "000", "000"],
            "left": [310, 57, 314, 355, 412],
            "top": [300, 458, 460, 461, 461],
            "width": [50, 103, 30, 35, 35],
            "height": [18, 17, 14, 14, 14],
            "conf": [95, 69, 80, 90, 90],
        }
        vision.pytesseract = type(
            "Tesseract",
            (),
            {
                "Output": type("Output", (), {"DICT": "dict"}),
                "image_to_data": lambda _self, _crop, output_type: data,
            },
        )()

        position = vision.find_wall_row(b"builder-list", [560, 100, 500, 600])

        self.assertEqual(position, [668, 566])

    def test_home_wall_confirmation_accepts_body_when_stylized_title_is_garbled(self) -> None:
        vision = Vision.__new__(Vision)
        vision.config = {"wall_upgrade": {}}
        vision.image_from_png = lambda _png: object()
        vision.read_text = lambda _image, _region, psm=7: (
            "spiradeiwgas do you really want to upgrade the selected "
            "walls for 8400000 elixir?"
        )
        vision.read_number = lambda _image, _region: 8_400_000

        confirmation = vision.read_wall_confirmation(b"modal")

        self.assertTrue(confirmation["is_wall_upgrade"])
        self.assertEqual(confirmation["currency"], "elixir")
        self.assertEqual(confirmation["cost"], 8_400_000)
        self.assertTrue(confirmation["sources_match"])

    def test_home_wall_confirmation_rejects_cost_source_mismatch(self) -> None:
        vision = Vision.__new__(Vision)
        vision.config = {"wall_upgrade": {}}
        vision.image_from_png = lambda _png: object()
        vision.read_text = lambda _image, _region, psm=7: (
            "upgrade walls do you really want to upgrade the selected walls for 800000 gold?"
        )
        vision.read_number = lambda _image, _region: 5_000_000

        confirmation = vision.read_wall_confirmation(b"modal")

        self.assertTrue(confirmation["is_wall_upgrade"])
        self.assertEqual(confirmation["text_cost"], 800_000)
        self.assertEqual(confirmation["region_cost"], 5_000_000)
        self.assertFalse(confirmation["sources_match"])
        self.assertEqual(confirmation["cost"], -1)

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

    def test_old_home_wall_cost_options_are_removed_without_touching_builder(self) -> None:
        config = normalize_config(
            {
                "wall_upgrade": {
                    "cost_read_attempts": 7,
                    "coords": {"confirm_upgrade_button": [100, 100]},
                },
                "builder_base": {"wall_upgrade": {"cost_read_attempts": 5}},
            }
        )
        self.assertNotIn("cost_read_attempts", config["wall_upgrade"])
        self.assertNotIn("confirm_upgrade_button", config["wall_upgrade"]["coords"])
        self.assertEqual(config["builder_base"]["wall_upgrade"]["cost_read_attempts"], 5)

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
