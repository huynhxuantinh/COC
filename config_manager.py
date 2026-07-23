from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


CONFIG_PATH = Path("config.json")


DEFAULT_CONFIG: dict[str, Any] = {
    "adb": {
        "path": "",
        "device": "127.0.0.1:5555",
        "devices": [],
        "package": "com.supercell.clashofclans",
        "connect_on_start": True,
    },
    "runtime": {
        "stats_path": "stats.json",
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
        "restart_wait_seconds": 18,
        "max_consecutive_cycle_errors": 8,
    },
    "farm": {
        "village": "main",
        "combo": "Rồng Điện",
        "deploy_mode": "one_edge",
        "attack_edge": "top",
        "attack_view": "random",
        "threshold_mode": "any",
        "gold_min": 900000,
        "elixir_min": 900000,
        "dark_min": 8000,
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
    },
    "ocr": {
        "enabled": True,
        "tesseract_path": "",
        "regions": {
            "loot_gold": [78, 125, 160, 35],
            "loot_elixir": [78, 175, 160, 35],
            "loot_dark": [78, 220, 140, 35],
            "damage_percent": [1355, 630, 190, 70],
            "next_button": [1325, 575, 250, 130],
            "damage_panel": [1320, 615, 260, 120],
            "home_attack_button": [20, 715, 170, 160],
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
            "titan": [414, 815],
            "siege": [556, 815],
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
        "slot_check_every": 2,
        "sequence": [
            {"slot": "siege", "count": 1, "delay": 0.35},
            {"slot": "dragon", "count": "all", "max_taps": 16, "delay": 0.18},
            {"slot": "balloon", "count": "all", "max_taps": 24, "delay": 0.16},
            {"slot": "titan", "count": "all", "max_taps": 4, "delay": 0.25},
            {"slot": "hero", "count": 1, "delay": 0.25},
        ],
        "spells": [
            {
                "slot": "rage",
                "enabled": True,
                "name": "No 1",
                "max_casts": 3,
                "delay_after_deploy": 4,
                "points": [[807, 281], [958, 371], [1083, 466]],
            },
            {
                "slot": "freeze",
                "enabled": True,
                "name": "Bang",
                "max_casts": 1,
                "delay_after_deploy": 7,
                "points": [[781, 352], [912, 436], [986, 490]],
            },
            {
                "slot": "rage",
                "enabled": True,
                "name": "No 2",
                "max_casts": 2,
                "delay_after_deploy": 10,
                "points": [[742, 405], [952, 555]],
            },
        ],
        "spell_groups": [
            {
                "name": "No/Bang linh hoat",
                "enabled": True,
                "slots": ["rage", "freeze"],
                "max_casts": 6,
                "delay_after_deploy": 4,
                "delay_between_casts": 0.22,
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
        "use_default": True,
        "troop_delay_ms": 150,
        "freeze_random_min_ms": 0,
        "freeze_random_max_ms": 1000,
        "rage_random_min_ms": 2000,
        "rage_random_max_ms": 4000,
        "siege_activation_min_ms": 5000,
        "siege_activation_max_ms": 7000,
        "hero_skill_min_ms": 2000,
        "hero_skill_max_ms": 4000,
        "next_battle_min_ms": 2000,
        "next_battle_max_ms": 5000,
        "adb_delay_seconds": 0.3,
        "hero_search_delay_seconds": 1.5,
        "optimized_mode": False,
    },
}


DEFAULT_CONFIG["combos"] = {
    "Rồng Điện": {
        "deploy": copy.deepcopy(DEFAULT_CONFIG["deploy"]),
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


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
    return merged


def save_config(config: dict[str, Any], path: Path = CONFIG_PATH) -> None:
    path.write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
