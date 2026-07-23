from __future__ import annotations

import copy
import json
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from adb_client import ADBClient, ADBError, COMMON_DEVICES, discover_adb_paths
from bot import FarmBot
from config_manager import load_config, save_config


class COCFarmApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("COC Auto Farm - LDPlayer 1600x900")
        self.geometry("1120x760")
        self.minsize(900, 640)
        self.colors = {
            "bg": "#171a1f",
            "panel": "#222731",
            "panel_2": "#282e39",
            "panel_3": "#11151b",
            "line": "#394250",
            "text": "#f3f6f9",
            "muted": "#9da8b5",
            "blue": "#2f8cff",
            "green": "#22c55e",
            "red": "#ef4444",
            "amber": "#f59e0b",
            "slate": "#64748b",
        }
        self.configure(bg=self.colors["bg"])

        self.config_data = load_config()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.stats_queue: queue.Queue[dict] = queue.Queue()
        self.bot_thread: threading.Thread | None = None
        self.bot_threads: list[threading.Thread] = []
        self.active_devices: list[str] = []
        self.stats_by_device: dict[str, dict] = {}
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.adb_ready = False
        self.vars: dict[str, tk.Variable] = {}
        self.stat_vars: dict[str, tk.StringVar] = {}
        self.responsive_mode = ""

        self._style()
        self._build_ui()
        self.bind("<Configure>", self._on_resize)
        self.after(120, self._drain_logs)

    def _style(self) -> None:
        c = self.colors
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background=c["bg"])
        style.configure("Panel.TFrame", background=c["panel"], relief="flat")
        style.configure("Card.TFrame", background=c["panel_2"], relief="flat")
        style.configure("TLabel", background=c["bg"], foreground=c["text"], font=("Segoe UI", 10))
        style.configure("Panel.TLabel", background=c["panel"], foreground=c["text"], font=("Segoe UI", 10))
        style.configure("Card.TLabel", background=c["panel_2"], foreground=c["text"], font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=c["panel"], foreground=c["text"], font=("Segoe UI", 12, "bold"))
        style.configure("CardTitle.TLabel", background=c["panel_2"], foreground=c["text"], font=("Segoe UI", 10, "bold"))
        style.configure("Muted.TLabel", background=c["panel"], foreground=c["muted"], font=("Segoe UI", 9))
        style.configure("TCheckbutton", background=c["panel"], foreground=c["text"], font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", c["panel"])], foreground=[("disabled", c["muted"])])
        style.configure("TRadiobutton", background=c["panel"], foreground=c["text"], font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[("active", c["panel"])])
        style.configure("TNotebook", background=c["panel"], borderwidth=0)
        style.configure("TNotebook.Tab", background=c["panel_3"], foreground=c["muted"], padding=(16, 9), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", c["panel_2"])], foreground=[("selected", c["text"])])
        style.configure(
            "TEntry",
            fieldbackground=c["panel_3"],
            foreground=c["text"],
            bordercolor=c["line"],
            lightcolor=c["line"],
            darkcolor=c["line"],
            padding=(8, 6),
        )
        style.configure(
            "TCombobox",
            fieldbackground=c["panel_3"],
            background=c["panel_3"],
            foreground=c["text"],
            bordercolor=c["line"],
            arrowcolor=c["text"],
            padding=(8, 6),
        )

    def _build_ui(self) -> None:
        root = tk.Frame(self, bg=self.colors["bg"])
        root.pack(fill="both", expand=True, padx=16, pady=16)
        root.grid_columnconfigure(0, weight=1)
        root.grid_rowconfigure(2, weight=1)

        self._build_header(root)

        content = tk.Frame(root, bg=self.colors["bg"])
        content.grid(row=2, column=0, sticky="nsew")
        self.content_frame = content

        left = tk.Frame(content, bg=self.colors["panel"], padx=14, pady=14)
        right = tk.Frame(content, bg=self.colors["bg"])
        self.left_panel = left
        self.right_panel = right
        right.grid_columnconfigure(0, weight=1)
        right.grid_rowconfigure(1, weight=1)

        self._build_tabs(left)
        self._build_stats(right)
        self._build_logs(right)
        self._apply_responsive_layout(self.winfo_width())

    def _on_resize(self, event) -> None:
        if event.widget is self:
            self._apply_responsive_layout(event.width)

    def _apply_responsive_layout(self, width: int) -> None:
        if not hasattr(self, "content_frame"):
            return
        mode = "compact" if width < 1040 else "wide"
        if mode == self.responsive_mode:
            return
        self.responsive_mode = mode

        content = self.content_frame
        left = self.left_panel
        right = self.right_panel
        left.grid_forget()
        right.grid_forget()

        if mode == "compact":
            self.header_frame.grid_columnconfigure(1, weight=0)
            self.actions_frame.grid(row=1, column=0, sticky="w", pady=(12, 0))
            content.grid_columnconfigure(0, weight=1, minsize=0)
            content.grid_columnconfigure(1, weight=0, minsize=0)
            content.grid_rowconfigure(0, weight=0)
            content.grid_rowconfigure(1, weight=1)
            left.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 12))
            right.grid(row=1, column=0, sticky="nsew")
            return

        self.actions_frame.grid(row=0, column=1, sticky="e", pady=0)
        content.grid_columnconfigure(0, weight=0, minsize=430)
        content.grid_columnconfigure(1, weight=1, minsize=0)
        content.grid_rowconfigure(0, weight=1)
        content.grid_rowconfigure(1, weight=0)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 14), pady=0)
        right.grid(row=0, column=1, sticky="nsew")

    def _build_header(self, parent: tk.Frame) -> None:
        c = self.colors
        header = tk.Frame(parent, bg=c["panel"], padx=16, pady=14)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        self.header_frame = header

        title_box = tk.Frame(header, bg=c["panel"])
        title_box.grid(row=0, column=0, sticky="w")
        self.title_box = title_box
        tk.Label(
            title_box,
            text="COC Auto Farm",
            bg=c["panel"],
            fg=c["text"],
            font=("Segoe UI", 17, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_box,
            text="LDPlayer 1600x900 - farm lang chinh qua ADB",
            bg=c["panel"],
            fg=c["muted"],
            font=("Segoe UI", 9),
        ).pack(anchor="w", pady=(2, 0))

        actions = tk.Frame(header, bg=c["panel"])
        actions.grid(row=0, column=1, sticky="e")
        self.actions_frame = actions

        self._button(actions, "Scan ADB", self.scan_adb, c["blue"], width=11).pack(side="left", padx=4)
        self._button(actions, "Start", self.start_bot, c["green"], width=9).pack(side="left", padx=4)
        self._button(actions, "Pause", self.toggle_pause, c["slate"], width=9).pack(side="left", padx=4)
        self._button(actions, "Stop", self.stop_bot, c["red"], width=9).pack(side="left", padx=4)
        self._button(actions, "Cai dat", self.open_settings_hint, "#4b5563", width=9).pack(side="left", padx=4)

        self.status_var = tk.StringVar(value="Chua scan ADB.")
        status = tk.Label(
            parent,
            textvariable=self.status_var,
            bg=c["panel_3"],
            fg=c["blue"],
            anchor="w",
            padx=14,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        )
        status.grid(row=1, column=0, sticky="ew", pady=(10, 14))

    def _build_stats(self, parent: tk.Frame) -> None:
        c = self.colors
        stats = self._load_saved_stats()
        card = tk.Frame(parent, bg=c["panel"], padx=14, pady=12)
        card.pack(fill="x", pady=(0, 12))

        tk.Label(
            card,
            text="Thong ke phien",
            bg=c["panel"],
            fg=c["text"],
            font=("Segoe UI", 12, "bold"),
        ).pack(anchor="w")

        items = [
            ("attacks", "Tran"),
            ("next", "Next"),
            ("gold_seen", "Vang"),
            ("elixir_seen", "Dau"),
            ("dark_seen", "Dau den"),
        ]
        row = tk.Frame(card, bg=c["panel"])
        row.pack(fill="x", pady=(10, 0))
        for key, label in items:
            value = int(stats.get(key, 0))
            self.stat_vars[key] = tk.StringVar(value=f"{value:,}")
            item = tk.Frame(row, bg=c["panel_2"], padx=10, pady=8)
            item.pack(side="left", fill="x", expand=True, padx=(0, 8))
            tk.Label(
                item,
                text=label,
                bg=c["panel_2"],
                fg=c["muted"],
                font=("Segoe UI", 8, "bold"),
            ).pack(anchor="w")
            tk.Label(
                item,
                textvariable=self.stat_vars[key],
                bg=c["panel_2"],
                fg=c["text"],
                font=("Segoe UI", 12, "bold"),
            ).pack(anchor="w", pady=(2, 0))

    def _load_saved_stats(self) -> dict:
        multi_stats = self._load_multi_device_stats()
        if multi_stats:
            return multi_stats
        try:
            with Path("stats.json").open("r", encoding="utf-8") as file:
                data = json.load(file)
                return data.get("current_session", data)
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_multi_device_stats(self) -> dict:
        stats_dir = Path("stats")
        if not stats_dir.exists():
            return {}
        keys = ("attacks", "next", "gold_seen", "elixir_seen", "dark_seen")
        total = {key: 0 for key in keys}
        loaded = 0
        for path in stats_dir.glob("*.json"):
            try:
                with path.open("r", encoding="utf-8") as file:
                    data = json.load(file)
            except (OSError, json.JSONDecodeError):
                continue
            session = data.get("current_session", data)
            for key in keys:
                total[key] += int(session.get(key, 0))
            loaded += 1
        return total if loaded else {}

    def _combo_names(self) -> list[str]:
        combos = self.config_data.get("combos", {})
        if combos:
            return list(combos.keys())
        combo = self.config_data.get("farm", {}).get("combo", "Rong Dien")
        return [combo]

    def _build_tabs(self, parent: tk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)

        farm_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=14)
        surrender_tab = ttk.Frame(notebook, style="Panel.TFrame", padding=14)
        notebook.add(farm_tab, text="Farm")
        notebook.add(surrender_tab, text="Dau hang")

        self._build_farm_tab(farm_tab)
        self._build_surrender_tab(surrender_tab)

    def _build_farm_tab(self, parent: ttk.Frame) -> None:
        game = self.config_data["game"]
        farm = self.config_data["farm"]

        self.vars["skip_restart_game"] = tk.BooleanVar(value=game["skip_restart_game"])
        self.vars["auto_stop"] = tk.BooleanVar(value=game["auto_stop"])
        self.vars["auto_restart_after_seconds"] = tk.StringVar(value=str(game["auto_restart_after_seconds"]))
        self.vars["periodic_restart_game"] = tk.BooleanVar(value=game.get("periodic_restart_game", False))
        self.vars["periodic_restart_min_seconds"] = tk.StringVar(value=str(game.get("periodic_restart_min_seconds", 3600)))
        self.vars["periodic_restart_max_seconds"] = tk.StringVar(value=str(game.get("periodic_restart_max_seconds", 5400)))
        self.vars["donate_when_farming"] = tk.BooleanVar(value=game["donate_when_farming"])
        self.vars["change_combo_on_start"] = tk.BooleanVar(value=game["change_combo_on_start"])
        self.vars["resource_stats"] = tk.BooleanVar(value=game["resource_stats"])
        self.vars["restart_if_attack_missing"] = tk.BooleanVar(value=game.get("restart_if_attack_missing", True))
        combo_names = self._combo_names()
        selected_combo = farm.get("combo") if farm.get("combo") in combo_names else combo_names[0]
        self.vars["combo"] = tk.StringVar(value=selected_combo)
        self.vars["deploy_mode"] = tk.StringVar(value=self._deploy_label(farm["deploy_mode"]))
        self.vars["gold_min"] = tk.StringVar(value=f"{farm['gold_min']:,}")
        self.vars["elixir_min"] = tk.StringVar(value=f"{farm['elixir_min']:,}")
        self.vars["dark_min"] = tk.StringVar(value=f"{farm['dark_min']:,}")
        self.vars["total_min"] = tk.StringVar(value=f"{farm['total_min']:,}")

        left = ttk.Frame(parent, style="Panel.TFrame")
        right = ttk.Frame(parent, style="Panel.TFrame")
        left.grid(row=0, column=0, sticky="ew")
        right.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        parent.columnconfigure(0, weight=1)

        ttk.Label(left, text="Cai dat chay", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        checks = [
            ("Bo qua khoi dong lai game", "skip_restart_game"),
            ("Bat tu dong dung", "auto_stop"),
            ("Bat cho linh khi farm", "donate_when_farming"),
            ("Tu dong doi combo khi bat dau", "change_combo_on_start"),
            ("Thong ke tai nguyen", "resource_stats"),
            ("Khong thay Attack thi mo lai game", "restart_if_attack_missing"),
            ("Restart game dinh ky", "periodic_restart_game"),
        ]
        for i, (text, key) in enumerate(checks, start=1):
            ttk.Checkbutton(left, text=text, variable=self.vars[key]).grid(
                row=i, column=0, columnspan=2, sticky="w", pady=5
            )

        ttk.Label(left, text="Tu dong dung sau", style="Panel.TLabel").grid(row=8, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(left, textvariable=self.vars["auto_restart_after_seconds"], width=8).grid(
            row=8, column=1, sticky="w", pady=(10, 0)
        )
        self._range(
            left,
            9,
            "Restart game tu",
            self.vars["periodic_restart_min_seconds"],
            self.vars["periodic_restart_max_seconds"],
            "s",
        )

        ttk.Label(right, text="Nguong farm", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self._field(right, 1, "Combo", self.vars["combo"], values=self._combo_names())
        self._field(right, 2, "Vang toi thieu", self.vars["gold_min"])
        self._field(right, 3, "Dau toi thieu", self.vars["elixir_min"])
        self._field(right, 4, "Dau den (chi thong ke)", self.vars["dark_min"])
        self._field(right, 5, "Tong vang + dau", self.vars["total_min"])

        ttk.Label(right, text="Che do tha", style="Panel.TLabel").grid(row=6, column=0, sticky="w", pady=(12, 6))
        modes = ["Tha 1 canh", "Tha theo hang", "Tha 4 goc map", "Ngau nhien"]
        for i, label in enumerate(modes, start=7):
            ttk.Radiobutton(right, text=label, variable=self.vars["deploy_mode"], value=label).grid(
                row=i, column=0, columnspan=2, sticky="w", pady=3
            )

    def _build_surrender_tab(self, parent: ttk.Frame) -> None:
        surrender = self.config_data["surrender"]
        self.vars["by_time"] = tk.BooleanVar(value=surrender["by_time"])
        self.vars["time_min_seconds"] = tk.StringVar(value=str(surrender["time_min_seconds"]))
        self.vars["time_max_seconds"] = tk.StringVar(value=str(surrender["time_max_seconds"]))
        self.vars["by_destruction"] = tk.BooleanVar(value=surrender["by_destruction"])
        self.vars["destruction_min_percent"] = tk.StringVar(value=str(surrender["destruction_min_percent"]))
        self.vars["destruction_max_percent"] = tk.StringVar(value=str(surrender["destruction_max_percent"]))
        self.vars["when_low_loot"] = tk.BooleanVar(value=surrender["when_low_loot"])
        self.vars["total_remaining_less_than"] = tk.StringVar(value=f"{surrender['total_remaining_less_than']:,}")
        self.vars["never_surrender"] = tk.BooleanVar(value=surrender["never_surrender"])

        ttk.Label(parent, text="Dieu kien dau hang", style="Title.TLabel").grid(
            row=0, column=0, columnspan=4, sticky="w", pady=(0, 10)
        )
        ttk.Checkbutton(parent, text="Dau hang theo thoi gian", variable=self.vars["by_time"]).grid(
            row=1, column=0, columnspan=4, sticky="w", pady=5
        )
        self._range(parent, 2, "Tu", self.vars["time_min_seconds"], self.vars["time_max_seconds"], "s")

        ttk.Checkbutton(parent, text="Dau hang theo % pha huy", variable=self.vars["by_destruction"]).grid(
            row=3, column=0, columnspan=4, sticky="w", pady=(14, 5)
        )
        self._range(parent, 4, "Tu", self.vars["destruction_min_percent"], self.vars["destruction_max_percent"], "%")

        ttk.Checkbutton(parent, text="Dau hang khi con it tai nguyen", variable=self.vars["when_low_loot"]).grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(14, 5)
        )
        self._field(parent, 6, "Tong vang + dau <", self.vars["total_remaining_less_than"])
        ttk.Checkbutton(parent, text="Khong dau hang (danh het)", variable=self.vars["never_surrender"]).grid(
            row=7, column=0, columnspan=4, sticky="w", pady=(14, 5)
        )

    def _build_logs(self, parent: tk.Frame) -> None:
        c = self.colors
        log_card = tk.Frame(parent, bg=c["panel"], padx=14, pady=12)
        log_card.pack(fill="both", expand=True)

        top = tk.Frame(log_card, bg=c["panel"])
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="Logs", bg=c["panel"], fg=c["text"], font=("Segoe UI", 12, "bold")).pack(side="left")
        tk.Label(
            top,
            text="Theo doi scan, search, attack va loi ADB/OCR",
            bg=c["panel"],
            fg=c["muted"],
            font=("Segoe UI", 9),
        ).pack(side="left", padx=(10, 0))
        self._button(top, "Clear", self.clear_logs, "#374151", width=9).pack(side="right")

        body = tk.Frame(log_card, bg=c["panel_3"])
        body.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            body,
            bg=c["panel_3"],
            fg="#e6edf3",
            insertbackground="white",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            padx=10,
            pady=10,
            height=18,
        )
        scroll = tk.Scrollbar(body, command=self.log_text.yview, bg=c["panel_3"], troughcolor=c["panel_3"])
        self.log_text.configure(yscrollcommand=scroll.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

    def _field(
        self,
        parent: ttk.Frame,
        row: int,
        label: str,
        var: tk.StringVar,
        values: list[str] | None = None,
    ) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
        if values:
            ttk.Combobox(parent, textvariable=var, values=values, width=20, state="readonly").grid(
                row=row, column=1, sticky="ew", pady=6
            )
        else:
            ttk.Entry(parent, textvariable=var, width=20).grid(row=row, column=1, sticky="ew", pady=6)

    def _range(self, parent: ttk.Frame, row: int, label: str, start: tk.StringVar, end: tk.StringVar, suffix: str) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=start, width=8).grid(row=row, column=1, sticky="w", padx=8)
        ttk.Label(parent, text="-", style="Panel.TLabel").grid(row=row, column=2, sticky="w")
        ttk.Entry(parent, textvariable=end, width=8).grid(row=row, column=3, sticky="w", padx=8)
        ttk.Label(parent, text=suffix, style="Panel.TLabel").grid(row=row, column=4, sticky="w")

    def _button(self, parent, text: str, command, bg: str, width: int = 12) -> tk.Button:
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg="white",
            activebackground=bg,
            activeforeground="white",
            relief="flat",
            bd=0,
            width=width,
            padx=8,
            pady=7,
            cursor="hand2",
            highlightthickness=0,
            font=("Segoe UI", 9, "bold"),
        )
        button.bind("<Enter>", lambda _event: button.configure(bg=self._lighten(bg)))
        button.bind("<Leave>", lambda _event: button.configure(bg=bg))
        return button

    def _lighten(self, color: str) -> str:
        color = color.lstrip("#")
        if len(color) != 6:
            return color
        channels = [int(color[index : index + 2], 16) for index in (0, 2, 4)]
        lighter = [min(255, int(channel + (255 - channel) * 0.12)) for channel in channels]
        return "#" + "".join(f"{channel:02x}" for channel in lighter)

    def start_bot(self) -> None:
        if self._bot_running():
            self._log("[INFO] Bot dang chay roi.")
            return
        if not self.adb_ready:
            self._log("[ADB] Bam Scan ADB truoc. Ket noi OK roi moi Start.")
            self.status_var.set("Chua scan ADB.")
            return
        try:
            self._sync_config_from_ui()
            save_config(self.config_data)
        except ValueError as exc:
            self._log(f"[CONFIG] {exc}")
            return

        self.stop_event.clear()
        self.pause_event.clear()
        self.status_var.set("Dang khoi dong...")
        devices = self._configured_devices()
        self.bot_threads = []
        self.active_devices = devices
        self.stats_by_device = {}
        for device in devices:
            bot_config = copy.deepcopy(self.config_data)
            bot_config["adb"]["device"] = device
            bot_config.setdefault("runtime", {})["stats_path"] = f"stats/{self._safe_device_name(device)}.json"
            bot = FarmBot(
                bot_config,
                lambda message, dev=device: self._log_threadsafe(f"[{dev}] {message}"),
                self.stop_event,
                self.pause_event,
                lambda stats, dev=device: self._stats_threadsafe(dev, stats),
            )
            thread = threading.Thread(target=bot.run, daemon=True, name=f"FarmBot-{device}")
            self.bot_threads.append(thread)
            thread.start()
        self.bot_thread = self.bot_threads[0] if self.bot_threads else None

    def _bot_running(self) -> bool:
        return any(thread.is_alive() for thread in self.bot_threads) or bool(
            self.bot_thread and self.bot_thread.is_alive()
        )

    def _configured_devices(self) -> list[str]:
        device = self.config_data["adb"].get("device", "127.0.0.1:5555")
        return [device]

    def _parse_device_list(self, raw: str) -> list[str]:
        parts = raw.replace("\n", ",").replace(";", ",").split(",")
        devices = [part.strip() for part in parts if part.strip()]
        return devices or ["127.0.0.1:5555"]

    def _safe_device_name(self, device: str) -> str:
        return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in device)

    def scan_adb(self) -> None:
        if self._bot_running():
            self._log("[ADB] Dung bot truoc khi scan.")
            return
        self.adb_ready = False
        self.status_var.set("Dang scan ADB...")
        threading.Thread(target=self._scan_adb_worker, daemon=True).start()

    def _scan_adb_worker(self) -> None:
        self._log_threadsafe("[ADB] Dang quet adb.exe...")
        paths = discover_adb_paths(self.config_data["adb"].get("path", ""))
        if not paths:
            self._log_threadsafe("[ADB] Khong tim thay adb.exe. Bam Cai dat de chon file.")
            self.after(0, lambda: self.status_var.set("Khong thay ADB."))
            return

        devices = []
        configured_devices = self.config_data["adb"].get("devices") or []
        for device in configured_devices:
            if device not in devices:
                devices.append(device)
        configured_device = self.config_data["adb"].get("device", "")
        if configured_device and configured_device not in devices:
            devices.append(configured_device)
        for device in COMMON_DEVICES:
            if device not in devices:
                devices.append(device)

        self._log_threadsafe(f"[ADB] Tim thay {len(paths)} path. Dang thu ket noi...")
        for path in paths:
            self._log_threadsafe(f"[ADB] Thu path: {path}")
            for device in devices:
                try:
                    client = ADBClient(path, device, log=self._log_threadsafe)
                    client.connect()
                    client.screencap_png()
                except ADBError as exc:
                    self._log_threadsafe(f"[ADB] Fail {device}: {exc}")
                    continue

                self.config_data["adb"]["path"] = path
                self.config_data["adb"]["device"] = device
                self.config_data["adb"]["devices"] = []
                save_config(self.config_data)
                self.adb_ready = True
                self._log_threadsafe(f"[ADB] OK: {path} | {device}")
                self.after(0, lambda: self.status_var.set("ADB da ket noi 1 device. Co the Start."))
                return

        self._log_threadsafe("[ADB] Co adb.exe nhung khong connect duoc LDPlayer.")
        self.after(0, lambda: self.status_var.set("ADB connect fail."))

    def toggle_pause(self) -> None:
        if self.pause_event.is_set():
            self.pause_event.clear()
            self.status_var.set("Dang chay...")
            self._log("[INFO] Tiep tuc.")
        else:
            self.pause_event.set()
            self.status_var.set("Da tam dung.")
            self._log("[INFO] Da tam dung.")

    def stop_bot(self) -> None:
        self.stop_event.set()
        self.pause_event.clear()
        self.status_var.set("Dang dung...")
        self._log("[INFO] Yeu cau dung.")

    def clear_logs(self) -> None:
        self.log_text.delete("1.0", "end")

    def open_settings_hint(self) -> None:
        c = self.colors
        win = tk.Toplevel(self)
        win.title("Cai dat")
        win.geometry("650x270")
        win.configure(bg=c["bg"])
        win.transient(self)
        win.grab_set()

        adb_path = tk.StringVar(value=self.config_data["adb"]["path"])
        device = tk.StringVar(value=self._configured_devices()[0])
        tess_path = tk.StringVar(value=self.config_data["ocr"]["tesseract_path"])
        max_next = tk.StringVar(value=str(self.config_data["farm"]["max_next"]))

        frame = ttk.Frame(win, style="Panel.TFrame", padding=16)
        frame.pack(fill="both", expand=True, padx=14, pady=14)

        self._settings_row(frame, 0, "ADB path", adb_path, True)
        self._settings_row(frame, 1, "Device", device)
        self._settings_row(frame, 2, "Tesseract path", tess_path, True)
        self._settings_row(frame, 3, "Max Next", max_next)

        def save() -> None:
            try:
                self.config_data["adb"]["path"] = adb_path.get().strip()
                devices = self._parse_device_list(device.get())
                self.config_data["adb"]["device"] = devices[0]
                self.config_data["adb"]["devices"] = []
                self.config_data["ocr"]["tesseract_path"] = tess_path.get().strip()
                self.config_data["farm"]["max_next"] = int(max_next.get().replace(",", "").strip())
                save_config(self.config_data)
            except ValueError:
                self._log("[CONFIG] Max Next phai la so.")
                return
            self.adb_ready = False
            self.status_var.set("Da luu. Scan ADB lai.")
            self._log("[INFO] Da luu cai dat.")
            win.destroy()

        self._button(frame, "Luu", save, c["green"]).grid(row=4, column=1, sticky="e", pady=18)

    def _settings_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, browse: bool = False) -> None:
        ttk.Label(parent, text=label, style="Panel.TLabel").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(parent, textvariable=var, width=52).grid(row=row, column=1, sticky="ew", pady=8, padx=8)
        if browse:
            self._button(parent, "Chon", lambda: self._pick_file(var), self.colors["slate"], width=8).grid(row=row, column=2)

    def _pick_file(self, target_var: tk.StringVar) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Chon file",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if path:
            target_var.set(path)

    def _sync_config_from_ui(self) -> None:
        game = self.config_data["game"]
        farm = self.config_data["farm"]
        surrender = self.config_data["surrender"]

        game["skip_restart_game"] = bool(self.vars["skip_restart_game"].get())
        game["auto_stop"] = bool(self.vars["auto_stop"].get())
        game["auto_restart_after_seconds"] = self._int_var("auto_restart_after_seconds")
        game["periodic_restart_game"] = bool(self.vars["periodic_restart_game"].get())
        game["periodic_restart_min_seconds"] = self._int_var("periodic_restart_min_seconds")
        game["periodic_restart_max_seconds"] = self._int_var("periodic_restart_max_seconds")
        if game["periodic_restart_min_seconds"] > game["periodic_restart_max_seconds"]:
            raise ValueError("periodic_restart_min_seconds phai <= periodic_restart_max_seconds.")
        game["donate_when_farming"] = bool(self.vars["donate_when_farming"].get())
        game["change_combo_on_start"] = bool(self.vars["change_combo_on_start"].get())
        game["resource_stats"] = bool(self.vars["resource_stats"].get())
        game["restart_if_attack_missing"] = bool(self.vars["restart_if_attack_missing"].get())

        farm["combo"] = str(self.vars["combo"].get())
        farm["deploy_mode"] = self._deploy_value(str(self.vars["deploy_mode"].get()))
        farm["gold_min"] = self._money_var("gold_min")
        farm["elixir_min"] = self._money_var("elixir_min")
        farm["dark_min"] = self._money_var("dark_min")
        farm["total_min"] = self._money_var("total_min")

        surrender["by_time"] = bool(self.vars["by_time"].get())
        surrender["time_min_seconds"] = self._int_var("time_min_seconds")
        surrender["time_max_seconds"] = self._int_var("time_max_seconds")
        surrender["by_destruction"] = bool(self.vars["by_destruction"].get())
        surrender["destruction_min_percent"] = self._int_var("destruction_min_percent")
        surrender["destruction_max_percent"] = self._int_var("destruction_max_percent")
        surrender["when_low_loot"] = bool(self.vars["when_low_loot"].get())
        surrender["total_remaining_less_than"] = self._money_var("total_remaining_less_than")
        surrender["never_surrender"] = bool(self.vars["never_surrender"].get())

    def _money_var(self, key: str) -> int:
        raw = str(self.vars[key].get()).replace(",", "").replace(" ", "")
        if not raw.isdigit():
            raise ValueError(f"{key} phai la so.")
        return int(raw)

    def _int_var(self, key: str) -> int:
        return self._money_var(key)

    def _deploy_value(self, label: str) -> str:
        return {
            "Tha 1 canh": "one_edge",
            "Tha theo hang": "line",
            "Tha 4 goc map": "four_corner",
            "Ngau nhien": "random",
        }.get(label, "one_edge")

    def _deploy_label(self, value: str) -> str:
        return {
            "one_edge": "Tha 1 canh",
            "line": "Tha theo hang",
            "four_corner": "Tha 4 goc map",
            "random": "Ngau nhien",
        }.get(value, "Tha 1 canh")

    def _log_threadsafe(self, message: str) -> None:
        self.log_queue.put(message)

    def _stats_threadsafe(self, device: str, stats: dict) -> None:
        self.stats_queue.put({"device": device, "stats": stats})

    def _log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def _drain_logs(self) -> None:
        self._drain_stats()
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._log(message)
            if "Bot started" in message:
                self.status_var.set("Dang chay...")
            if "Bot stopped" in message and not self._bot_running():
                self.status_var.set("Da dung.")
            if "[ERROR]" in message and not self._bot_running():
                self.status_var.set("Da dung.")
        self.after(120, self._drain_logs)

    def _drain_stats(self) -> None:
        latest = None
        while True:
            try:
                latest = self.stats_queue.get_nowait()
            except queue.Empty:
                break
            if latest:
                device = latest.get("device", "")
                self.stats_by_device[device] = latest.get("stats", {})
        if self.stats_by_device:
            self._update_stats_display(self._aggregate_session_stats())

    def _aggregate_session_stats(self) -> dict:
        keys = ("attacks", "next", "gold_seen", "elixir_seen", "dark_seen")
        total = {key: 0 for key in keys}
        for stats in self.stats_by_device.values():
            session = stats.get("current_session", stats)
            for key in keys:
                total[key] += int(session.get(key, 0))
        return total

    def _update_stats_display(self, stats: dict) -> None:
        session = stats.get("current_session", stats)
        labels = {
            "attacks": "Tran",
            "next": "Next",
            "gold_seen": "Vang",
            "elixir_seen": "Dau",
            "dark_seen": "Dau den",
        }
        for key, label in labels.items():
            value = int(session.get(key, 0))
            if key in self.stat_vars:
                self.stat_vars[key].set(f"{value:,}")


if __name__ == "__main__":
    app = COCFarmApp()
    app.mainloop()
