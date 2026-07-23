from __future__ import annotations

import copy
import threading
from dataclasses import dataclass
from typing import Any, Callable

from adb_client import ADBClient, ADBError, COMMON_DEVICES, discover_adb_paths
from bot import FarmBot


STAT_KEYS = ("attacks", "next", "gold_seen", "elixir_seen", "dark_seen")


@dataclass(frozen=True)
class ScanADBResult:
    path: str
    device: str
    path_count: int


def safe_device_name(device: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in device)


def configured_devices(config: dict[str, Any]) -> list[str]:
    device = config.get("adb", {}).get("device", "127.0.0.1:5555")
    return [device]


def candidate_devices(config: dict[str, Any]) -> list[str]:
    devices: list[str] = []
    configured_device = config.get("adb", {}).get("device", "")
    if configured_device:
        devices.append(configured_device)
    for device in COMMON_DEVICES:
        if device not in devices:
            devices.append(device)
    return devices


def scan_adb_connection(config: dict[str, Any], log: Callable[[str], None]) -> ScanADBResult:
    adb_config = config.setdefault("adb", {})
    deep_scan = bool(adb_config.get("deep_scan", False))
    paths = discover_adb_paths(adb_config.get("path", ""), deep_scan=deep_scan)
    if not paths:
        log("[ADB] Không tìm thấy adb.exe. Vào Cài đặt để chọn file.")
        raise RuntimeError("Không tìm thấy adb.exe.")

    devices = candidate_devices(config)
    scan_mode = "quét sâu" if deep_scan else "quét nhanh"
    log(f"[ADB] Tìm thấy {len(paths)} path ({scan_mode}). Đang thử kết nối...")
    for path in paths:
        log(f"[ADB] Thử path: {path}")
        for device in devices:
            try:
                client = ADBClient(path, device, log=log)
                client.connect()
                client.screencap_png()
            except ADBError as exc:
                log(f"[ADB] Fail {device}: {exc}")
                continue

            adb_config["path"] = path
            adb_config["device"] = device
            adb_config["devices"] = []
            log(f"[ADB] OK: {path} | {device}")
            return ScanADBResult(path=path, device=device, path_count=len(paths))

    log("[ADB] Có adb.exe nhưng không kết nối được LDPlayer.")
    raise RuntimeError("Kết nối ADB thất bại.")


def start_farm_threads(
    config: dict[str, Any],
    log: Callable[[str], None],
    stop_event: threading.Event,
    pause_event: threading.Event,
    stats_callback: Callable[[str, dict[str, Any]], None],
) -> tuple[list[threading.Thread], list[str]]:
    devices = configured_devices(config)
    threads: list[threading.Thread] = []
    for device in devices:
        bot_config = copy.deepcopy(config)
        bot_config.setdefault("adb", {})["device"] = device
        bot_config.setdefault("runtime", {})["stats_path"] = f"stats/{safe_device_name(device)}.json"
        bot = FarmBot(
            bot_config,
            lambda message, dev=device: log(f"[{dev}] {message}"),
            stop_event,
            pause_event,
            lambda stats, dev=device: stats_callback(dev, stats),
        )
        thread = threading.Thread(target=bot.run, daemon=True, name=f"FarmBot-{device}")
        threads.append(thread)
        thread.start()
    return threads, devices
