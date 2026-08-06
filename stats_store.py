from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


STAT_KEYS = (
    "attacks",
    "next",
    "gold_seen",
    "elixir_seen",
    "builder_attacks",
    "builder_gold",
    "builder_elixir",
    "builder_trophies",
    "builder_damage",
)


def load_total_stats(path: Path) -> dict[str, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {key: 0 for key in STAT_KEYS}

    total = data.get("total", {})
    if not isinstance(total, dict):
        total = {}
    return {key: int(total.get(key, 0)) for key in STAT_KEYS}


def merge_existing_stats(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        existing = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        existing = {}
    if not isinstance(existing, dict):
        existing = {}

    merged = {**existing, **payload}
    for section in ("current_session", "total"):
        old_section = existing.get(section, {})
        new_section = payload.get(section, {})
        if not isinstance(old_section, dict):
            old_section = {}
        if not isinstance(new_section, dict):
            new_section = {}
        merged[section] = {**old_section, **new_section}
    return merged


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(payload, file, ensure_ascii=True, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, path)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
