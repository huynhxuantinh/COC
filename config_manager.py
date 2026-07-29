from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config.json")


EMPTY_VIEW_ZONES = {
    "trenbenphai": [],
    "trenbentrai": [],
    "duoibenphai": [],
    "duoibentrai": [],
}


DEFAULT_CONFIG: dict[str, Any] = {
    "adb": {
        "path": "",
        "device": "127.0.0.1:5555",
        "devices": [],
        "package": "com.supercell.clashofclans",
        "connect_on_start": True,
        "deep_scan": False,
    },
    "runtime": {
        "stats_path": "stats.json",
    },
    "slot_detection": {
        "enabled": True,
        "template_dir": "img/slots",
        "threshold": 0.72,
        "bar_region": [80, 720, 1220, 180],
        "template_size": [76, 76],
        "kinds": ["dragon", "balloon", "valkyrie", "hero", "rage", "freeze"],
        "cluster_kinds": ["hero"],
        "cluster_padding": 430,
        "count_max_by_kind": {
            "dragon": 16,
            "balloon": 40,
            "valkyrie": 60,
            "rage": 5,
            "freeze": 11,
        },
        "count_corrections": {
            "rage": {"7": 4},
        },
        "strict": False,
    },
    "manual_army": {
        "enabled": False,
        "counts": {
            "dragon": 0,
            "balloon": 0,
            "valkyrie": 0,
            "hero": 0,
            "rage": 0,
            "freeze": 0,
        },
    },
    "game": {
        "resolution": [1600, 900],
        "language": "en",
        "skip_restart_game": True,
        "auto_stop": False,
        "auto_restart_after_seconds": 60,
        "periodic_restart_game": False,
        "periodic_restart_min_seconds": 3600,
        "periodic_restart_max_seconds": 5400,
        "donate_when_farming": False,
        "change_combo_on_start": False,
        "resource_stats": True,
        "restart_if_attack_missing": True,
        "attack_missing_retries": 3,
        "max_home_restart_failures": 3,
        "restart_wait_seconds": 18,
        "max_consecutive_cycle_errors": 8,
        "home_zoom_out_keyevents": 3,
        "ldplayer_index": 0,
    },
    "farm": {
        "village": "main",
        "combo": "Rồng Điện",
        "deploy_mode": "polygon",
        "attack_edge": "top",
        "attack_view": "random",
        "threshold_mode": "any",
        "gold_min": 900000,
        "elixir_min": 900000,
        "total_min": 1700000,
        "max_next": 80,
        "search_delay_seconds": 3.0,
        "ocr_fail_restart_seconds": 30,
    },
    "surrender": {
        "by_time": True,
        "time_min_seconds": 50,
        "time_max_seconds": 80,
        "by_destruction": True,
        "destruction_min_percent": 50,
        "destruction_max_percent": 80,
        "when_low_loot": True,
        "total_remaining_less_than": 200000,
        "never_surrender": False,
        "max_battle_seconds": 175,
        "damage_jump_confirm_percent": 40,
        "damage_jump_max_pending_reads": 3,
        "damage_stall_seconds": 20,
        "damage_unknown_restart_seconds": 20,
    },
    "ocr": {
        "enabled": True,
        "tesseract_path": "",
        "regions": {
            "loot_panel": [78, 123, 145, 86],
            "loot_gold": [78, 123, 145, 40],
            "loot_elixir": [78, 169, 145, 40],
            "result_loot_panel": [612, 370, 212, 124],
            "result_gold": [612, 370, 210, 40],
            "result_elixir": [612, 430, 210, 40],
            "damage_percent": [1495, 645, 89, 51],
            "next_button": [1325, 575, 250, 130],
            "damage_panel": [1320, 615, 260, 120],
            "home_attack_button": [20, 715, 170, 160],
            "home_gold": [1305, 25, 250, 45],
            "home_elixir": [1320, 103, 220, 45],
        },
    },
    "coords": {
        "home_attack": [104, 795],
        "find_match": [275, 666],
        "my_army_attack": [1415, 801],
        "next": [1455, 641],
        "end_battle": [115, 672],
        "end_battle_okay": [974, 580],
        "return_home": [800, 772],
        "slots": {
            "dragon": [172, 815],
            "balloon": [295, 815],
            "valkyrie": [414, 815],
            "hero": [676, 815],
            "rage": [815, 815],
            "freeze": [932, 815],
            "poison": [1064, 815],
        },
    },
    "deploy": {
        "zoom_out_keyevents": 3,
        "camera_swipes": [
            [800, 250, 800, 560, 450],
            [800, 250, 800, 560, 450],
        ],
        "view_camera_swipes": {
            "trenbenphai": [
                [1050, 260, 650, 620, 500],
                [1050, 260, 650, 620, 500],
            ],
            "trenbentrai": [
                [550, 260, 950, 620, 500],
                [550, 260, 950, 620, 500],
            ],
            "duoibenphai": [
                [1050, 640, 650, 280, 500],
                [1050, 640, 650, 280, 500],
            ],
            "duoibentrai": [
                [550, 640, 950, 280, 500],
                [550, 640, 950, 280, 500],
            ],
        },
        "camera_settle_seconds": 0.8,
        "pre_attack_swipes": [],
        "one_edge_points": [
            [820, 135],
            [880, 165],
            [940, 200],
            [1000, 240],
            [1060, 285],
            [1120, 330],
            [1180, 375],
            [1240, 425],
        ],
        "edge_points": {
            "top": [
                [820, 135],
                [880, 165],
                [940, 200],
                [1000, 240],
                [1060, 285],
                [1120, 330],
                [1180, 375],
                [1240, 425],
            ],
            "bottom": [
                [760, 670],
                [820, 640],
                [880, 610],
                [940, 580],
                [1000, 545],
                [1060, 510],
                [1120, 475],
                [1180, 440],
            ],
            "left": [
                [315, 330],
                [380, 365],
                [445, 400],
                [510, 435],
                [575, 470],
                [640, 505],
                [705, 540],
                [770, 575],
            ],
            "right": [
                [1245, 330],
                [1180, 365],
                [1115, 400],
                [1050, 435],
                [985, 470],
                [920, 505],
                [855, 540],
                [790, 575],
            ],
        },
        "view_points": {
            "trenbenphai": [],
            "trenbentrai": [],
            "duoibenphai": [],
            "duoibentrai": [],
        },
        "deploy_zones": {
            "trenbenphai": [],
            "trenbentrai": [],
            "duoibenphai": [],
            "duoibentrai": [],
        },
        "zone_random_points": 48,
        "line_points": [
            [560, 610],
            [650, 640],
            [740, 675],
            [835, 700],
            [930, 675],
            [1020, 640],
            [1080, 610],
        ],
        "four_corner_points": [
            [315, 330],
            [1245, 330],
            [560, 610],
            [1080, 610],
        ],
        "random_area": [260, 170, 1250, 700],
        "scan_slot_counts": True,
        "strict_slot_counts": True,
        "slot_check_every": 8,
        "sequence": [
            {"slot": "dragon", "count": "all", "max_taps": 16, "delay": 0.08},
            {"slot": "balloon", "count": "all", "max_taps": 24, "delay": 0.07},
            {"slot": "hero", "count": "all", "max_taps": 5, "delay": 0.12},
        ],
        "spell_groups": [
            {
                "name": "Nộ/Băng linh hoạt",
                "enabled": True,
                "slots": ["rage", "freeze"],
                "max_casts": 6,
                "delay_after_deploy": 2,
                "delay_between_casts": 0.4,
                "zone": [],
                "zones": copy.deepcopy(EMPTY_VIEW_ZONES),
                "points": [
                    [807, 281],
                    [958, 371],
                    [1083, 466],
                    [781, 352],
                    [912, 436],
                    [952, 555],
                ],
            },
        ],
    },
    "timing": {
        "after_click": 0.25,
        "after_home_attack": 1.5,
        "after_find_match": 1.5,
        "after_my_army_attack": 4.0,
        "after_next": 3.0,
        "after_return_home": 5.0,
        "loop_sleep": 0.2,
        "sleep_jitter_percent": 0.15,
        "sleep_jitter_min_seconds": 0.25,
    },
    "attack_timing": {
        "use_default": False,
        "troop_delay_ms": 80,
        "freeze_random_min_ms": 0,
        "freeze_random_max_ms": 250,
        "rage_random_min_ms": 500,
        "rage_random_max_ms": 1200,
        "spell_min_point_distance_px": 120,
        "hero_skill_min_ms": 2000,
        "hero_skill_max_ms": 4000,
        "next_battle_min_ms": 2000,
        "next_battle_max_ms": 5000,
        "adb_delay_seconds": 0.18,
        "hero_search_delay_seconds": 1.5,
        "optimized_mode": False,
    },
    "wall_upgrade": {
        "enabled": False,
        "run_every_n_attacks": 20,
        "gold_capacity": 6000000,
        "elixir_capacity": 6000000,
        "trigger_percent": 95,
        "pay_with": "auto",
        "reserve_gold": 200000,
        "reserve_elixir": 200000,
        "use_add10": False,
        "max_add_rounds": 10,
        "retry_backoff_attacks": 20,
        "max_wall_search_scrolls": 6,
        "resource_read_attempts": 3,
        "cost_read_attempts": 3,
        "read_attempt_delay": 0.45,
        "search_region": [560, 100, 500, 600],
        "list_scroll_swipe": [820, 650, 820, 220, 500],
        "coords": {
            "builder_icon": [755, 60],
            "upgrade_more_button": [800, 745],
            "add10_button": [630, 749],
            "add1_button": [797, 750],
            "remove_button": [446, 730],
            "upgrade_gold_button": [984, 700],
            "upgrade_elixir_button": [1145, 700],
            "confirm_upgrade_button": [1120, 786],
            "confirm_okay_button": [972, 578],
            "confirm_cancel_button": [622, 578],
        },
    },
}


