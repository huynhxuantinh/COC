from __future__ import annotations

import os
import random
import shutil
import subprocess
import time
from pathlib import Path


class ADBError(RuntimeError):
    pass


COMMON_ADB_PATHS = [
    Path("tools") / "platform-tools" / "adb.exe",
    Path(r"C:\platform-tools\adb.exe"),
    Path(r"C:\Android\platform-tools\adb.exe"),
    Path(r"C:\Program Files\Android\platform-tools\adb.exe"),
    Path(r"C:\Program Files (x86)\Android\platform-tools\adb.exe"),
    Path(r"C:\Program Files\LDPlayer\LDPlayer9\adb.exe"),
    Path(r"C:\Program Files\ldplayer9box\adb.exe"),
    Path(r"C:\Program Files\ldplayer9box\dnadb.exe"),
    Path(r"C:\LDPlayer\LDPlayer9\adb.exe"),
    Path(r"C:\Program Files\dnplayerext2\adb.exe"),
    Path(r"C:\Program Files (x86)\LDPlayer\LDPlayer9\adb.exe"),
    Path(r"C:\Program Files (x86)\ldplayer9box\adb.exe"),
    Path(r"C:\Program Files (x86)\ldplayer9box\dnadb.exe"),
    Path(r"D:\LDPlayer\LDPlayer9\adb.exe"),
    Path(r"D:\LDPlayer\LDPlayer9\dnadb.exe"),
    Path(r"E:\LDPlayer\LDPlayer9\adb.exe"),
    Path(r"E:\LDPlayer\LDPlayer9\dnadb.exe"),
]

COMMON_DEVICES = [
    "127.0.0.1:5555",
    "emulator-5554",
    "127.0.0.1:5554",
    "127.0.0.1:5556",
    "127.0.0.1:5557",
    "127.0.0.1:5559",
]


def discover_adb_paths(configured_path: str = "", deep_scan: bool = False) -> list[str]:
    candidates: list[Path] = []
    if configured_path:
        candidates.append(Path(configured_path))
    candidates.extend(COMMON_ADB_PATHS)

    path_adb = shutil.which("adb")
    if path_adb:
        candidates.append(Path(path_adb))

    if deep_scan:
        candidates.extend(_deep_discover_adb_paths())

    found: list[str] = []
    seen: set[str] = set()
    for item in candidates:
        try:
            resolved = str(item.resolve())
        except OSError:
            resolved = str(item)
        if resolved not in seen and item.exists():
            seen.add(resolved)
            found.append(resolved)
    return found


def _deep_discover_adb_paths() -> list[Path]:
    candidates: list[Path] = []
    for root in [
        Path(r"C:\LDPlayer"),
        Path(r"D:\LDPlayer"),
        Path(r"E:\LDPlayer"),
        Path(r"C:\Program Files"),
        Path(r"C:\Program Files (x86)"),
        Path.home() / "AppData" / "Local",
    ]:
        if not root.exists():
            continue
        try:
            for child in root.iterdir():
                name = child.name.lower()
                if child.is_dir() and any(token in name for token in ("ldplayer", "android", "platform")):
                    candidates.extend(child.rglob("adb.exe"))
                    candidates.extend(child.rglob("dnadb.exe"))
        except OSError:
            continue
    return candidates


