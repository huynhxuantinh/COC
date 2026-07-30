from __future__ import annotations

import copy
import base64
import json
import queue
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

from adb_client import ADBClient
from bot_runtime import STAT_KEYS, scan_adb_connection, start_farm_threads
from config_manager import load_config, save_config
from slot_detector import SlotDetector
from vision import Vision


class BotService:
    def __init__(self) -> None:
        self.config_data = load_config()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.stats_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.bot_threads: list[threading.Thread] = []
        self.active_devices: list[str] = []
        self.stats_by_device: dict[str, dict[str, Any]] = {}
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.adb_ready = False
        self.status = "Chưa quét ADB."
        self.logs: list[dict[str, Any]] = []
        self.next_log_id = 1
        self.lock = threading.RLock()

    def get_config(self) -> dict[str, Any]:
        with self.lock:
            return copy.deepcopy(self.config_data)

    def save_config_data(self, config: dict[str, Any]) -> dict[str, Any]:
        self._validate_config(config)
        with self.lock:
            self.config_data = copy.deepcopy(config)
            save_config(self.config_data)
            self.adb_ready = False
            self.status = "Đã lưu. Quét ADB lại."
        self._log("[INFO] Đã lưu cài đặt.")
        return self.get_config()

    def get_options(self) -> dict[str, Any]:
        with self.lock:
            combos = self.config_data.get("combos", {})
            combo_names = list(combos.keys()) or [self.config_data.get("farm", {}).get("combo", "Rồng Điện")]
        return {
            "combos": combo_names,
            "deploy_modes": [
                {"label": "Thả theo vùng polygon", "value": "polygon"},
            ],
            "attack_edges": [
                {"label": "Trên", "value": "top"},
                {"label": "Dưới", "value": "bottom"},
                {"label": "Trái", "value": "left"},
                {"label": "Phải", "value": "right"},
                {"label": "Ngẫu nhiên", "value": "random"},
                {"label": "Tự động", "value": "auto"},
            ],
            "attack_views": [
                {"label": "Ngẫu nhiên", "value": "random"},
                {"label": "Trên bên phải", "value": "trenbenphai"},
                {"label": "Trên bên trái", "value": "trenbentrai"},
                {"label": "Dưới bên phải", "value": "duoibenphai"},
                {"label": "Dưới bên trái", "value": "duoibentrai"},
                {"label": "Tự động", "value": "auto"},
            ],
        }

    def get_status(self) -> dict[str, Any]:
        self._drain_stats()
        self._drain_logs()
        with self.lock:
            return {
                "status": self.status,
                "adb_ready": self.adb_ready,
                "running": self._bot_running_locked(),
                "paused": self.pause_event.is_set(),
                "active_devices": list(self.active_devices),
            }

    def scan_adb(self) -> dict[str, Any]:
        with self.lock:
            if self._bot_running_locked():
                raise RuntimeError("Dừng bot trước khi quét ADB.")
            self.adb_ready = False
            self.status = "Đang quét ADB..."
        self._log("[ADB] Đang quét adb.exe...")

        try:
            scan_adb_connection(self.config_data, self._log)
        except RuntimeError as exc:
            with self.lock:
                self.status = "Không thấy ADB." if "Không tìm thấy" in str(exc) else "Kết nối ADB thất bại."
            raise

        with self.lock:
            save_config(self.config_data)
            self.adb_ready = True
            self.status = "ADB đã kết nối 1 device. Có thể bắt đầu."
        return self.get_status()

    def start_bot(self) -> dict[str, Any]:
        with self.lock:
            if self._bot_running_locked():
                self._log("[INFO] Bot đang chạy rồi.")
                return self.get_status()
            if not self.adb_ready:
                self.status = "Chưa quét ADB."
                self._log("[ADB] Bấm Quét ADB trước. Kết nối OK rồi mới Bắt đầu.")
                return self.get_status()

            save_config(self.config_data)
            self.stop_event.clear()
            self.pause_event.clear()
            self.status = "Đang khởi động..."
            self.stats_by_device = {}
            self.bot_threads, self.active_devices = start_farm_threads(
                self.config_data,
                self._log,
                self.stop_event,
                self.pause_event,
                self._stats_threadsafe,
            )
        return self.get_status()

    def toggle_pause(self) -> dict[str, Any]:
        with self.lock:
            if self.pause_event.is_set():
                self.pause_event.clear()
                self.status = "Đang chạy..."
                self._log("[INFO] Tiếp tục.")
            else:
                self.pause_event.set()
                self.status = "Đã tạm dừng."
                self._log("[INFO] Đã tạm dừng.")
        return self.get_status()

    def stop_bot(self) -> dict[str, Any]:
        with self.lock:
            self.stop_event.set()
            self.pause_event.clear()
            self.status = "Đang dừng..."
        self._log("[INFO] Yêu cầu dừng.")
        return self.get_status()

    def get_logs(self, after: int = 0) -> dict[str, Any]:
        self._drain_logs()
        with self.lock:
            items = [item for item in self.logs if int(item["id"]) > after]
            next_after = int(self.logs[-1]["id"]) if self.logs else after
            return {"items": copy.deepcopy(items), "next_after": next_after}

    def clear_logs(self) -> None:
        with self.lock:
            self.logs.clear()
            self.next_log_id = 1

    def get_stats(self) -> dict[str, Any]:
        self._drain_stats()
        live_current = self._aggregate_session_stats()
        saved = self._load_saved_stats()
        current = live_current if any(live_current.values()) else saved.get("current_session", saved)
        total = saved.get("total", current)
        return {
            "current_session": {key: int(current.get(key, 0)) for key in STAT_KEYS},
            "total": {key: int(total.get(key, 0)) for key in STAT_KEYS},
            "by_device": copy.deepcopy(self.stats_by_device),
        }

    def capture_screenshot(self) -> dict[str, Any]:
        config = self.get_config()
        resolution = tuple(config["game"].get("resolution", [1600, 900]))
        client = ADBClient(config["adb"].get("path", ""), config["adb"].get("device", ""), log=self._log, resolution=resolution)
        if config["adb"].get("connect_on_start", True):
            client.connect()
        png = client.screencap_png()
        return {
            "image_base64": base64.b64encode(png).decode("ascii"),
            "width": int(resolution[0]),
            "height": int(resolution[1]),
        }

    def list_reference_images(self) -> dict[str, Any]:
        img_dir = Path("img")
        items: list[dict[str, Any]] = []
        if not img_dir.exists():
            return {"items": items}
        for path in sorted(img_dir.iterdir()):
            if path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
                continue
            width, height = self._image_size(path)
            items.append(
                {
                    "name": path.name,
                    "label": self._reference_image_label(path.stem),
                    "width": width,
                    "height": height,
                }
            )
        return {"items": items}

    def reference_image(self, name: str) -> dict[str, Any]:
        path = self._safe_reference_image_path(name)
        width, height = self._image_size(path)
        return {
            "image_base64": base64.b64encode(path.read_bytes()).decode("ascii"),
            "width": width,
            "height": height,
        }

    def test_tap(self, x: int, y: int) -> None:
        config = self.get_config()
        resolution = tuple(config["game"].get("resolution", [1600, 900]))
        client = ADBClient(config["adb"].get("path", ""), config["adb"].get("device", ""), log=self._log, resolution=resolution)
        if config["adb"].get("connect_on_start", True):
            client.connect()
        client.tap(int(x), int(y), jitter=0)
        self._log(f"[COORD] Test tap {int(x)},{int(y)}.")

    def save_points(self, target: str, points: list[list[int]], combo_name: str = "") -> dict[str, Any]:
        deploy_zone_targets = {
            "zone_trenbenphai": ["deploy", "deploy_zones", "trenbenphai"],
            "zone_trenbentrai": ["deploy", "deploy_zones", "trenbentrai"],
            "zone_duoibenphai": ["deploy", "deploy_zones", "duoibenphai"],
            "zone_duoibentrai": ["deploy", "deploy_zones", "duoibentrai"],
        }
        allowed = dict(deploy_zone_targets)
        global_targets = set(deploy_zone_targets)
        spell_targets = {
            "spell_group": ["deploy", "spell_groups", "0", "zones"],
        }
        for prefix, base_path in spell_targets.items():
            for view in ("trenbenphai", "trenbentrai", "duoibenphai", "duoibentrai"):
                allowed[f"{prefix}_zone_{view}"] = [*base_path, view]
                global_targets.add(f"{prefix}_zone_{view}")
        if target not in allowed:
            raise ValueError("Target tọa độ không hợp lệ.")
        normalized = [[int(point[0]), int(point[1])] for point in points]
        with self.lock:
            self._set_config_path(self.config_data, allowed[target], normalized)
            combos = self.config_data.get("combos", {})
            selected_combo = combo_name or self.config_data.get("farm", {}).get("combo", "")
            combo_path = allowed[target][1:] if allowed[target][0] == "deploy" else allowed[target]
            updated_combos: list[str] = []

            if target in global_targets:
                selected_combo = "__global__"
            elif selected_combo == "__global__":
                updated_combos = []
            elif selected_combo == "__all__":
                for name, combo in combos.items():
                    combo_deploy = combo.setdefault("deploy", copy.deepcopy(self.config_data.get("deploy", {})))
                    self._set_config_path(combo_deploy, combo_path, normalized)
                    updated_combos.append(str(name))
            elif selected_combo:
                if selected_combo not in combos:
                    raise ValueError(f"Combo không hợp lệ: {selected_combo}")
                combo_deploy = combos[selected_combo].setdefault("deploy", copy.deepcopy(self.config_data.get("deploy", {})))
                self._set_config_path(combo_deploy, combo_path, normalized)
                updated_combos.append(selected_combo)
            save_config(self.config_data)
        combo_label = "global deploy" if target in global_targets else (", ".join(updated_combos) if updated_combos else "global deploy")
        self._log(f"[COORD] Saved {len(normalized)} point(s) to {target} | {combo_label}.")
        return self.get_config()

    def slot_templates(self) -> dict[str, Any]:
        detector = SlotDetector(self.get_config(), self._log)
        return {"kinds": detector.kinds, "items": detector.template_summary()}

    def save_slot_template(
        self,
        kind: str,
        image_base64: str,
        x: int,
        y: int,
        size: int = 76,
        crop_region: list[int] | None = None,
    ) -> dict[str, Any]:
        detector = SlotDetector(self.get_config(), self._log)
        path = detector.save_template_from_base64(kind, image_base64, x, y, size, crop_region)
        self._log(f"[SLOT] Saved template {kind}: {path}.")
        return self.slot_templates()

    def delete_slot_template(self, kind: str, filename: str) -> dict[str, Any]:
        detector = SlotDetector(self.get_config(), self._log)
        path = detector.delete_template(kind, filename)
        self._log(f"[SLOT] Deleted template {kind}: {path.name}.")
        return self.slot_templates()

    def detect_slots(self, image_base64: str = "") -> dict[str, Any]:
        config = self.get_config()
        if image_base64:
            png = base64.b64decode(image_base64)
        else:
            resolution = tuple(config["game"].get("resolution", [1600, 900]))
            client = ADBClient(config["adb"].get("path", ""), config["adb"].get("device", ""), log=self._log, resolution=resolution)
            if config["adb"].get("connect_on_start", True):
                client.connect()
            png = client.screencap_png()

        detector = SlotDetector(config, self._log)
        vision = Vision(config, self._log)
        detections = detector.detect(png)
        for detection in detections:
            detection.count = vision.read_slot_count(png, detection.center, detection.kind)
        return {"items": [detection.as_dict() for detection in detections]}

    def _bot_running_locked(self) -> bool:
        return any(thread.is_alive() for thread in self.bot_threads)

    def _log(self, message: str) -> None:
        self.log_queue.put(message)

    def _drain_logs(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            with self.lock:
                if "Bot started" in message:
                    self.status = "Đang chạy..."
                if "Bot stopped" in message and not self._bot_running_locked():
                    self.status = "Đã dừng."
                if "[ERROR]" in message and not self._bot_running_locked():
                    self.status = "Đã dừng."
                self.logs.append(
                    {
                        "id": self.next_log_id,
                        "message": message,
                        "created_at": datetime.now().isoformat(timespec="seconds"),
                    }
                )
                self.next_log_id += 1
                if len(self.logs) > 2000:
                    self.logs = self.logs[-1500:]

    def _stats_threadsafe(self, device: str, stats: dict[str, Any]) -> None:
        self.stats_queue.put({"device": device, "stats": stats})

    def _drain_stats(self) -> None:
        while True:
            try:
                latest = self.stats_queue.get_nowait()
            except queue.Empty:
                break
            device = latest.get("device", "")
            if device:
                with self.lock:
                    self.stats_by_device[device] = latest.get("stats", {})

    def _aggregate_session_stats(self) -> dict[str, int]:
        total = {key: 0 for key in STAT_KEYS}
        for stats in self.stats_by_device.values():
            session = stats.get("current_session", stats)
            for key in STAT_KEYS:
                total[key] += int(session.get(key, 0))
        return total

    def _load_saved_stats(self) -> dict[str, Any]:
        stats_dir = Path("stats")
        if stats_dir.exists():
            current = {key: 0 for key in STAT_KEYS}
            total = {key: 0 for key in STAT_KEYS}
            loaded = 0
            for path in stats_dir.glob("*.json"):
                try:
                    with path.open("r", encoding="utf-8") as file:
                        data = json.load(file)
                except (OSError, json.JSONDecodeError):
                    continue
                session = data.get("current_session", {})
                all_time = data.get("total", session)
                for key in STAT_KEYS:
                    current[key] += int(session.get(key, 0))
                    total[key] += int(all_time.get(key, 0))
                loaded += 1
            if loaded:
                return {"current_session": current, "total": total}

        try:
            with Path("stats.json").open("r", encoding="utf-8") as file:
                data = json.load(file)
                session = data.get("current_session", data)
                total = data.get("total", session)
                return {"current_session": session, "total": total}
        except (OSError, json.JSONDecodeError):
            empty = {key: 0 for key in STAT_KEYS}
            return {"current_session": empty, "total": empty}

    def _validate_config(self, config: dict[str, Any]) -> None:
        game = config.get("game", {})
        farm = config.get("farm", {})
        surrender = config.get("surrender", {})
        attack_timing = config.get("attack_timing", {})
        manual_army = config.get("manual_army", {})
        wall_upgrade = config.get("wall_upgrade", {})
        if int(game.get("periodic_restart_min_seconds", 0)) > int(game.get("periodic_restart_max_seconds", 0)):
            raise ValueError("Thời gian restart tối thiểu phải <= tối đa.")
        if int(game.get("home_zoom_out_keyevents", 0)) < 0:
            raise ValueError("Zoom out ở làng chính phải >= 0.")
        if int(game.get("ldplayer_index", 0)) < 0:
            raise ValueError("LDPlayer index phải >= 0.")
        if int(farm.get("max_next", 0)) < 1:
            raise ValueError("Max Next phải >= 1.")
        if int(surrender.get("time_min_seconds", 0)) > int(surrender.get("time_max_seconds", 0)):
            raise ValueError("Thời gian đầu hàng tối thiểu phải <= tối đa.")
        if int(surrender.get("destruction_min_percent", 0)) > int(surrender.get("destruction_max_percent", 0)):
            raise ValueError("% phá hủy tối thiểu phải <= tối đa.")
        if int(surrender.get("damage_unknown_restart_seconds", 0)) < 0:
            raise ValueError("Thời gian restart khi damage không đọc được phải >= 0.")
        timing_ranges = [
            ("freeze_random_min_ms", "freeze_random_max_ms", "Thả băng"),
            ("rage_random_min_ms", "rage_random_max_ms", "Thả nộ"),
            ("hero_skill_min_ms", "hero_skill_max_ms", "Kích hoạt skill tướng"),
            ("next_battle_min_ms", "next_battle_max_ms", "Do tre tran moi"),
        ]
        for min_key, max_key, label in timing_ranges:
            if int(attack_timing.get(min_key, 0)) > int(attack_timing.get(max_key, 0)):
                raise ValueError(f"{label}: gia tri tu phai <= den.")
        if int(attack_timing.get("spell_min_point_distance_px", 0)) < 0:
            raise ValueError("Khoảng cách tối thiểu giữa 2 điểm thuốc phải >= 0.")
        if wall_upgrade:
            if int(wall_upgrade.get("run_every_n_attacks", 1)) < 1:
                raise ValueError("Nâng tường: số trận phải >= 1.")
            if int(wall_upgrade.get("trigger_percent", 0)) < 1 or int(wall_upgrade.get("trigger_percent", 0)) > 100:
                raise ValueError("Nâng tường: ngưỡng tài nguyên phải từ 1 đến 100.")
            if int(wall_upgrade.get("gold_capacity", 1)) < 1 or int(wall_upgrade.get("elixir_capacity", 1)) < 1:
                raise ValueError("Nâng tường: sức chứa vàng/dầu phải >= 1.")
            if int(wall_upgrade.get("reserve_gold", 0)) < 0 or int(wall_upgrade.get("reserve_elixir", 0)) < 0:
                raise ValueError("Nâng tường: tài nguyên giữ lại phải >= 0.")
            if int(wall_upgrade.get("add1_rounds", 1)) < 1:
                raise ValueError("Nâng tường: số lần bấm +1 phải >= 1.")
            if int(wall_upgrade.get("max_add_rounds", 1)) < 1:
                raise ValueError("Nâng tường: tối đa lần bấm +10 phải >= 1.")
            if int(wall_upgrade.get("retry_backoff_attacks", 1)) < 1:
                raise ValueError("Nâng tường: số trận nghỉ sau lỗi phải >= 1.")
            if str(wall_upgrade.get("pay_with", "auto")) not in {"auto", "gold", "elixir"}:
                raise ValueError("Nâng tường: tài nguyên dùng phải là auto/gold/elixir.")
        counts = manual_army.get("counts", {})
        if isinstance(counts, dict):
            for kind, value in counts.items():
                if int(value) < 0:
                    raise ValueError(f"Số quân {kind} phải >= 0.")

    def _set_config_path(self, root: dict[str, Any], path: list[str], value: Any) -> None:
        cursor: Any = root
        for key in path[:-1]:
            if key.isdigit() and isinstance(cursor, list):
                cursor = cursor[int(key)]
                continue
            if key not in cursor or not isinstance(cursor[key], (dict, list)):
                cursor[key] = {}
            cursor = cursor[key]
        last = path[-1]
        if last.isdigit() and isinstance(cursor, list):
            cursor[int(last)] = value
        else:
            cursor[last] = value

    def _safe_reference_image_path(self, name: str) -> Path:
        img_dir = Path("img").resolve()
        path = (img_dir / name).resolve()
        if not str(path).startswith(str(img_dir)) or path.suffix.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
            raise ValueError("Ảnh mẫu không hợp lệ.")
        if not path.exists():
            raise ValueError("Không tìm thấy ảnh mẫu.")
        return path

    def _image_size(self, path: Path) -> tuple[int, int]:
        try:
            from PIL import Image

            with Image.open(path) as image:
                return image.size
        except Exception:
            resolution = self.config_data.get("game", {}).get("resolution", [1600, 900])
            return int(resolution[0]), int(resolution[1])

    def _reference_image_label(self, stem: str) -> str:
        labels = {
            "trenbentrai": "Trên bên trái",
            "trenbenphai": "Trên bên phải",
            "duoibentrai": "Dưới bên trái",
            "duoibenphai": "Dưới bên phải",
        }
        return labels.get(stem.lower(), stem)
