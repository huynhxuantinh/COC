from __future__ import annotations

import random
import threading
import unittest
from io import BytesIO
from unittest.mock import patch

from PIL import Image, ImageDraw

from backend.services.bot_service import BotService
from bot import FarmBot
from builder_bot import BuilderBaseBot
from builder_vision import BuilderBaseVision, BuilderScreen
from config_manager import normalize_config
from bot_runtime import start_farm_threads


class BuilderBaseTests(unittest.TestCase):
    def test_old_config_receives_builder_defaults(self) -> None:
        config = normalize_config({"farm": {"village": "builder"}})
        builder = config["builder_base"]
        self.assertEqual(builder["entry"]["zoom_out_count"], 4)
        self.assertEqual(builder["entry"]["return_zoom_out_count"], 4)
        self.assertEqual(builder["entry"]["return_camera_swipes"][0][:4], [950, 350, 650, 650])
        self.assertEqual(builder["entry"]["stage2_to_stage1_swipes"][0][:4], [1200, 700, 400, 200])
        self.assertEqual(builder["deploy"]["stage1_zoom_out_count"], 3)
        self.assertEqual(builder["deploy"]["stage2_zoom_out_count"], 3)
        self.assertEqual(builder["deploy"]["slot_scan_attempts"], 3)
        self.assertEqual(builder["deploy"]["hero_deploy_attempts"], 2)
        self.assertEqual(builder["deploy"]["troop_skill_delay_seconds"], 3.0)
        self.assertEqual(builder["deploy"]["hero_first_skill_delay_seconds"], 28.0)
        self.assertTrue(builder["elixir_cart"]["enabled"])
        self.assertEqual(builder["elixir_cart"]["collect_every_n_attacks"], 1)
        self.assertEqual(builder["elixir_cart"]["icon_search_attempts"], 3)
        self.assertEqual(builder["timing"]["state_confirmations"], 2)
        self.assertEqual(builder["timing"]["damage_unknown_restart_seconds"], 20)
        self.assertEqual(builder["timing"]["damage_stall_seconds"], 20)
        self.assertEqual(builder["timing"]["unknown_state_restart_seconds"], 12)
        self.assertEqual(builder["timing"]["max_watchdog_restarts"], 3)
        self.assertEqual(builder["coords"]["star_bonus_okay"], [800, 700])
        self.assertEqual(builder["coords"]["start_dialog_close"], [1360, 165])
        self.assertFalse(builder["wall_upgrade"]["enabled"])
        self.assertEqual(builder["wall_upgrade"]["trigger_percent"], 90)
        self.assertEqual(builder["wall_upgrade"]["retry_backoff_attacks"], 10)
        self.assertEqual(builder["wall_upgrade"]["max_wall_search_scrolls"], 9)

    def test_each_stage_zooms_before_slot_scan(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "deploy": {
                "stage1_zoom_out_count": 2,
                "stage2_zoom_out_count": 4,
                "camera_settle_seconds": 0,
            }
        }
        calls: list[int] = []
        bot._zoom_out = calls.append
        bot._sleep = lambda _seconds: None
        bot.log = lambda _message: None
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: b"fresh-frame"})()

        self.assertEqual(bot._prepare_stage_camera(1), b"fresh-frame")
        self.assertEqual(bot._prepare_stage_camera(2), b"fresh-frame")
        self.assertEqual(calls, [2, 4])

    def test_builder_wall_payment_uses_larger_available_budget(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        settings = {"reserve_gold": 200000, "reserve_elixir": 200000}
        payment = bot._select_builder_wall_payment(
            settings,
            {"gold": 1200000, "elixir": 1800000},
            {"gold": 800000, "elixir": 800000},
        )
        self.assertEqual(payment, ("elixir", 800000))

    def test_builder_wall_payment_rejects_cost_over_reserve_budget(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        payment = bot._select_builder_wall_payment(
            {"reserve_gold": 500000, "reserve_elixir": 500000},
            {"gold": 1000000, "elixir": 1000000},
            {"gold": 800000, "elixir": 800000},
        )
        self.assertIsNone(payment)

    def test_builder_wall_due_uses_percent_or_attack_interval(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "wall_upgrade": {
                "enabled": True,
                "run_after_attacks_enabled": True,
                "run_every_n_attacks": 10,
                "trigger_percent": 90,
                "gold_capacity": 6000000,
                "elixir_capacity": 6000000,
            }
        }
        bot.attacks_since_wall_upgrade = 3
        bot._read_builder_resources_stable = lambda _settings: {"gold": 5500000, "elixir": 1000000}
        self.assertTrue(bot._builder_wall_upgrade_due())
        bot.attacks_since_wall_upgrade = 10
        bot._read_builder_resources_stable = lambda _settings: {"gold": 1, "elixir": 1}
        self.assertTrue(bot._builder_wall_upgrade_due())
        bot.attacks_since_wall_upgrade = -1
        self.assertFalse(bot._builder_wall_upgrade_due())

    def test_builder_wall_confirmation_requires_currency_and_cost(self) -> None:
        vision = BuilderBaseVision(normalize_config({}))
        vision.vision.image_from_png = lambda _png: object()
        vision._compact_text = lambda _image, _region: "upgradewallsbuilderelixir"
        vision.vision.read_number = lambda _image, _region: 800000
        confirmation = vision.read_wall_confirmation(b"dialog")
        self.assertTrue(confirmation["is_wall_upgrade"])
        self.assertEqual(confirmation["currency"], "elixir")
        self.assertEqual(confirmation["cost"], 800000)

    def test_result_screen_falls_back_to_green_return_home_button(self) -> None:
        vision = BuilderBaseVision(normalize_config({}))
        image = Image.new("RGB", (1600, 900), "black")
        ImageDraw.Draw(image).rectangle((680, 710, 925, 815), fill=(80, 190, 25))
        output = BytesIO()
        image.save(output, format="PNG")

        with (
            patch.object(vision, "find_template_center", return_value=None),
            patch.object(vision, "_compact_text", return_value="totaldamage"),
        ):
            self.assertTrue(vision.is_result_screen(output.getvalue()))

    def test_green_troop_health_bars_are_not_a_result_screen(self) -> None:
        vision = BuilderBaseVision(normalize_config({}))
        image = Image.new("RGB", (1600, 900), "black")
        ImageDraw.Draw(image).rectangle((680, 710, 925, 815), fill=(80, 190, 25))
        output = BytesIO()
        image.save(output, format="PNG")

        with (
            patch.object(vision, "find_template_center", return_value=None),
            patch.object(vision, "_compact_text", return_value=""),
        ):
            self.assertFalse(vision.is_result_screen(output.getvalue()))

    def test_result_panel_is_not_misclassified_as_star_bonus(self) -> None:
        vision = BuilderBaseVision(normalize_config({}))
        image = Image.new("RGB", (1600, 900), (20, 40, 110))
        ImageDraw.Draw(image).rectangle((650, 640, 950, 770), fill=(80, 190, 25))
        output = BytesIO()
        image.save(output, format="PNG")

        with patch.object(vision, "_compact_text", return_value="totaldamage"):
            self.assertFalse(vision.is_star_bonus_popup(output.getvalue()))

    def test_hero_deploy_confirmation_uses_health_bar(self) -> None:
        vision = BuilderBaseVision(normalize_config({}))
        blank = Image.new("RGB", (1600, 900), "black")
        before = BytesIO()
        blank.save(before, format="PNG")
        self.assertFalse(vision.hero_deployed(before.getvalue(), [162, 812]))

        deployed = blank.copy()
        ImageDraw.Draw(deployed).rectangle((112, 736, 212, 747), fill=(45, 220, 35))
        after = BytesIO()
        deployed.save(after, format="PNG")
        self.assertTrue(vision.hero_deployed(after.getvalue(), [162, 812]))

    def test_find_now_availability_distinguishes_green_from_cooldown(self) -> None:
        vision = BuilderBaseVision(normalize_config({}))
        cooldown = Image.new("RGB", (1600, 900), (60, 60, 60))
        cooldown_png = BytesIO()
        cooldown.save(cooldown_png, format="PNG")
        self.assertFalse(vision.find_now_available(cooldown_png.getvalue()))

        available = cooldown.copy()
        ImageDraw.Draw(available).rectangle((1025, 520, 1355, 660), fill=(80, 190, 35))
        available_png = BytesIO()
        available.save(available_png, format="PNG")
        self.assertTrue(vision.find_now_available(available_png.getvalue()))

    def test_battle_frame_difference_detects_frozen_image(self) -> None:
        vision = BuilderBaseVision(normalize_config({}))
        first = Image.new("RGB", (1600, 900), "black")
        first_png = BytesIO()
        first.save(first_png, format="PNG")

        changed = first.copy()
        ImageDraw.Draw(changed).rectangle((400, 200, 900, 500), fill="white")
        changed_png = BytesIO()
        changed.save(changed_png, format="PNG")

        self.assertEqual(vision.battle_frame_difference(first_png.getvalue(), first_png.getvalue()), 0)
        self.assertGreater(vision.battle_frame_difference(first_png.getvalue(), changed_png.getvalue()), 1.5)

    def test_cooldown_dialog_is_closed_then_retried_later(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "coords": {"start_dialog_close": [1360, 165]},
            "timing": {"attack_cooldown_retry_seconds": 15.0},
        }
        taps: list[tuple[list[int], int]] = []
        sleeps: list[float] = []
        bot.log = lambda _message: None
        bot._tap = lambda point, jitter=0: taps.append((point, jitter))
        bot._sleep = sleeps.append

        bot._close_start_dialog(cooldown=True)

        self.assertEqual(taps, [([1360, 165], 0)])
        self.assertEqual(sleeps, [1.0, 15.0])

    def test_monitor_exits_when_interrupted_dialog_reappears(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {"timing": {"battle_timeout_seconds": 30, "state_confirmations": 1}}
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        bot.log = lambda _message: None
        bot._pause_gate = lambda: None
        bot._sleep = lambda _seconds: None
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: b"start-dialog"})()
        bot.vision = type(
            "Vision",
            (),
            {
                "classify": lambda _self, _png: BuilderScreen.START_DIALOG,
                "find_now_available": lambda _self, _png: False,
            },
        )()
        closed: list[bool] = []
        failures: list[str] = []
        bot._close_start_dialog = lambda cooldown: closed.append(cooldown)
        bot._record_state_failure = lambda reason, _png=b"", restart=True: failures.append(reason)

        state, _png = bot._monitor_stage(1, initial_state=BuilderScreen.BATTLE)

        self.assertEqual(state, BuilderScreen.INTERRUPTED)
        self.assertEqual(closed, [True])
        self.assertEqual(failures, ["builder-stage1-interrupted"])

    def test_damage_unknown_watchdog_restarts_stage(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "timing": {
                "battle_timeout_seconds": 190,
                "state_confirmations": 1,
                "screen_poll_seconds": 0,
                "damage_unknown_restart_seconds": 20,
                "damage_stall_seconds": 0,
                "unknown_state_restart_seconds": 0,
            }
        }
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        bot.log = lambda _message: None
        bot._pause_gate = lambda: None
        bot._sleep = lambda _seconds: None
        bot._maybe_activate_hero = lambda _png: None
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: b"battle"})()
        bot.vision = type(
            "Vision",
            (),
            {
                "classify": lambda _self, _png: BuilderScreen.BATTLE,
                "read_damage": lambda _self, _png: -1,
                "battle_frame_difference": lambda _self, _previous, _current: 10.0,
            },
        )()
        restarted: list[str] = []
        bot._restart_stage_watchdog = lambda reason, _png, _message: restarted.append(reason)
        clock = iter(range(0, 1000, 10))

        with patch("builder_bot.time.time", side_effect=lambda: next(clock)):
            state, _png = bot._monitor_stage(1, initial_state=BuilderScreen.BATTLE)

        self.assertEqual(state, BuilderScreen.RESTARTED)
        self.assertEqual(restarted, ["builder-stage1-damage-unknown"])

    def test_unknown_screen_watchdog_restarts_stage(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "timing": {
                "battle_timeout_seconds": 190,
                "state_confirmations": 1,
                "screen_poll_seconds": 0,
                "damage_unknown_restart_seconds": 0,
                "damage_stall_seconds": 0,
                "unknown_state_restart_seconds": 12,
            }
        }
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        bot.log = lambda _message: None
        bot._pause_gate = lambda: None
        bot._sleep = lambda _seconds: None
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: b"unknown"})()
        bot.vision = type("Vision", (), {"classify": lambda _self, _png: BuilderScreen.UNKNOWN})()
        restarted: list[str] = []
        bot._restart_stage_watchdog = lambda reason, _png, _message: restarted.append(reason)
        clock = iter(range(0, 1000, 10))

        with patch("builder_bot.time.time", side_effect=lambda: next(clock)):
            state, _png = bot._monitor_stage(2, initial_state=BuilderScreen.BATTLE)

        self.assertEqual(state, BuilderScreen.RESTARTED)
        self.assertEqual(restarted, ["builder-stage2-unknown-screen"])

    def test_frozen_damage_and_frame_restart_stage(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "timing": {
                "battle_timeout_seconds": 190,
                "state_confirmations": 1,
                "screen_poll_seconds": 0,
                "damage_unknown_restart_seconds": 0,
                "damage_stall_seconds": 20,
                "unknown_state_restart_seconds": 0,
                "frozen_frame_min_difference": 1.5,
            }
        }
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        bot.log = lambda _message: None
        bot._pause_gate = lambda: None
        bot._sleep = lambda _seconds: None
        bot._maybe_activate_hero = lambda _png: None
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: b"frozen-battle"})()
        bot.vision = type(
            "Vision",
            (),
            {
                "classify": lambda _self, _png: BuilderScreen.BATTLE,
                "read_damage": lambda _self, _png: 25,
                "battle_frame_difference": lambda _self, _previous, _current: 0.0,
            },
        )()
        restarted: list[str] = []
        bot._restart_stage_watchdog = lambda reason, _png, _message: restarted.append(reason)
        clock = iter(range(0, 1000, 10))

        with patch("builder_bot.time.time", side_effect=lambda: next(clock)):
            state, _png = bot._monitor_stage(1, initial_state=BuilderScreen.BATTLE)

        self.assertEqual(state, BuilderScreen.RESTARTED)
        self.assertEqual(restarted, ["builder-stage1-battle-frozen"])

    def test_elixir_cart_only_adds_confirmed_collection(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "elixir_cart": {
                "enabled": True,
                "collect_button": [1175, 760],
                "close_button": [1342, 88],
                "collect_wait_seconds": 0,
            }
        }
        bot.stop_event = threading.Event()
        bot.stats = {"builder_elixir": 0}
        bot.log = lambda _message: None
        bot._sleep = lambda _seconds: None
        published: list[int] = []
        bot._publish_stats = lambda: published.append(bot.stats["builder_elixir"])
        taps: list[tuple[int, int]] = []

        class FakeADB:
            def screencap_png(self) -> bytes:
                return b"after"

            def tap(self, x: int, y: int, jitter: int = 0) -> None:
                taps.append((x, y))

        class FakeVision:
            def is_elixir_cart_popup(self, _png: bytes) -> bool:
                return True

            def read_elixir_cart_reward(self, png: bytes) -> int:
                return 131000 if png == b"before" else -1

        bot.adb = FakeADB()
        bot.vision = FakeVision()
        self.assertTrue(bot._collect_elixir_cart(b"before"))

        self.assertEqual(bot.stats["builder_elixir"], 131000)
        self.assertEqual(published, [131000])
        self.assertEqual(taps, [(1175, 760), (1342, 88)])

    def test_elixir_cart_respects_attack_interval(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {"elixir_cart": {"enabled": True, "collect_every_n_attacks": 5}}
        bot.base_total_stats = {"builder_attacks": 10}
        bot.stats = {"builder_attacks": 4}
        bot._elixir_cart_pending = False
        self.assertFalse(bot._elixir_cart_due())
        bot.stats["builder_attacks"] = 5
        self.assertTrue(bot._elixir_cart_due())
        bot.stats["builder_attacks"] = 6
        self.assertTrue(bot._elixir_cart_due())
        bot._elixir_cart_pending = False
        self.assertFalse(bot._elixir_cart_due())

    def test_star_bonus_popup_is_dismissed_and_verified(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "coords": {"star_bonus_okay": [800, 700]},
            "timing": {"star_bonus_wait_seconds": 0},
        }
        bot.stop_event = threading.Event()
        bot.log = lambda _message: None
        bot._sleep = lambda _seconds: None
        bot._dump_debug = lambda _reason, _png=b"": None
        taps: list[tuple[int, int]] = []

        class FakeADB:
            def screencap_png(self) -> bytes:
                return b"closed"

            def tap(self, x: int, y: int, jitter: int = 0) -> None:
                taps.append((x, y))

        bot.adb = FakeADB()
        bot.vision = type(
            "Vision",
            (),
            {"is_star_bonus_popup": lambda _self, png: png == b"bonus"},
        )()

        self.assertTrue(bot._dismiss_star_bonus(b"bonus"))
        self.assertEqual(taps, [(800, 700)])

    def test_clustered_deploy_points_stay_inside_polygon(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "deploy": {
                "random_points": 64,
                "point_spacing_min_px": 20,
                "point_spacing_max_px": 45,
            }
        }
        polygon = [[200, 200], [700, 200], [700, 600], [200, 600]]
        random.seed(42)
        points = bot._clustered_points(polygon, 9)
        self.assertEqual(len(points), 9)
        self.assertTrue(all(bot._point_in_polygon(point, polygon) for point in points))
        self.assertTrue(all((x - points[0][0]) ** 2 + (y - points[0][1]) ** 2 <= 45**2 * 2 for x, y in points[1:]))

    def test_stage_transition_requires_battle_then_stable_prep(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "timing": {
                "battle_timeout_seconds": 2,
                "screen_poll_seconds": 0,
                "state_confirmations": 2,
            }
        }
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        bot.log = lambda _message: None
        bot._sleep = lambda _seconds: None
        bot._pause_gate = lambda: None
        hero_checks: list[bytes] = []
        bot._maybe_activate_hero = hero_checks.append
        frames = iter([b"initial-prep", b"battle", b"transition-1", b"transition-2"])
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: next(frames)})()
        states = {
            b"initial-prep": BuilderScreen.STAGE_PREP,
            b"battle": BuilderScreen.BATTLE,
            b"transition-1": BuilderScreen.STAGE_PREP,
            b"transition-2": BuilderScreen.STAGE_PREP,
        }
        bot.vision = type(
            "Vision",
            (),
            {
                "classify": lambda _self, png: states[png],
                "read_damage": lambda _self, _png: 100,
            },
        )()

        state, png = bot._monitor_stage(1, initial_state=BuilderScreen.STAGE_PREP)

        self.assertEqual(state, BuilderScreen.STAGE_PREP)
        self.assertEqual(png, b"transition-2")
        self.assertEqual(hero_checks, [b"battle"])

    def test_stage_two_waits_through_false_home_frame_for_result(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "timing": {
                "battle_timeout_seconds": 5,
                "screen_poll_seconds": 0,
                "state_confirmations": 1,
                "result_transition_grace_seconds": 8,
                "damage_unknown_restart_seconds": 0,
                "damage_stall_seconds": 0,
                "unknown_state_restart_seconds": 0,
            }
        }
        bot.stop_event = threading.Event()
        bot.pause_event = threading.Event()
        logs: list[str] = []
        bot.log = logs.append
        bot._pause_gate = lambda: None
        bot._sleep = lambda _seconds: None
        bot._maybe_activate_hero = lambda _png: None
        frames = iter([b"battle", b"false-home", b"result"])
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: next(frames)})()
        states = {
            b"battle": BuilderScreen.BATTLE,
            b"false-home": BuilderScreen.BUILDER_HOME,
            b"result": BuilderScreen.RESULT,
        }
        bot.vision = type(
            "Vision",
            (),
            {
                "classify": lambda _self, png: states[png],
                "read_damage": lambda _self, _png: 12,
            },
        )()

        state, png = bot._monitor_stage(2, initial_state=BuilderScreen.BATTLE)

        self.assertEqual(state, BuilderScreen.RESULT)
        self.assertEqual(png, b"result")
        self.assertIn("[BUILDER] Làng 2: damage=100%.", logs)
        self.assertFalse(any("bị gián đoạn" in message for message in logs))

    def test_stage_two_army_scan_uses_majority_and_survivors_first(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {"deploy": {"slot_scan_attempts": 3, "slot_scan_delay_seconds": 0}}
        bot.stop_event = threading.Event()
        bot._sleep = lambda _seconds: None
        bot.log = lambda _message: None
        hero = [10, 10]
        regular = [[20, 10], [30, 10]]
        reinforcements = [[40, 10], [50, 10]]
        frames = iter([b"frame-2", b"frame-3"])
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: next(frames)})()
        available = {
            b"frame-1": {tuple(hero), tuple(regular[1]), tuple(reinforcements[0])},
            b"frame-2": {tuple(hero), tuple(regular[1]), tuple(reinforcements[0])},
            b"frame-3": {tuple(regular[0]), tuple(reinforcements[1])},
        }
        bot.vision = type(
            "Vision",
            (),
            {"slot_available": lambda _self, png, slot: tuple(slot) in available[png]},
        )()

        has_hero, survivors, reinforcement = bot._scan_stage_army(
            2,
            b"frame-1",
            hero,
            regular,
            reinforcements,
        )

        self.assertTrue(has_hero)
        self.assertEqual(survivors, [regular[1]])
        self.assertEqual(reinforcement, [reinforcements[0]])

    def test_resume_stage_two_prep_instead_of_opening_new_match(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {"coords": {"reinforcement_slots": [[100, 800]]}}
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: b"stage-two-prep"})()
        bot.vision = type(
            "Vision",
            (),
            {
                "classify": lambda _self, _png: BuilderScreen.STAGE_PREP,
                "slot_available": lambda _self, _png, _slot: True,
            },
        )()
        resumed: list[tuple[int, str, bytes, bool]] = []
        bot.log = lambda _message: None
        bot._run_match_from_stage = lambda stage, state, png, deploy_current: resumed.append(
            (stage, state, png, deploy_current)
        )

        self.assertFalse(bot._ensure_builder_home())
        self.assertEqual(resumed, [(2, BuilderScreen.STAGE_PREP, b"stage-two-prep", True)])

    def test_stage_two_deploys_survivors_before_reinforcements(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        survivor = [300, 812]
        reinforcement = [1063, 812]
        bot.builder = {
            "coords": {
                "hero_slot": [162, 812],
                "troop_slots": [survivor],
                "reinforcement_slots": [reinforcement],
            },
            "deploy": {
                "stage2_zone": [[100, 100], [300, 100], [200, 300]],
                "troop_delay_seconds": 0,
                "troop_skill_delay_seconds": 0,
            },
        }
        bot.stop_event = threading.Event()
        bot.log = lambda _message: None
        bot._sleep = lambda _seconds: None
        bot._scan_stage_army = lambda *_args: (False, [survivor], [reinforcement])
        bot._clustered_points = lambda _polygon, count: [[150 + index, 150] for index in range(count)]
        deployed: list[list[int]] = []
        bot._deploy_slot = lambda slot, _point: deployed.append(slot)
        bot._run_troop_skill_jobs = lambda _jobs: None

        self.assertTrue(bot._deploy_stage(2, b"prep"))
        self.assertEqual(deployed, [survivor, reinforcement])

    def test_repeated_state_failures_restart_then_stop(self) -> None:
        bot = BuilderBaseBot.__new__(BuilderBaseBot)
        bot.builder = {
            "timing": {
                "restart_after_state_failures": 2,
                "max_state_failures": 3,
            }
        }
        bot.stop_event = threading.Event()
        bot._state_failures = 0
        bot.log = lambda _message: None
        bot._dump_debug = lambda _reason, _png=b"": None
        restarts: list[int] = []
        bot._restart_game = lambda: restarts.append(bot._state_failures)

        bot._record_state_failure("one")
        bot._record_state_failure("two")
        self.assertEqual(restarts, [2])
        self.assertFalse(bot.stop_event.is_set())
        bot._record_state_failure("three")
        self.assertTrue(bot.stop_event.is_set())

    def test_builder_start_requires_both_polygons(self) -> None:
        service = BotService.__new__(BotService)
        config = normalize_config({"farm": {"village": "builder"}})
        with self.assertRaisesRegex(ValueError, "Làng 1, Làng 2"):
            service._validate_start_requirements(config)

        config["builder_base"]["deploy"]["stage1_zone"] = [[0, 0], [10, 0], [0, 10]]
        config["builder_base"]["deploy"]["stage2_zone"] = [[0, 0], [10, 0], [0, 10]]
        service._validate_start_requirements(config)

    def test_runtime_selects_builder_bot_without_touching_main_bot(self) -> None:
        created: list[str] = []

        class FakeBuilderBot:
            def __init__(self, config, log, stop_event, pause_event, stats_callback) -> None:
                created.append(config["adb"]["device"])

            def run(self) -> None:
                return

        config = normalize_config({"farm": {"village": "builder"}, "adb": {"device": "emulator-5554"}})
        with patch("bot_runtime.BuilderBaseBot", FakeBuilderBot):
            threads, devices = start_farm_threads(
                config,
                lambda _message: None,
                threading.Event(),
                threading.Event(),
                lambda _device, _stats: None,
            )
            for thread in threads:
                thread.join(timeout=2)

        self.assertEqual(devices, ["emulator-5554"])
        self.assertEqual(created, ["emulator-5554"])

    def test_main_bot_routes_builder_home_before_attack_flow(self) -> None:
        bot = FarmBot.__new__(FarmBot)
        bot.adb = type("ADB", (), {"screencap_png": lambda _self: b"builder-home"})()
        bot.village_vision = type("VillageVision", (), {"classify": lambda _self, _png: BuilderScreen.BUILDER_HOME})()
        called: list[bytes] = []
        bot._travel_to_main_village = lambda png: called.append(png) or True

        self.assertTrue(bot._ensure_main_village())
        self.assertEqual(called, [b"builder-home"])

    def test_return_to_main_moves_from_builder_stage2_when_boat_is_missing(self) -> None:
        bot = FarmBot.__new__(FarmBot)
        bot.config = {
            "builder_base": {
                "entry": {
                    "return_zoom_out_count": 0,
                    "return_camera_swipes": [],
                    "stage2_to_stage1_swipes": [[1200, 700, 400, 200, 700]],
                    "boat_search_attempts": 2,
                }
            }
        }
        bot.stop_event = threading.Event()
        bot.log = lambda _message: None
        bot._sleep = lambda _seconds: None
        bot._dump_debug_png = lambda _reason, _png: None
        swipes: list[tuple[int, ...]] = []

        class FakeADB:
            tapped = False

            def screencap_png(self) -> bytes:
                return b"frame"

            def swipe(self, *values: int) -> None:
                swipes.append(values)

            def tap(self, _x: int, _y: int, jitter: int = 0) -> None:
                self.tapped = True

        adb = FakeADB()
        bot.adb = adb

        class FakeVision:
            boat_calls = 0

            def classify(self, _png: bytes) -> str:
                return BuilderScreen.MAIN_HOME if adb.tapped else BuilderScreen.BUILDER_HOME

            def find_return_boat(self, _png: bytes):
                self.boat_calls += 1
                return None if self.boat_calls == 1 else (1345, 522, 0.99)

        bot.village_vision = FakeVision()

        self.assertTrue(bot._travel_to_main_village())
        self.assertEqual(swipes, [(1200, 700, 400, 200, 700)])


if __name__ == "__main__":
    unittest.main()