class ADBClient:
    PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

    def __init__(self, adb_path: str, device: str, log=None, resolution: tuple[int, int] = (1600, 900)) -> None:
        self.device = device
        self.log = log or (lambda message: None)
        self.max_x = max(0, int(resolution[0]) - 1)
        self.max_y = max(0, int(resolution[1]) - 1)
        self.adb_path = self._resolve_adb(adb_path)

    def _resolve_adb(self, configured_path: str) -> str:
        paths = discover_adb_paths(configured_path)
        if paths:
            return paths[0]
        raise ADBError("Khong tim thay adb.exe. Cai Android platform-tools hoac dien adb.path.")

    def _run(self, args: list[str], timeout: float = 15) -> subprocess.CompletedProcess:
        try:
            return subprocess.run(
                [self.adb_path, *args],
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ADBError(f"ADB timeout: {' '.join(args)}") from exc
        except OSError as exc:
            raise ADBError(f"Khong chay duoc ADB: {exc}") from exc

    def connect(self) -> None:
        self.log(f"[ADB] connect {self.device}")
        self._run(["connect", self.device], timeout=10)
        result = self._run(["devices"], timeout=10)
        text = result.stdout.decode("utf-8", errors="ignore")
        state = self._device_state(text)
        if state != "device":
            raise ADBError("Khong ket noi duoc LDPlayer. Kiem tra ADB debugging/port.")
        self.log("[ADB] Connected.")

    def _device_state(self, adb_devices_text: str) -> str:
        for line in adb_devices_text.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and parts[0] == self.device:
                return parts[1]
        return ""

    def shell(self, *parts: str, timeout: float = 15) -> str:
        result = self._run(["-s", self.device, "shell", *parts], timeout=timeout)
        return result.stdout.decode("utf-8", errors="ignore")

    def start_app(self, package: str) -> None:
        self.shell("monkey", "-p", package, "1", timeout=15)

    def force_stop_app(self, package: str) -> None:
        self.shell("am", "force-stop", package, timeout=15)

    def restart_app(self, package: str, wait_seconds: float = 12) -> None:
        self.force_stop_app(package)
        time.sleep(1)
        self.start_app(package)
        time.sleep(wait_seconds)

    def tap(self, x: int, y: int, jitter: int = 4) -> None:
        if jitter > 0:
            x += random.randint(-jitter, jitter)
            y += random.randint(-jitter, jitter)
        x = min(self.max_x, max(0, x))
        y = min(self.max_y, max(0, y))
        self.shell("input", "tap", str(x), str(y), timeout=8)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration_ms: int = 300) -> None:
        self.shell(
            "input",
            "swipe",
            str(x1),
            str(y1),
            str(x2),
            str(y2),
            str(duration_ms),
            timeout=8,
        )

    def screencap_png(self) -> bytes:
        last_error = "Khong chup duoc man hinh tu ADB."
        for attempt in range(1, 4):
            try:
                result = self._run(
                    ["-s", self.device, "exec-out", "screencap", "-p"],
                    timeout=8,
                )
                return self._normalize_png(result.stdout)
            except ADBError as exc:
                last_error = str(exc)
                self.log(f"[ADB] Screencap fail ({attempt}/3): {last_error}")
                time.sleep(0.5)
        raise ADBError(last_error)

    def _normalize_png(self, data: bytes) -> bytes:
        if not data:
            raise ADBError("Khong chup duoc man hinh tu ADB.")
        if data.startswith(self.PNG_SIGNATURE):
            return data

        marker = b"__ADB_ORIGINAL_CRLF__"
        fixed = data.replace(b"\r\r\n", marker).replace(b"\r\n", b"\n").replace(marker, b"\r\n")
        if fixed.startswith(self.PNG_SIGNATURE):
            return fixed

        preview = data[:16].hex(" ")
        fixed_preview = fixed[:16].hex(" ")
        self.log(
            "[ADB] Screencap khong phai PNG hop le sau khi sua CRLF. "
            f"Header={preview} | Fixed={fixed_preview}. "
            "Se retry; neu lap lai, thu doi adb.exe/LDPlayer ADB hoac dung exec-out khac."
        )
        raise ADBError(
            "Screencap PNG hong sau normalize CRLF. "
            f"Header={preview}; fixed={fixed_preview}. "
            "Goi y: doi adb.exe/LDPlayer ADB hoac kiem tra ket noi gia lap."
        )

    def sleep_after_action(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


def env_adb_hint() -> str:
    return os.environ.get("ANDROID_HOME", "")
