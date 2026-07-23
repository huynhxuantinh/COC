from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from adb_client import ADBClient, ADBError, COMMON_DEVICES, discover_adb_paths
from bot import FarmBot
from config_manager import load_config, save_config


class COCFarmApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("COC Auto Farm - LDPlayer 1600x900")
        self.geometry("920x820")
        self.minsize(860, 720)
        self.configure(bg="#1f2227")

        self.config_data = load_config()
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.bot_thread: threading.Thread | None = None
        self.stop_event = threading.Event()
        self.pause_event = threading.Event()
        self.adb_ready = False
        self.vars: dict[str, tk.Variable] = {}

        self._style()
        self._build_ui()
        self.after(120, self._drain_logs)

    def _style(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#1f2227")
        style.configure("Card.TFrame", background="#2b2f36", relief="flat")
        style.configure("TLabel", background="#1f2227", foreground="#eef2f6", font=("Segoe UI", 10))
        style.configure("Card.TLabel", background="#2b2f36", foreground="#eef2f6", font=("Segoe UI", 10))
        style.configure("Title.TLabel", background="#2b2f36", foreground="#ffffff", font=("Segoe UI", 11, "bold"))
        style.configure("Muted.TLabel", background="#2b2f36", foreground="#9aa5b1")
        style.configure("TCheckbutton", background="#2b2f36", foreground="#eef2f6", font=("Segoe UI", 10))
        style.map("TCheckbutton", background=[("active", "#2b2f36")])
        style.configure("TRadiobutton", background="#2b2f36", foreground="#eef2f6", font=("Segoe UI", 10))
        style.map("TRadiobutton", background=[("active", "#2b2f36")])
        style.configure("TNotebook", background="#1f2227", borderwidth=0)
        style.configure("TNotebook.Tab", background="#343944", foreground="#dce3ea", padding=(14, 8))
        style.map("TNotebook.Tab", background=[("selected", "#485161")], foreground=[("selected", "#ffffff")])
        style.configure("TEntry", fieldbackground="#20242a", foreground="#ffffff", bordercolor="#56606c")
        style.configure("TCombobox", fieldbackground="#20242a", background="#20242a", foreground="#ffffff")

    def _build_ui(self) -> None:
        root = tk.Frame(self, bg="#1f2227")
        root.pack(fill="both", expand=True, padx=16, pady=16)

        self._build_header(root)
        self._build_tabs(root)
        self._build_logs(root)

    def _build_header(self, parent: tk.Frame) -> None:
        header = tk.Frame(parent, bg="#2b2f36", padx=14, pady=12)
        header.pack(fill="x")

        tk.Label(
            header,
            text="COC Auto Farm",
            bg="#2b2f36",
            fg="#ffffff",
            font=("Segoe UI", 15, "bold"),
        ).pack(side="left")

        actions = tk.Frame(header, bg="#2b2f36")
        actions.pack(side="right")

        self._button(actions, "Scan ADB", self.scan_adb, "#2478d4").pack(side="left", padx=5)
        self._button(actions, "Start", self.start_bot, "#25c766").pack(side="left", padx=5)
        self._button(actions, "Pause / Resume", self.toggle_pause, "#69788f").pack(side="left", padx=5)
        self._button(actions, "Stop", self.stop_bot, "#e53138").pack(side="left", padx=5)
        self._button(actions, "Cai dat", self.open_settings_hint, "#56657a").pack(side="left", padx=5)

        self.status_var = tk.StringVar(value="Chua scan ADB.")
        status = tk.Label(
            parent,
            textvariable=self.status_var,
            bg="#111418",
            fg="#47a7ff",
            anchor="w",
            padx=14,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        )
        status.pack(fill="x", pady=(10, 12))

    def _build_tabs(self, parent: tk.Frame) -> None:
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="x")

        farm_tab = ttk.Frame(notebook, style="Card.TFrame", padding=16)
        surrender_tab = ttk.Frame(notebook, style="Card.TFrame", padding=16)
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
        self.vars["donate_when_farming"] = tk.BooleanVar(value=game["donate_when_farming"])
        self.vars["change_combo_on_start"] = tk.BooleanVar(value=game["change_combo_on_start"])
        self.vars["resource_stats"] = tk.BooleanVar(value=game["resource_stats"])
        self.vars["restart_if_attack_missing"] = tk.BooleanVar(value=game.get("restart_if_attack_missing", True))
        self.vars["combo"] = tk.StringVar(value="Rong Dien")
        self.vars["deploy_mode"] = tk.StringVar(value=self._deploy_label(farm["deploy_mode"]))
        self.vars["gold_min"] = tk.StringVar(value=f"{farm['gold_min']:,}")
        self.vars["elixir_min"] = tk.StringVar(value=f"{farm['elixir_min']:,}")
        self.vars["dark_min"] = tk.StringVar(value=f"{farm['dark_min']:,}")
        self.vars["total_min"] = tk.StringVar(value=f"{farm['total_min']:,}")

        left = ttk.Frame(parent, style="Card.TFrame")
        right = ttk.Frame(parent, style="Card.TFrame")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 24))
        right.grid(row=0, column=1, sticky="nsew")
        parent.columnconfigure(0, weight=1)
        parent.columnconfigure(1, weight=1)

        ttk.Label(left, text="Cai dat chay", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        checks = [
            ("Bo qua khoi dong lai game", "skip_restart_game"),
            ("Bat tu dong dung", "auto_stop"),
            ("Bat cho linh khi farm", "donate_when_farming"),
            ("Tu dong doi combo khi bat dau", "change_combo_on_start"),
            ("Thong ke tai nguyen", "resource_stats"),
            ("Khong thay Attack thi mo lai game", "restart_if_attack_missing"),
        ]
        for i, (text, key) in enumerate(checks, start=1):
            ttk.Checkbutton(left, text=text, variable=self.vars[key]).grid(
                row=i, column=0, columnspan=2, sticky="w", pady=5
            )

        ttk.Label(left, text="Tu dong bat lai sau", style="Card.TLabel").grid(row=7, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(left, textvariable=self.vars["auto_restart_after_seconds"], width=8).grid(
            row=7, column=1, sticky="w", pady=(10, 0)
        )

        ttk.Label(right, text="Nguong farm", style="Title.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        self._field(right, 1, "Combo", self.vars["combo"], values=["Rong Dien"])
        self._field(right, 2, "Vang toi thieu", self.vars["gold_min"])
        self._field(right, 3, "Dau toi thieu", self.vars["elixir_min"])
        self._field(right, 4, "Dau den toi thieu", self.vars["dark_min"])
        self._field(right, 5, "Tong tai nguyen", self.vars["total_min"])

        ttk.Label(right, text="Che do tha", style="Card.TLabel").grid(row=6, column=0, sticky="w", pady=(12, 6))
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
        self._field(parent, 6, "Tong tai nguyen <", self.vars["total_remaining_less_than"])
        ttk.Checkbutton(parent, text="Khong dau hang (danh het)", variable=self.vars["never_surrender"]).grid(
            row=7, column=0, columnspan=4, sticky="w", pady=(14, 5)
        )

    def _build_logs(self, parent: tk.Frame) -> None:
        log_card = tk.Frame(parent, bg="#111418", padx=10, pady=10)
        log_card.pack(fill="both", expand=True, pady=(14, 0))

        top = tk.Frame(log_card, bg="#111418")
        top.pack(fill="x", pady=(0, 8))
        tk.Label(top, text="Logs", bg="#111418", fg="#ffffff", font=("Segoe UI", 11, "bold")).pack(side="left")
        self._button(top, "Clear", self.clear_logs, "#343944", width=9).pack(side="right")

        body = tk.Frame(log_card, bg="#111418")
        body.pack(fill="both", expand=True)
        self.log_text = tk.Text(
            body,
            bg="#0c0f13",
            fg="#e7edf3",
            insertbackground="white",
            relief="flat",
            wrap="word",
            font=("Consolas", 10),
            height=18,
        )
        scroll = tk.Scrollbar(body, command=self.log_text.yview)
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
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=6, padx=(0, 12))
        if values:
            ttk.Combobox(parent, textvariable=var, values=values, width=20, state="readonly").grid(
                row=row, column=1, sticky="ew", pady=6
            )
        else:
            ttk.Entry(parent, textvariable=var, width=20).grid(row=row, column=1, sticky="ew", pady=6)

    def _range(self, parent: ttk.Frame, row: int, label: str, start: tk.StringVar, end: tk.StringVar, suffix: str) -> None:
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(parent, textvariable=start, width=8).grid(row=row, column=1, sticky="w", padx=8)
        ttk.Label(parent, text="-", style="Card.TLabel").grid(row=row, column=2, sticky="w")
        ttk.Entry(parent, textvariable=end, width=8).grid(row=row, column=3, sticky="w", padx=8)
        ttk.Label(parent, text=suffix, style="Card.TLabel").grid(row=row, column=4, sticky="w")

    def _button(self, parent, text: str, command, bg: str, width: int = 12) -> tk.Button:
        return tk.Button(
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
            font=("Segoe UI", 9, "bold"),
        )

    def start_bot(self) -> None:
        if self.bot_thread and self.bot_thread.is_alive():
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
        bot = FarmBot(self.config_data, self._log_threadsafe, self.stop_event, self.pause_event)
        self.bot_thread = threading.Thread(target=bot.run, daemon=True)
        self.bot_thread.start()

    def scan_adb(self) -> None:
        if self.bot_thread and self.bot_thread.is_alive():
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
        configured_device = self.config_data["adb"].get("device", "")
        if configured_device:
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
                save_config(self.config_data)
                self.adb_ready = True
                self._log_threadsafe(f"[ADB] OK: {path} | {device}")
                self.after(0, lambda: self.status_var.set("ADB da ket noi. Co the Start."))
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
        win = tk.Toplevel(self)
        win.title("Cai dat")
        win.geometry("650x270")
        win.configure(bg="#1f2227")
        win.transient(self)
        win.grab_set()

        adb_path = tk.StringVar(value=self.config_data["adb"]["path"])
        device = tk.StringVar(value=self.config_data["adb"]["device"])
        tess_path = tk.StringVar(value=self.config_data["ocr"]["tesseract_path"])
        max_next = tk.StringVar(value=str(self.config_data["farm"]["max_next"]))

        frame = ttk.Frame(win, style="Card.TFrame", padding=16)
        frame.pack(fill="both", expand=True, padx=14, pady=14)

        self._settings_row(frame, 0, "ADB path", adb_path, True)
        self._settings_row(frame, 1, "Device", device)
        self._settings_row(frame, 2, "Tesseract path", tess_path, True)
        self._settings_row(frame, 3, "Max Next", max_next)

        def save() -> None:
            try:
                self.config_data["adb"]["path"] = adb_path.get().strip()
                self.config_data["adb"]["device"] = device.get().strip() or "127.0.0.1:5555"
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

        self._button(frame, "Luu", save, "#25c766").grid(row=4, column=1, sticky="e", pady=18)

    def _settings_row(self, parent: ttk.Frame, row: int, label: str, var: tk.StringVar, browse: bool = False) -> None:
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=8)
        ttk.Entry(parent, textvariable=var, width=52).grid(row=row, column=1, sticky="ew", pady=8, padx=8)
        if browse:
            self._button(parent, "Chon", lambda: self._pick_file(var), "#56657a", width=8).grid(row=row, column=2)

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
        game["donate_when_farming"] = bool(self.vars["donate_when_farming"].get())
        game["change_combo_on_start"] = bool(self.vars["change_combo_on_start"].get())
        game["resource_stats"] = bool(self.vars["resource_stats"].get())
        game["restart_if_attack_missing"] = bool(self.vars["restart_if_attack_missing"].get())

        farm["combo"] = "Rong Dien"
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

    def _log(self, message: str) -> None:
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")

    def _drain_logs(self) -> None:
        while True:
            try:
                message = self.log_queue.get_nowait()
            except queue.Empty:
                break
            self._log(message)
            if message.startswith("[INFO] Bot started"):
                self.status_var.set("Dang chay...")
            if message.startswith("[INFO] Bot stopped") or message.startswith("[ERROR]"):
                self.status_var.set("Da dung.")
        self.after(120, self._drain_logs)


if __name__ == "__main__":
    app = COCFarmApp()
    app.mainloop()