DEFAULT_CONFIG["combos"] = {
    "Rồng Điện": {
        "deploy": copy.deepcopy(DEFAULT_CONFIG["deploy"]),
    },
}
DEFAULT_CONFIG["combos"]["Valkyrie"] = {
    "deploy": copy.deepcopy(DEFAULT_CONFIG["deploy"]),
}
DEFAULT_CONFIG["combos"]["Valkyrie"]["deploy"]["sequence"] = [
    {"slot": "valkyrie", "count": "all", "max_taps": 60, "delay": 0.06},
    {"slot": "hero", "count": "all", "max_taps": 5, "delay": 0.12},
]
for combo in DEFAULT_CONFIG["combos"].values():
    combo.get("deploy", {}).pop("deploy_zones", None)
    combo.get("deploy", {}).pop("spell_groups", None)


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def migrate_fast_attack_delays(config: dict[str, Any]) -> None:
    def migrate_deploy(deploy: dict[str, Any]) -> None:
        if not isinstance(deploy, dict):
            return
        if deploy.get("slot_check_every") == 2:
            deploy["slot_check_every"] = 8

        sequence_delays = {
            "dragon": (0.18, 0.08),
            "balloon": (0.16, 0.07),
            "hero": (0.25, 0.12),
        }
        for step in deploy.get("sequence", []):
            slot = step.get("slot")
            old_new = sequence_delays.get(slot)
            if old_new and step.get("delay") == old_new[0]:
                step["delay"] = old_new[1]

        for group in deploy.get("spell_groups", []):
            group.setdefault("zone", [])
            if not isinstance(group.get("zones"), dict):
                group["zones"] = copy.deepcopy(EMPTY_VIEW_ZONES)
            else:
                for view in EMPTY_VIEW_ZONES:
                    group["zones"].setdefault(view, [])
            if group.get("delay_after_deploy") == 4:
                group["delay_after_deploy"] = 2
            if group.get("delay_between_casts") in (0.08, 0.22):
                group["delay_between_casts"] = 0.4

    migrate_deploy(config.get("deploy", {}))
    for combo in config.get("combos", {}).values():
        migrate_deploy(combo.get("deploy", {}))

    timing = config.get("attack_timing", {})
    replacements = {
        "troop_delay_ms": (150, 80),
        "freeze_random_max_ms": (1000, 250),
        "rage_random_min_ms": (2000, 500),
        "rage_random_max_ms": (4000, 1200),
        "adb_delay_seconds": (0.3, 0.18),
    }
    for key, (old_value, new_value) in replacements.items():
        if timing.get(key) == old_value:
            timing[key] = new_value


def migrate_global_deploy_zones(config: dict[str, Any]) -> None:
    for combo in config.get("combos", {}).values():
        deploy = combo.get("deploy", {}) if isinstance(combo, dict) else {}
        if isinstance(deploy, dict):
            deploy.pop("deploy_zones", None)
            deploy.pop("spell_groups", None)


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        save_config(DEFAULT_CONFIG, path)
        return copy.deepcopy(DEFAULT_CONFIG)

    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    merged = deep_merge(DEFAULT_CONFIG, data)
    if "combos" not in data:
        merged["combos"] = {
            "Rồng Điện": {
                "deploy": copy.deepcopy(merged["deploy"]),
            },
        }
    migrate_fast_attack_delays(merged)
    migrate_global_deploy_zones(merged)
    return merged


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
