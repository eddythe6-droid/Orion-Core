"""Tkinter desktop dashboard with a live, event-driven diagnostic console.

The UI displays real collector events; it does not simulate hardware test progress.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from . import __version__
from .report import collect_diagnostics_report
from .gpu_probe import ProbeReportError, validate_probe_report
from .history import HistoryStore, HistoryStoreError
from .game_inspector import GameInspectionError, inspect_game_path


class OrionDashboard:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title(f"Orion-Core | Research Laboratory {__version__}")
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        window_width = max(1120, min(1648, screen_width - 40))
        window_height = max(700, min(929, screen_height - 80))
        self.root.geometry(f"{window_width}x{window_height}")
        self.root.minsize(1120, 700)
        self.events: queue.Queue[tuple[str, Any]] = queue.Queue()
        self.worker: threading.Thread | None = None
        self.report: dict[str, Any] | None = None
        self.gpu_report: dict[str, Any] | None = None
        self.history_store = HistoryStore()
        self._scan_success = False
        self.log_lines: list[str] = []
        self._configure_style()
        self._build_layout()
        self.root.after(100, self._drain_events)
        self._log("INFO", "Orion-Core desktop interface initialized.")
        self._log("INFO", "Diagnostic collectors are read-only; GPU runtime tests are not started by this scan.")

    def _configure_style(self) -> None:
        """Apply a consistent dark desktop theme using native ttk widgets."""
        self.root.configure(bg="#0b1220")
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        bg = "#0b1220"
        surface = "#111c2d"
        card = "#17263a"
        border = "#263b55"
        text = "#e8f0fb"
        muted = "#91a5bf"
        accent = "#4ea1ff"
        accent_hover = "#70b4ff"

        self.root.option_add("*Font", ("Segoe UI", 10))
        self.root.option_add("*TCombobox*Listbox*Background", surface)
        self.root.option_add("*TCombobox*Listbox*Foreground", text)

        style.configure(".", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card, relief="flat")
        style.configure("Panel.TFrame", background=surface, relief="flat")
        style.configure("TLabel", background=bg, foreground=text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", background=bg, foreground="#f4f8ff",
                        font=("Segoe UI Semibold", 23))
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure("CardTitle.TLabel", background=card, foreground=muted,
                        font=("Segoe UI Semibold", 8))
        style.configure("CardValue.TLabel", background=card, foreground=text,
                        font=("Segoe UI Semibold", 15))
        style.configure("Section.TLabel", background=surface, foreground=accent,
                        font=("Segoe UI Semibold", 9))

        style.configure("TButton", background="#1b2140", foreground=text,
                        bordercolor="#343b76", lightcolor="#1b2140", darkcolor="#1b2140",
                        padding=(12, 8), relief="flat", font=("Segoe UI Semibold", 9))
        style.map("TButton",
                  background=[("disabled", "#171b31"), ("pressed", "#1b1746"),
                              ("active", "#30216f")],
                  foreground=[("disabled", "#61738b"), ("active", "#ffffff")],
                  bordercolor=[("active", accent)])
        style.configure("Accent.TButton", background="#6528e8", foreground="#ffffff",
                        bordercolor="#8559ff", lightcolor="#6528e8", darkcolor="#6528e8",
                        padding=(14, 9), relief="flat",
                        font=("Segoe UI Semibold", 9))
        style.map("Accent.TButton",
                  background=[("disabled", "#2c2747"), ("pressed", "#4d1fc3"),
                              ("active", "#7c48ff")],
                  foreground=[("disabled", "#91a5bf"), ("!disabled", "#ffffff")])

        style.configure("TNotebook", background=bg, bordercolor=border,
                        tabmargins=(2, 5, 2, 0), lightcolor=bg, darkcolor=bg)
        style.configure("TNotebook.Tab", background="#17263a", foreground=muted,
                        padding=(13, 8), bordercolor=border,
                        font=("Segoe UI Semibold", 9))
        style.map("TNotebook.Tab",
                  background=[("selected", "#203a58"), ("active", "#1b3049")],
                  foreground=[("selected", "#ffffff"), ("active", text)],
                  expand=[("selected", (1, 1, 1, 0))])

        style.configure("Treeview", background=surface, fieldbackground=surface,
                        foreground=text, bordercolor=border, rowheight=27,
                        font=("Segoe UI", 9))
        style.configure("Treeview.Heading", background="#20324a", foreground=text,
                        relief="flat", padding=(8, 7),
                        font=("Segoe UI Semibold", 9))
        style.map("Treeview",
                  background=[("selected", "#24558a")],
                  foreground=[("selected", "#ffffff")])
        style.map("Treeview.Heading", background=[("active", "#2b4564")])

        style.configure("TEntry", fieldbackground="#0e1929", foreground=text,
                        insertcolor=text, bordercolor=border, lightcolor=border,
                        darkcolor=border, padding=7)
        style.map("TEntry", bordercolor=[("focus", accent)])
        style.configure("TScrollbar", background="#20324a", troughcolor="#0e1929",
                        bordercolor=bg, arrowcolor=muted, gripcount=0)
        style.map("TScrollbar", background=[("active", "#355477")])
        style.configure("TPanedwindow", background=bg, sashrelief="flat")
        style.configure("Horizontal.TProgressbar", troughcolor="#0e1929",
                        background=accent, bordercolor=border, lightcolor=accent,
                        darkcolor=accent)
        style.configure("Accent.Horizontal.TProgressbar", troughcolor="#202b45",
                        background="#21e98b", bordercolor="#343b76",
                        lightcolor="#21e98b", darkcolor="#21e98b")
        style.configure("Warning.Horizontal.TProgressbar", troughcolor="#202b45",
                        background="#f3c56b", bordercolor="#5a4a43",
                        lightcolor="#f3c56b", darkcolor="#f3c56b")
        style.configure("Failed.Horizontal.TProgressbar", troughcolor="#202b45",
                        background="#ff647c", bordercolor="#59334a",
                        lightcolor="#ff647c", darkcolor="#ff647c")

    def _build_layout(self) -> None:
        """Build the Orion-Core dashboard to match the supplied visual concept."""
        self.status = tk.StringVar(value="Ожидание запуска")
        self.root.title(f"Orion-Core | GPU Compatibility Analyzer {__version__}")
        outer = tk.Frame(self.root, bg="#080d1d")
        outer.pack(fill="both", expand=True)

        self._build_header(outer)
        self._build_footer(outer)

        body = tk.Frame(outer, bg="#080d1d")
        body.pack(fill="both", expand=True)

        self._build_sidebar(body)

        self.main_area = tk.Frame(body, bg="#080d1d")
        self.main_area.pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.main_area.rowconfigure(0, weight=1)
        self.main_area.columnconfigure(0, weight=1)

        self.page_host = tk.Frame(self.main_area, bg="#080d1d")
        self.page_host.grid(row=0, column=0, sticky="nsew")
        self.page_host.rowconfigure(0, weight=1)
        self.page_host.columnconfigure(0, weight=1)

        self.dashboard_page = tk.Frame(self.page_host, bg="#080d1d")
        self.details_page = tk.Frame(self.page_host, bg="#080d1d")
        for page in (self.dashboard_page, self.details_page):
            page.grid(row=0, column=0, sticky="nsew")

        self._build_dashboard_page(self.dashboard_page)
        self._build_details_page(self.details_page)
        self._build_console(self.main_area)

        self._navigate("Главная")

    def _build_header(self, parent: tk.Misc) -> None:
        header = tk.Frame(parent, bg="#090e21", height=76,
                          highlightthickness=1, highlightbackground="#252d58")
        header.pack(fill="x")
        header.pack_propagate(False)

        brand = tk.Frame(header, bg="#090e21")
        brand.pack(side="left", padx=(18, 10), fill="y")
        tk.Label(brand, text="✦", bg="#090e21", fg="#8b4dff",
                 font=("Segoe UI Symbol", 34, "bold")).pack(side="left", padx=(0, 12))
        title_block = tk.Frame(brand, bg="#090e21")
        title_block.pack(side="left", pady=10)
        tk.Label(title_block, text="Orion-Core", bg="#090e21", fg="#f5f6ff",
                 font=("Segoe UI Semibold", 22)).pack(anchor="w")
        tk.Label(title_block, text=f"GPU Compatibility Analyzer  v{__version__}",
                 bg="#090e21", fg="#aab5d6", font=("Segoe UI", 9)).pack(anchor="w")

        self.header_status = tk.StringVar(value="ГОТОВО")
        status = tk.Frame(header, bg="#090e21")
        status.pack(side="right", padx=24)
        tk.Label(status, text="●", bg="#090e21", fg="#18e58a",
                 font=("Segoe UI", 14)).pack(side="left", padx=(0, 8))
        tk.Label(status, textvariable=self.header_status, bg="#090e21",
                 fg="#e6eaff", font=("Segoe UI Semibold", 10)).pack(side="left")

    def _build_sidebar(self, parent: tk.Misc) -> None:
        sidebar = tk.Frame(parent, bg="#0b1025", width=166,
                           highlightthickness=1, highlightbackground="#242b55")
        sidebar.pack(side="left", fill="y", padx=(0, 10))
        sidebar.pack_propagate(False)

        nav_items = (
            ("⌂", "Главная"),
            ("▣", "GPU"),
            ("⊗", "DirectX 12"),
            ("✣", "Шейдеры"),
            ("◈", "Текстуры"),
            ("⚙", "Конвейер"),
            ("⬡", "Совместимость"),
            ("▤", "Отчёт"),
            ("⚙", "Настройки"),
            ("♙", "О программе"),
        )
        self.nav_buttons: dict[str, tk.Button] = {}
        tk.Label(sidebar, text="НАВИГАЦИЯ", bg="#0b1025", fg="#65749e",
                 font=("Segoe UI Semibold", 8)).pack(anchor="w", padx=16, pady=(18, 12))
        for icon, name in nav_items:
            button = tk.Button(
                sidebar, text=f"  {icon}   {name}", anchor="w",
                command=lambda item=name: self._navigate(item),
                bg="#0b1025", fg="#c4cce7", activebackground="#24165d",
                activeforeground="#ffffff", relief="flat", bd=0,
                padx=12, pady=10, cursor="hand2",
                font=("Segoe UI Semibold", 9),
            )
            button.pack(fill="x", padx=6, pady=2)
            self.nav_buttons[name] = button
        tk.Frame(sidebar, bg="#27234f", height=1).pack(fill="x", padx=12, pady=(16, 10))
        tk.Label(sidebar, text="READ-ONLY MODE", bg="#0b1025", fg="#7e8aac",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16)
        tk.Label(sidebar, text="Файлы не запускаются\nи не изменяются",
                 bg="#0b1025", fg="#687698", justify="left",
                 font=("Segoe UI", 8)).pack(anchor="w", padx=16, pady=(5, 0))

    def _panel(self, parent: tk.Misc, title: str, icon: str = "") -> tuple[tk.Frame, tk.Frame]:
        panel = tk.Frame(parent, bg="#10172c", highlightthickness=1,
                         highlightbackground="#343b76", bd=0)
        heading = tk.Frame(panel, bg="#10172c", height=34)
        heading.pack(fill="x", padx=10, pady=(5, 0))
        heading.pack_propagate(False)
        if icon:
            tk.Label(heading, text=icon, bg="#10172c", fg="#55aaff",
                     font=("Segoe UI Symbol", 14, "bold")).pack(side="left", padx=(2, 8))
        tk.Label(heading, text=title, bg="#10172c", fg="#dce4ff",
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        body = tk.Frame(panel, bg="#10172c")
        body.pack(fill="both", expand=True, padx=10, pady=(3, 9))
        return panel, body

    def _build_dashboard_page(self, parent: tk.Misc) -> None:
        parent.grid_rowconfigure(1, weight=1)
        parent.grid_columnconfigure(0, weight=1)

        cards = tk.Frame(parent, bg="#080d1d")
        cards.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        for column, weight in enumerate((11, 13, 8, 12)):
            cards.grid_columnconfigure(column, weight=weight, uniform="summary")

        self.card_values: dict[str, tk.StringVar] = {
            "os": tk.StringVar(value="Не проверено"),
            "cpu": tk.StringVar(value="Не проверено"),
            "gpu": tk.StringVar(value="Не обнаружена"),
            "ram": tk.StringVar(value="Нет данных"),
        }
        self.system_os_var = self.card_values["os"]
        self.system_cpu_var = self.card_values["cpu"]
        self.system_ram_var = self.card_values["ram"]
        self.gpu_name_var = self.card_values["gpu"]
        self.gpu_memory_var = tk.StringVar(value="Память: нет данных")
        self.gpu_driver_var = tk.StringVar(value="Драйвер: нет данных")
        self.gpu_api_var = tk.StringVar(value="API: не проверено")
        self.dx12_summary_var = tk.StringVar(value="Не проверено")
        self.dx12_detail_var = tk.StringVar(value="D3D12 probe не запускался")
        self.verdict_var = tk.StringVar(value="Совместимость не определена")
        self.verdict_note_var = tk.StringVar(value="Сначала соберите данные системы")
        
        system_panel, system_body = self._panel(cards, "Информация о системе", "▣")
        system_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        for label, variable in (("ОС:", self.system_os_var), ("Процессор:", self.system_cpu_var),
                                ("ОЗУ:", self.system_ram_var)):
            line = tk.Frame(system_body, bg="#10172c")
            line.pack(fill="x", pady=3)
            tk.Label(line, text=label, width=11, anchor="w", bg="#10172c",
                     fg="#8997bc", font=("Segoe UI", 9)).pack(side="left")
            tk.Label(line, textvariable=variable, anchor="w", bg="#10172c",
                     fg="#f0f3ff", font=("Segoe UI Semibold", 9)).pack(side="left", fill="x", expand=True)

        gpu_panel, gpu_body = self._panel(cards, "Видеокарта", "▦")
        gpu_panel.grid(row=0, column=1, sticky="nsew", padx=3)
        tk.Label(gpu_body, textvariable=self.gpu_name_var, bg="#10172c",
                 fg="#f3f5ff", font=("Segoe UI Semibold", 13),
                 wraplength=260).pack(anchor="w", pady=(2, 5))
        for variable in (self.gpu_memory_var, self.gpu_driver_var, self.gpu_api_var):
            tk.Label(gpu_body, textvariable=variable, bg="#10172c", fg="#aebbdc",
                     font=("Segoe UI", 8)).pack(anchor="w", pady=1)

        dx_panel, dx_body = self._panel(cards, "DirectX 12", "⊗")
        dx_panel.grid(row=0, column=2, sticky="nsew", padx=3)
        tk.Label(dx_body, textvariable=self.dx12_summary_var, bg="#10172c",
                 fg="#e4eaff", font=("Segoe UI Semibold", 13),
                 justify="center").pack(fill="x", pady=(8, 3))
        tk.Label(dx_body, textvariable=self.dx12_detail_var, bg="#10172c",
                 fg="#91a5c8", font=("Segoe UI", 8), justify="center",
                 wraplength=180).pack(fill="x")

        verdict_panel, verdict_body = self._panel(cards, "Общий вердикт", "⬡")
        verdict_panel.grid(row=0, column=3, sticky="nsew", padx=(6, 0))
        self.verdict_box = tk.Frame(verdict_body, bg="#172039",
                                    highlightthickness=1, highlightbackground="#5360a0")
        self.verdict_box.pack(fill="both", expand=True, padx=1, pady=2)
        tk.Label(self.verdict_box, text="◈", bg="#172039", fg="#7b64ff",
                 font=("Segoe UI Symbol", 24)).pack(side="left", padx=12)
        verdict_text = tk.Frame(self.verdict_box, bg="#172039")
        verdict_text.pack(side="left", fill="both", expand=True, pady=8)
        tk.Label(verdict_text, textvariable=self.verdict_var, bg="#172039",
                 fg="#dce4ff", font=("Segoe UI Semibold", 11),
                 wraplength=210, justify="left").pack(anchor="w")
        tk.Label(verdict_text, textvariable=self.verdict_note_var, bg="#172039",
                 fg="#9eaccd", font=("Segoe UI", 8),
                 wraplength=230, justify="left").pack(anchor="w", pady=(3, 0))

        middle = tk.Frame(parent, bg="#080d1d")
        middle.grid(row=1, column=0, sticky="nsew")
        middle.grid_columnconfigure(0, weight=20, uniform="middle")
        middle.grid_columnconfigure(1, weight=12, uniform="middle")
        middle.grid_columnconfigure(2, weight=10, uniform="middle")
        middle.grid_rowconfigure(0, weight=1)

        stages_panel, stages_body = self._panel(middle, "Этапы проверки", "▥")
        stages_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        stage_names = (
            "Сбор информации о системе",
            "Инвентаризация Windows и драйверов",
            "Проверка устройства DirectX 12",
            "Анализ шейдеров и форматов",
            "Инвентаризация текстур и ресурсов",
            "Проверка операций графического конвейера",
        )
        self.stage_vars: list[tk.StringVar] = []
        self.stage_bars: list[ttk.Progressbar] = []
        self.stage_icons: list[tk.Label] = []
        self.stage_details: list[tk.Label] = []
        for index, name in enumerate(stage_names):
            row = tk.Frame(stages_body, bg="#10172c")
            row.pack(fill="x", pady=4)
            icon = tk.Label(row, text="○", width=2, bg="#10172c", fg="#637191",
                            font=("Segoe UI", 13, "bold"))
            icon.pack(side="left", padx=(2, 7))
            self.stage_icons.append(icon)
            tk.Label(row, text=name, width=28, anchor="w", bg="#10172c",
                     fg="#dce4ff", font=("Segoe UI", 8)).pack(side="left")
            bar = ttk.Progressbar(row, maximum=100, value=0,
                                  style="Accent.Horizontal.TProgressbar")
            bar.pack(side="left", fill="x", expand=True, padx=(6, 8), ipady=2)
            self.stage_bars.append(bar)
            state = tk.StringVar(value="Ожидает")
            self.stage_vars.append(state)
            detail = tk.Label(row, textvariable=state, width=16, anchor="e",
                              bg="#10172c", fg="#7785a8",
                              font=("Segoe UI", 8))
            detail.pack(side="right", padx=(2, 1))
            self.stage_details.append(detail)

        metrics_panel, metrics_body = self._panel(middle, "Ключевые показатели", "⚙")
        metrics_panel.grid(row=0, column=1, sticky="nsew", padx=3)
        self.metric_vars = {
            "gpu_perf": tk.StringVar(value="Не измерялась"),
            "vram": tk.StringVar(value="Нет данных"),
            "feature": tk.StringVar(value="Не проверено"),
            "ray": tk.StringVar(value="Нет данных"),
            "mesh": tk.StringVar(value="Нет данных"),
        }
        metric_rows = (
            ("Производительность GPU", "gpu_perf"),
            ("Видеопамять / бюджет", "vram"),
            ("DirectX Feature Level", "feature"),
            ("Ray Tracing", "ray"),
            ("Mesh Shaders", "mesh"),
        )
        for label, key in metric_rows:
            line = tk.Frame(metrics_body, bg="#10172c")
            line.pack(fill="x", pady=7)
            tk.Label(line, text="◆", bg="#10172c", fg="#54a6ff",
                     font=("Segoe UI", 11)).pack(side="left", padx=(2, 8))
            text_block = tk.Frame(line, bg="#10172c")
            text_block.pack(side="left", fill="x", expand=True)
            tk.Label(text_block, text=label, bg="#10172c", fg="#aab8da",
                     font=("Segoe UI", 8)).pack(anchor="w")
            tk.Label(text_block, textvariable=self.metric_vars[key], bg="#10172c",
                     fg="#f0f3ff", font=("Segoe UI Semibold", 9)).pack(anchor="w")

        graph_panel, graph_body = self._panel(middle, "Графический тест", "▣")
        graph_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self.probe_canvas = tk.Canvas(graph_body, bg="#050a16", height=108,
                                      highlightthickness=1, highlightbackground="#29375f")
        self.probe_canvas.pack(fill="x", pady=(2, 8))
        self.probe_canvas.create_line(0, 27, 400, 27, fill="#101c34")
        self.probe_canvas.create_line(0, 54, 400, 54, fill="#101c34")
        self.probe_canvas.create_line(0, 81, 400, 81, fill="#101c34")
        self.probe_canvas.create_line(65, 0, 65, 110, fill="#101c34")
        self.probe_canvas.create_line(130, 0, 130, 110, fill="#101c34")
        self.probe_canvas.create_line(195, 0, 195, 110, fill="#101c34")
        self.probe_canvas.create_line(260, 0, 260, 110, fill="#101c34")
        self.probe_canvas.create_oval(150, 25, 190, 65, outline="#5a4aa8", width=2)
        self.probe_canvas.create_text(170, 45, text="GPU", fill="#a89bff",
                                     font=("Segoe UI Semibold", 10))
        self.probe_state_var = tk.StringVar(value="Нативный тест не запускался")
        tk.Label(graph_body, textvariable=self.probe_state_var, bg="#10172c",
                 fg="#aab8da", font=("Segoe UI", 8), wraplength=230,
                 justify="center").pack(fill="x", pady=(0, 5))
        self.gpu_button = ttk.Button(graph_body, text="Выбрать D3D12 Probe…",
                                     command=self.choose_gpu_probe)
        self.gpu_button.pack(fill="x")

    def _build_details_page(self, parent: tk.Misc) -> None:
        self.overview_text = tk.StringVar(
            value="Запустите диагностику, чтобы получить сведения о системе."
        )
        self.detail_notebook = ttk.Notebook(parent)
        self.detail_notebook.pack(fill="both", expand=True, padx=2, pady=2)
        self.detail_views: dict[str, tk.Text] = {}
        for tab_name in ("Обзор", "Анализ игры", "CPU и память", "GPU / D3D12",
                         "Совместимость", "История", "Настройки", "О программе"):
            tab = tk.Frame(self.detail_notebook, bg="#10172c")
            text_view = tk.Text(tab, bg="#0b1221", fg="#e4eaff",
                                insertbackground="#ffffff", relief="flat",
                                wrap="word", font=("Consolas", 10),
                                padx=10, pady=10, state="disabled")
            text_view.pack(fill="both", expand=True, padx=8, pady=8)
            self.detail_notebook.add(tab, text=tab_name)
            self.detail_views[tab_name] = text_view

        self.game_inspection_report = None
        self._set_detail(
            "Анализ игры",
            "Выберите папку игры, EXE/DLL или образ ISO/XISO. Анализ выполняется локально, "
            "только для чтения; файлы не запускаются и не распаковываются."
        )
        game_tab = self.detail_notebook.nametowidget(self.detail_notebook.tabs()[1])
        game_controls = tk.Frame(game_tab, bg="#10172c")
        game_controls.pack(fill="x", padx=8, pady=(8, 0), before=self.detail_views["Анализ игры"])
        tk.Label(game_controls, text="Файл или папка игры:", bg="#10172c",
                 fg="#b8c5e5", font=("Segoe UI", 9)).pack(side="left")
        self.game_path = tk.StringVar()
        ttk.Entry(game_controls, textvariable=self.game_path).pack(
            side="left", fill="x", expand=True, padx=8
        )
        ttk.Button(game_controls, text="Папка…", command=self.choose_game_folder).pack(side="left")
        ttk.Button(game_controls, text="Файл…", command=self.choose_game_file).pack(
            side="left", padx=(5, 0)
        )
        self.game_button = ttk.Button(
            game_controls, text="Анализировать", style="Accent.TButton",
            command=self.start_game_inspection
        )
        self.game_button.pack(side="left", padx=(8, 0))
        ttk.Button(game_controls, text="Экспорт JSON",
                   command=self.export_game_report).pack(side="left", padx=8)
        self.game_progress = ttk.Progressbar(game_controls, mode="indeterminate", length=110)
        self.game_progress.pack(side="right", padx=(8, 0))

        dependency_panel = tk.Frame(game_tab, bg="#10172c")
        dependency_panel.pack(fill="both", expand=True, padx=8, pady=(8, 0),
                              before=self.detail_views["Анализ игры"])
        dependency_header = tk.Frame(dependency_panel, bg="#10172c")
        dependency_header.pack(fill="x", pady=(0, 6))
        tk.Label(dependency_header, text="ТАБЛИЦА ЗАВИСИМОСТЕЙ",
                 bg="#10172c", fg="#6ab4ff",
                 font=("Segoe UI Semibold", 9)).pack(side="left")
        self.dependency_filter = tk.StringVar()
        filter_entry = ttk.Entry(dependency_header, textvariable=self.dependency_filter, width=28)
        filter_entry.pack(side="right")
        tk.Label(dependency_header, text="Поиск DLL / API:",
                 bg="#10172c", fg="#aab8da",
                 font=("Segoe UI", 8)).pack(side="right", padx=(0, 6))
        filter_entry.bind("<KeyRelease>", self._filter_dependency_tree)
        tree_frame = tk.Frame(dependency_panel, bg="#10172c")
        tree_frame.pack(fill="both", expand=True)
        columns = ("module", "classification", "kind", "symbols", "resolution")
        self.dependency_tree = ttk.Treeview(
            tree_frame, columns=columns, show="headings", height=7
        )
        for column, title, width in (
            ("module", "Модуль DLL", 190), ("classification", "Класс", 170),
            ("kind", "Импорт", 100), ("symbols", "Функции", 75),
            ("resolution", "Локальная сверка", 155),
        ):
            self.dependency_tree.heading(column, text=title)
            self.dependency_tree.column(
                column, width=width, minwidth=60, stretch=column == "module"
            )
        tree_scroll = ttk.Scrollbar(tree_frame, orient="vertical",
                                    command=self.dependency_tree.yview)
        self.dependency_tree.configure(yscrollcommand=tree_scroll.set)
        self.dependency_tree.pack(side="left", fill="both", expand=True)
        tree_scroll.pack(side="right", fill="y")
        self.dependency_tree.bind("<<TreeviewSelect>>", self._on_dependency_selected)
        self.dependency_rows = []
        self.dependency_selection = tk.StringVar(
            value="Выберите DLL в таблице, чтобы увидеть подробности."
        )
        tk.Label(dependency_panel, textvariable=self.dependency_selection,
                 bg="#10172c", fg="#9eaccd", wraplength=1000,
                 justify="left", font=("Segoe UI", 8)).pack(anchor="w", pady=(6, 0))

        self._set_detail("Обзор", "Запустите диагностику, чтобы получить сведения о системе.")
        self._set_detail("CPU и память", "Данные появятся после системной диагностики.")
        self._set_detail("GPU / D3D12", "Выберите собранный D3D12 probe для runtime-проверки.")
        self._set_detail(
            "Совместимость",
            "Каталог содержит документированные контракты платформ, а не оценку конкретной игры."
        )
        self._set_detail("История", "Нажмите «История», чтобы просмотреть сохранённые снимки.")
        self._set_detail(
            "Настройки",
            "Orion-Core работает в режиме исследования и чтения. "
            "Этот раздел будет расширен настройками интерфейса и поведения."
        )
        self._set_detail(
            "О программе",
            f"Orion-Core {__version__}\nGPU Compatibility Analyzer\n\n"
            "Инструмент системной диагностики и анализа метаданных игровых файлов. "
            "Не является эмулятором Xbox и не гарантирует совместимость игр."
        )

    def _build_console(self, parent: tk.Misc) -> None:
        console_panel = tk.Frame(parent, bg="#090f20", height=205,
                                 highlightthickness=1, highlightbackground="#343b76")
        console_panel.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        console_panel.grid_propagate(False)
        header = tk.Frame(console_panel, bg="#10172c", height=34)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text="▣  Консоль выполнения", bg="#10172c",
                 fg="#dce4ff", font=("Segoe UI Semibold", 9)).pack(side="left", padx=10)
        tk.Label(header, text="INFO   •   SUCCESS   •   WARNING   •   ERROR",
                 bg="#10172c", fg="#8292b7",
                 font=("Segoe UI", 8)).pack(side="left", padx=16)
        ttk.Button(header, text="Очистить", command=self.clear_console).pack(
            side="right", padx=(4, 8), pady=3
        )
        ttk.Button(header, text="Сохранить лог", command=self.save_log).pack(
            side="right", padx=4, pady=3
        )
        console_body = tk.Frame(console_panel, bg="#050a14")
        console_body.pack(fill="both", expand=True, padx=5, pady=(0, 5))
        self.console = tk.Text(
            console_body, bg="#050a14", fg="#dce6ff",
            insertbackground="#ffffff", relief="flat", wrap="word",
            font=("Consolas", 9), state="disabled",
            padx=8, pady=5, borderwidth=0
        )
        self.console.tag_configure("INFO", foreground="#58c8ff")
        self.console.tag_configure("SUCCESS", foreground="#43ed91")
        self.console.tag_configure("WARNING", foreground="#f4c76b")
        self.console.tag_configure("ERROR", foreground="#ff647c")
        self.console.tag_configure("DEFAULT", foreground="#dce6ff")
        scrollbar = ttk.Scrollbar(console_body, orient="vertical", command=self.console.yview)
        self.console.configure(yscrollcommand=scrollbar.set)
        self.console.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_footer(self, parent: tk.Misc) -> None:
        footer = tk.Frame(parent, bg="#090e21", height=52,
                          highlightthickness=1, highlightbackground="#252d58")
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        self.footer_state_var = tk.StringVar(value="Анализ ещё не запускался")
        tk.Label(footer, text="●", bg="#090e21", fg="#18e58a",
                 font=("Segoe UI", 13)).pack(side="left", padx=(14, 6))
        tk.Label(footer, textvariable=self.status, bg="#090e21",
                 fg="#aebbe0", font=("Segoe UI", 9)).pack(side="left")
        tk.Label(footer, textvariable=self.footer_state_var, bg="#090e21",
                 fg="#7f8fb4", font=("Segoe UI", 8)).pack(side="left", padx=(16, 0))
        ttk.Button(footer, text="История",
                   command=lambda: self._show_details("История", update_nav=False)).pack(
                       side="right", padx=4, pady=7
                   )
        ttk.Button(footer, text="Сохранить снимок",
                   command=self.save_history).pack(side="right", padx=4, pady=7)
        ttk.Button(footer, text="Экспорт отчёта",
                   command=self.export_report).pack(side="right", padx=4, pady=7)
        self.scan_button = ttk.Button(
            footer, text="▶  Запустить проверку",
            style="Accent.TButton", command=self.start_scan
        )
        self.scan_button.pack(side="right", padx=4, pady=7)

    def _navigate(self, destination: str) -> None:
        """Switch between the home dashboard and the existing detailed report views."""
        routes = {
            "GPU": "GPU / D3D12",
            "DirectX 12": "GPU / D3D12",
            "Шейдеры": "Анализ игры",
            "Текстуры": "Анализ игры",
            "Конвейер": "GPU / D3D12",
            "Совместимость": "Совместимость",
            "Отчёт": "Обзор",
            "Настройки": "Настройки",
            "О программе": "О программе",
        }
        for name, button in self.nav_buttons.items():
            selected = name == destination
            button.configure(
                bg="#28146c" if selected else "#0b1025",
                fg="#ffffff" if selected else "#c4cce7",
                activebackground="#302078" if selected else "#17203d",
            )
        if destination == "Главная":
            self.dashboard_page.tkraise()
            return
        tab_name = routes.get(destination, "Обзор")
        self._show_details(tab_name, update_nav=False)

    def _show_details(self, tab_name: str, update_nav: bool = True) -> None:
        self.details_page.tkraise()
        if tab_name in self.detail_views:
            tabs = self.detail_notebook.tabs()
            index = list(self.detail_views).index(tab_name)
            if index < len(tabs):
                self.detail_notebook.select(tabs[index])
        if update_nav:
            tab_to_nav = {
                "Анализ игры": "Шейдеры",
                "GPU / D3D12": "GPU",
                "Обзор": "Отчёт",
            }
            nav_name = tab_to_nav.get(tab_name)
            if nav_name and nav_name in self.nav_buttons:
                self._navigate(nav_name)

    def _set_stage(self, index: int, state: str, detail: str = "") -> None:
        if not 0 <= index < len(self.stage_vars):
            return
        configs = {
            "complete": ("✓", 100, "#21e98b", "Готово", "Accent.Horizontal.TProgressbar"),
            "warning": ("!", 50, "#f3c56b", "Частично", "Warning.Horizontal.TProgressbar"),
            "running": ("◌", 35, "#59b5ff", "Выполняется", "Horizontal.TProgressbar"),
            "failed": ("×", 0, "#ff647c", "Ошибка", "Failed.Horizontal.TProgressbar"),
            "pending": ("○", 0, "#687697", "Ожидает", "Horizontal.TProgressbar"),
        }
        icon, value, color, label, style_name = configs.get(state, configs["pending"])
        self.stage_icons[index].configure(text=icon, fg=color)
        self.stage_bars[index].configure(value=value, style=style_name)
        self.stage_vars[index].set(detail or label)
        self.stage_details[index].configure(fg=color)

    def _set_detail(self, name: str, value: str) -> None:
        widget = self.detail_views[name]
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", value)
        widget.configure(state="disabled")
    def _log(self, level: str, message: str) -> None:
        stamp = datetime.now().astimezone().strftime("%H:%M:%S")
        line = f"[{stamp}] [{level}] {message}"
        self.log_lines.append(line)
        self.console.configure(state="normal")
        self.console.insert("end", line + "\n", level)
        self.console.see("end")
        self.console.configure(state="disabled")

    def _emit(self, level: str, message: str) -> None:
        self.events.put(("log", (level, message)))

    def start_scan(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        self.scan_button.configure(state="disabled")
        self._scan_success = False
        self.report = None
        self.gpu_report = None
        self.game_inspection_report = None
        for index in range(len(self.stage_vars)):
            self._set_stage(index, "pending")
        self.dx12_summary_var.set("Не проверено")
        self.dx12_detail_var.set("D3D12 probe не запускался")
        self.gpu_api_var.set("API: не проверено")
        self.verdict_var.set("Совместимость не определена")
        self.verdict_note_var.set("Ожидается сбор данных системы")
        self.probe_state_var.set("Нативный тест не запускался")
        self.metric_vars["gpu_perf"].set("Не измерялась")
        self.metric_vars["vram"].set("Нет данных")
        self.metric_vars["feature"].set("Не проверено")
        self.metric_vars["ray"].set("Нет данных")
        self.metric_vars["mesh"].set("Нет данных")
        self.status.set("Выполняется диагностика…")
        self.header_status.set("СБОР ДАННЫХ")
        self.footer_state_var.set("Выполняется системная инвентаризация")
        self._set_stage(0, "running", "Сбор сведений об ОС, CPU и памяти")
        self._set_stage(1, "running", "Запрос Windows CIM / реестра")
        self.overview_text.set("Сбор системной информации. Смотрите подробные этапы в консоли.")
        self._log("INFO", "Запрошен запуск read-only диагностики.")
        self.worker = threading.Thread(target=self._scan_worker, daemon=True)
        self.worker.start()

    def _scan_worker(self) -> None:
        try:
            self._emit("INFO", "Этап 1/3: сбор сведений об ОС, архитектуре, CPU и памяти.")
            report = collect_diagnostics_report(include_windows=False)
            self._emit("SUCCESS", "Этап 1/3 завершён: базовая системная информация собрана.")
            self._emit("INFO", "Этап 2/3: запрос сведений Windows через CIM и реестр (только чтение).")
            from .windows_info import collect_windows_diagnostics
            report["windows_diagnostics"] = collect_windows_diagnostics()
            if report["windows_diagnostics"].get("supported"):
                self._emit("SUCCESS", "Этап 2/3 завершён: Windows-инвентаризация получена.")
            else:
                self._emit("WARNING", "Этап 2/3: Windows-инвентаризация недоступна на этой платформе.")
            self._emit("INFO", "Этап 3/3: формирование итогового диагностического отчёта.")
            self.events.put(("report", report))
            self._scan_success = True
            self._emit("SUCCESS", "Этап 3/3 завершён: отчёт сформирован.")
            self.events.put(("done", None))
        except Exception as exc:  # surfaced in the live console for diagnosis
            self._emit("ERROR", f"Диагностика прервана: {type(exc).__name__}: {exc}")
            self.events.put(("done", None))

    def _drain_events(self) -> None:
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "log":
                    self._log(*payload)
                elif kind == "report":
                    self.report = payload
                    self._update_dashboard(payload)
                elif kind == "done":
                    self.scan_button.configure(state="normal")
                    self.status.set("Готово" if self._scan_success else "Завершено с ошибкой")
                    self.header_status.set("ГОТОВО" if self._scan_success else "ЕСТЬ ОШИБКИ")
                    if not self._scan_success:
                        self.footer_state_var.set("Проверьте сообщения ERROR в консоли")
                elif kind == "game_report":
                    self.game_inspection_report = payload
                    self._render_game_report(payload)
                elif kind == "game_done":
                    self.game_button.configure(state="normal")
                    self.game_progress.stop()
                    self.status.set("Анализ игры завершён" if payload else "Анализ игры завершился с ошибкой")
                    if payload:
                        self.footer_state_var.set("Game Inspector сформировал отчёт; файлы не запускались")
                    else:
                        self._set_stage(3, "warning", "Анализ не завершён")
                        self._set_stage(4, "warning", "Анализ не завершён")
                elif kind == "gpu_report":
                    self.gpu_report = payload
                    adapters = payload.get("adapters", [])
                    hardware = [item for item in adapters if not item.get("software") and item.get("d3d12_device")]
                    if hardware:
                        self.card_values["gpu"].set(hardware[0]["name"])
                    if hardware:
                        adapter = hardware[0]
                        memory = adapter.get("video_memory", {}).get("local", {})
                        budget = memory.get("budget_bytes")
                        usage = memory.get("current_usage_bytes")
                        memory_line = (
                            f"Локальная видеопамять: бюджет {budget / (1024 ** 3):.2f} ГиБ, "
                            f"занято {usage / (1024 ** 3):.2f} ГиБ."
                            if isinstance(budget, int) and isinstance(usage, int)
                            else "Локальная видеопамять: данные бюджета недоступны."
                        )
                        tests = (
                            ("Очередь/fence", adapter.get("direct_queue_fence_test")),
                            ("Копирование/readback", adapter.get("resource_copy_smoke_test")),
                            ("Root signature", adapter.get("root_signature_smoke_test")),
                            ("Рендер/readback", adapter.get("render_smoke_test")),
                        )
                        test_lines = "\n".join(
                            f"{label}: {'OK' if value is True else 'ОШИБКА' if value is False else 'НЕТ ДАННЫХ'}"
                            for label, value in tests
                        )
                        details = (
                            f"GPU: {adapter['name']}\n"
                            f"Feature Level: {adapter.get('feature_level', 'unknown')} | "
                            f"Shader Model: {adapter.get('shader_model', 'unknown')} | "
                            f"Binding Tier: {adapter.get('resource_binding_tier', 'unknown')}\n"
                            f"{memory_line}\n{test_lines}\n\n"
                            "Это Windows D3D12 runtime-проверка, а не подтверждение совместимости Xbox-игр."
                        )
                    else:
                        details = (
                            "D3D12-отчёт получен, но аппаратный адаптер не прошёл создание D3D12 device. "
                            "Совместимость Xbox-игр не устанавливается."
                        )
                    self.overview_text.set(details)
                    self._set_detail("GPU / D3D12", details)
                    self._set_detail("Обзор", details)
                    self._update_gpu_dashboard(payload)
                    self._show_details("GPU / D3D12", update_nav=True)
                elif kind == "gpu_done":
                    self.scan_button.configure(state="normal")
                    self.gpu_button.configure(state="normal")
                    self.status.set("D3D12-тест завершён" if payload else "D3D12-тест завершился с ошибкой")
                    self.header_status.set("D3D12 ГОТОВ" if payload else "D3D12 ОШИБКА")
                    if not payload:
                        self._set_stage(2, "failed", "Не удалось завершить D3D12 probe")
                        self._set_stage(5, "warning", "GPU операции не подтверждены")
                        self.footer_state_var.set("D3D12 probe завершился с ошибкой; подробности в консоли")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _update_dashboard(self, report: dict[str, Any]) -> None:
        system = report.get("system", {})
        os_info = system.get("os", {})
        os_label = f"{os_info.get('system', 'ОС не определена')} {os_info.get('release', '')}".strip()
        self.card_values["os"].set(os_label)

        win = report.get("windows_diagnostics", {})
        hardware = win.get("hardware", {})
        cpu_info = hardware.get("cpu") or {}
        cpu = cpu_info.get("Name") or system.get("processor") or "Модель не сообщена ОС"
        self.card_values["cpu"].set(str(cpu))

        gpus = hardware.get("gpus") or []
        gpu_name = str(gpus[0].get("Name") or "Не обнаружена") if gpus else "Нет данных"
        self.card_values["gpu"].set(gpu_name)
        if gpus:
            gpu = gpus[0]
            driver = gpu.get("DriverVersion") or gpu.get("Driver")
            memory_bytes = gpu.get("AdapterRAM") or gpu.get("DedicatedVideoMemory")
            self.gpu_driver_var.set(f"Драйвер: {driver}" if driver else "Драйвер: не сообщён ОС")
            if isinstance(memory_bytes, (int, float)) and memory_bytes > 0:
                self.gpu_memory_var.set(f"Память: {memory_bytes / (1024 ** 3):.1f} GiB (по данным ОС)")
            else:
                self.gpu_memory_var.set("Память: данные ОС не сообщила")
        else:
            self.gpu_driver_var.set("Драйвер: нет данных")
            self.gpu_memory_var.set("Память: нет данных")

        memory = system.get("memory_total_bytes")
        self.card_values["ram"].set(
            f"{memory / (1024 ** 3):.1f} GiB" if isinstance(memory, (int, float)) and memory > 0 else "Нет данных"
        )
        self.gpu_api_var.set("API: D3D12 runtime не проверен")
        self.verdict_var.set("Совместимость не определена")
        self.verdict_note_var.set("Собрана информация об оборудовании; нужна отдельная проверка API и самой игры")
        self.dx12_summary_var.set("Не проверено")
        self.dx12_detail_var.set("Системная инвентаризация не заменяет D3D12 runtime probe")
        self.metric_vars["vram"].set("Нет данных")
        self.metric_vars["feature"].set("Не проверено")
        self.metric_vars["gpu_perf"].set("Не измерялась")
        self.overview_text.set(
            "Инвентаризация завершена. Это отчёт о системе, а не подтверждение совместимости конкретной игры. "
            "Для проверки D3D12 выберите отдельный native probe; анализ игровых файлов выполняется отдельно."
        )
        self._set_detail("Обзор", self.overview_text.get())
        memory_text = f"{memory / (1024 ** 3):.2f} GiB" if isinstance(memory, (int, float)) else "Нет данных"
        self._set_detail(
            "CPU и память",
            f"CPU: {cpu}\nЯдер: {cpu_info.get('NumberOfCores', '—')}\n"
            f"Потоков: {cpu_info.get('NumberOfLogicalProcessors', '—')}\nRAM: {memory_text}"
        )
        self._set_detail(
            "Совместимость",
            "Каталог платформ описывает документированные API-контракты Windows PC и Xbox. "
            "Он не подтверждает совместимость конкретной игры, её бинарного файла или аппаратной конфигурации."
        )
        self._set_stage(0, "complete", "Системная информация собрана")
        if win.get("supported"):
            self._set_stage(1, "complete", "Windows-данные получены")
        else:
            self._set_stage(1, "warning", "Инвентаризация Windows недоступна")
        self.footer_state_var.set("Системный отчёт сформирован; игровые и GPU-тесты ещё не запускались")
        self.header_status.set("СИСТЕМА ПРОВЕРЕНА")
        self._log(
            "SUCCESS",
            f"Система: {os_label}; CPU: {cpu}; GPU: {self.card_values['gpu'].get()}."
        )

    def _update_gpu_dashboard(self, payload: dict[str, Any]) -> None:
        adapters = payload.get("adapters", [])
        hardware = [
            item for item in adapters
            if not item.get("software") and item.get("d3d12_device")
        ]
        if not hardware:
            self.dx12_summary_var.set("Устройство не создано")
            self.dx12_detail_var.set("Аппаратный D3D12 device не подтверждён")
            self.gpu_api_var.set("API: аппаратная проверка не пройдена")
            self.verdict_var.set("Недостаточно данных")
            self.verdict_note_var.set("D3D12 probe не подтвердил создание аппаратного устройства")
            self.probe_state_var.set("D3D12 runtime: аппаратный адаптер не прошёл проверку")
            self._set_stage(2, "warning", "Аппаратный D3D12 device не создан")
            self._set_stage(5, "warning", "Операции GPU не подтверждены")
            self.metric_vars["feature"].set("Нет аппаратного device")
            self.metric_vars["vram"].set("Нет данных")
            self._log("WARNING", "D3D12 probe не подтвердил аппаратное устройство.")
            return

        adapter = hardware[0]
        feature = adapter.get("feature_level", "неизвестен")
        shader_model = adapter.get("shader_model", "неизвестна")
        self.card_values["gpu"].set(str(adapter.get("name") or self.card_values["gpu"].get()))
        self.dx12_summary_var.set("D3D12 device создан")
        self.dx12_detail_var.set(f"Feature Level: {feature} · Shader Model: {shader_model}")
        self.gpu_api_var.set(f"API: Direct3D 12 · FL {feature}")
        self.metric_vars["feature"].set(str(feature))
        self.metric_vars["gpu_perf"].set("Бенчмарк не запускался")
        memory = adapter.get("video_memory", {}).get("local", {})
        budget = memory.get("budget_bytes")
        usage = memory.get("current_usage_bytes")
        if isinstance(budget, int):
            self.metric_vars["vram"].set(
                f"Бюджет {budget / (1024 ** 3):.2f} GiB" +
                (f" · занято {usage / (1024 ** 3):.2f} GiB" if isinstance(usage, int) else "")
            )
        else:
            self.metric_vars["vram"].set("Бюджет недоступен")
        self.metric_vars["ray"].set(str(adapter.get("ray_tracing_tier") or "Нет данных"))
        self.metric_vars["mesh"].set(str(adapter.get("mesh_shader_tier") or "Нет данных"))
        tests = (
            adapter.get("direct_queue_fence_test"),
            adapter.get("resource_copy_smoke_test"),
            adapter.get("root_signature_smoke_test"),
            adapter.get("render_smoke_test"),
        )
        passed = sum(value is True for value in tests)
        failed = sum(value is False for value in tests)
        self.probe_state_var.set(
            f"GPU runtime smoke tests: {passed}/{len(tests)} успешно; ошибок: {failed}. "
            "Это не игровой бенчмарк."
        )
        self._set_stage(2, "complete", f"D3D12 device создан · FL {feature}")
        self._set_stage(5, "complete" if failed == 0 and passed == len(tests) else "warning",
                        f"GPU smoke tests: {passed}/{len(tests)}")
        self.verdict_var.set("D3D12 runtime проверен")
        self.verdict_note_var.set("Это результат аппаратной проверки API, а не вердикт о совместимости Xbox-игр")
        self.footer_state_var.set("Аппаратный D3D12 probe обработан; совместимость игр не устанавливается")
        self.header_status.set("D3D12 ПРОВЕРЕН")
        self._log("SUCCESS", f"D3D12 device: {adapter.get('name', 'GPU')}, Feature Level {feature}; smoke tests {passed}/{len(tests)}.")



    def choose_game_folder(self) -> None:
        path = filedialog.askdirectory(title="Выберите папку игры")
        if path:
            self.game_path.set(path)

    def choose_game_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Выберите EXE, DLL или образ игры",
            filetypes=[("Поддерживаемые файлы", "*.exe *.dll *.iso *.xiso *.xex *.zip"),
                       ("Все файлы", "*.*")],
        )
        if path:
            self.game_path.set(path)

    def _filter_dependency_tree(self, _event: Any = None) -> None:
        query = self.dependency_filter.get().strip().casefold()
        for item in self.dependency_tree.get_children():
            self.dependency_tree.delete(item)
        for row in self.dependency_rows:
            haystack = (" ".join(str(value) for value in row["values"]) + " " + row["detail"]).casefold()
            if not query or query in haystack:
                self.dependency_tree.insert("", "end", iid=row["iid"], values=row["values"])

    def _on_dependency_selected(self, _event: Any = None) -> None:
        selected = self.dependency_tree.selection()
        if not selected:
            return
        row = next((item for item in self.dependency_rows if item["iid"] == selected[0]), None)
        if row:
            self.dependency_selection.set(row["detail"])

    def _populate_dependency_tree(self, report: dict[str, Any]) -> None:
        self.dependency_rows = []
        for record in report.get("files", []):
            deps = record.get("dependency_analysis") or {}
            resolution = deps.get("local_resolution", {})
            resolution_by_name = {item.get("module", "").casefold(): item for item in resolution.get("modules", [])}
            api_report = deps.get("api_catalog_assessment", {})
            api_by_name = {item.get("module", "").casefold(): item for item in api_report.get("modules", [])}
            for module in deps.get("modules", []):
                name = module.get("module", "")
                match = resolution_by_name.get(name.casefold(), {})
                status = match.get("status", "не выполнялась")
                status = {"candidate_file_found": "кандидат найден", "missing_module": "нет в папке",
                          "ambiguous_module": "неоднозначно", "architecture_mismatch": "архитектура не совпала"}.get(status, status)
                api_module = api_by_name.get(name.casefold(), {})
                known = [item for item in api_module.get("symbols", []) if item.get("status") == "known_win32_api_family"]
                symbol_count = len(module.get("symbols", []))
                kind = "Обычный" if module.get("normal_import") else ""
                if module.get("delay_load_import"):
                    kind = (kind + " + отложенный").strip(" +")
                details = [f"DLL: {name}", f"Классификация: {module.get('classification', '—')}",
                           f"Импорт: {kind or 'неизвестен'}", f"Функций в таблице: {symbol_count}",
                           f"Локальная сверка: {status}"]
                if match.get("candidate_path"):
                    details.append(f"Файл-кандидат: {match['candidate_path']}")
                if known:
                    details.append("Известные Win32 API семейства: " + ", ".join(sorted({x.get("family", "") for x in known})))
                imported_names = [item.get("name", "") for item in module.get("symbols", []) if item.get("kind") == "name"]
                if imported_names:
                    details.append("Импортируемые функции: " + ", ".join(imported_names))
                details.append("Маркировка Win32 API не означает эквивалентность Xbox API.")
                iid = f"dep_{len(self.dependency_rows)}"
                self.dependency_rows.append({"iid": iid, "values": (
                    name, module.get("classification", "—"), kind or "—", symbol_count, status
                ), "detail": " | ".join(details)})
        self._filter_dependency_tree()

    def start_game_inspection(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Orion-Core", "Дождитесь завершения текущей операции.")
            return
        path = self.game_path.get().strip()
        if not path:
            messagebox.showinfo("Orion-Core", "Сначала выберите файл или папку игры.")
            return
        self.game_button.configure(state="disabled")
        self.game_progress.start(12)
        self.status.set("Выполняется анализ игры…")
        self.header_status.set("АНАЛИЗ ИГРЫ")
        self._set_stage(3, "running", "Game Inspector обрабатывает файлы")
        self._set_stage(4, "running", "Инвентаризация ресурсов")
        self._set_detail("Анализ игры", "Анализ выполняется. Большие папки могут обрабатываться некоторое время.")
        self._log("INFO", f"Начат read-only анализ игрового материала: {path}")
        self.worker = threading.Thread(target=self._game_inspection_worker, args=(path,), daemon=True)
        self.worker.start()

    def _game_inspection_worker(self, path: str) -> None:
        try:
            self._emit("INFO", "Game Inspector: проверка структуры, форматов и PE-зависимостей.")
            report = inspect_game_path(path)
            self.events.put(("game_report", report))
            self._emit("SUCCESS", f"Game Inspector: найдено записей файлов: {report.get('files_inspected', 0)}.")
            self.events.put(("game_done", True))
        except (GameInspectionError, OSError, ValueError) as exc:
            self._emit("ERROR", f"Game Inspector: {type(exc).__name__}: {exc}")
            self.events.put(("game_done", False))
        except Exception as exc:
            self._emit("ERROR", f"Game Inspector: непредвиденная ошибка {type(exc).__name__}: {exc}")
            self.events.put(("game_done", False))

    def _render_game_report(self, report: dict[str, Any]) -> None:
        self._populate_dependency_tree(report)
        lines = [
            f"Источник: {report.get('source_name', '—')}",
            f"Тип: {report.get('source_kind', '—')}",
            f"Обработано записей: {report.get('files_inspected', 0)}",
            "",
            "Распределение форматов:",
        ]
        for kind, count in report.get("type_counts", {}).items():
            lines.append(f"  {kind}: {count}")
        files = report.get("files", [])
        pe_records = [item for item in files if item.get("pe_analysis")]
        lines.extend(["", f"PE-файлов с отчётом: {len(pe_records)}"])
        for item in pe_records:
            pe = item.get("pe_analysis") or {}
            deps = item.get("dependency_analysis") or {}
            scarlett = item.get("scarlett_analysis") or {}
            lines.extend([
                "",
                f"Файл: {item.get('path')}",
                f"  Архитектура: {pe.get('architecture', 'не определена')}",
                f"  Экспортируемых функций: {len(pe.get('exported_functions', []))}",
                f"  Импортируемых функций: {len(pe.get('imported_functions', []))}",
                f"  Xbox-модулей-подсказок: {deps.get('classification_counts', {}).get('xbox_platform_module_hint', 0)}",
                f"  Оценка Scarlett: {scarlett.get('assessment', 'не определена')}",
            ])
            resolution = deps.get("local_resolution", {})
            resolution_counts = resolution.get("counts", {})
            if resolution:
                lines.append(
                    "  Локальная сверка импортов: "
                    f"совпадений по имени {resolution_counts.get('resolved_name_match', 0)}, "
                    f"по ordinal {resolution_counts.get('resolved_ordinal_match', 0)}, "
                    f"перенаправленных {resolution_counts.get('forwarded_export', 0)}, "
                    f"отсутствующих DLL {resolution_counts.get('missing_module', 0)}, "
                    f"отсутствующих символов {resolution_counts.get('missing_symbol', 0)}, "
                    f"неоднозначных DLL {resolution_counts.get('ambiguous_module', 0)}."
                )
                for module_result in resolution.get("modules", []):
                    state = module_result.get("status", "")
                    if state != "candidate_file_found":
                        lines.append(f"    DLL {module_result.get('module')}: {state}")
                    for symbol_result in module_result.get("symbols", []):
                        if symbol_result.get("status") not in ("resolved_name_match", "resolved_ordinal_match"):
                            imported = symbol_result.get("import", {})
                            label = imported.get("name", f"ordinal #{imported.get('ordinal', '?')}")
                            lines.append(f"      {label}: {symbol_result.get('status')}")
            exports = pe.get("exported_functions", [])
            for exported in exports[:30]:
                names = ", ".join(exported.get("names", [])) or f"ordinal #{exported.get('ordinal')}"
                forward = f" → {exported.get('forwarder')}" if exported.get("is_forwarder") else ""
                lines.append(f"    EXPORT {names}{forward}")
            if len(exports) > 30:
                lines.append(f"    … ещё {len(exports) - 30} экспортов (полный список в JSON)")
        if report.get("warnings"):
            lines.extend(["", "Предупреждения:"] + [f"  • {warning}" for warning in report["warnings"]])
        lines.extend(["", "Ограничения: анализ только для чтения; исполняемые файлы не запускаются.",
                      "Локальное совпадение импорта с экспортом не доказывает ABI- или runtime-совместимость."])
        self._set_detail("Анализ игры", "\n".join(lines))
        type_counts = report.get("type_counts", {})
        shader_count = sum(
            count for kind, count in type_counts.items()
            if any(token in str(kind).casefold() for token in ("shader", "dxbc", "dxil", "spirv"))
        )
        if shader_count:
            self._set_stage(3, "complete", f"Обнаружены shader-ресурсы: {shader_count}")
        else:
            self._set_stage(3, "warning", "Шейдерные файлы не обнаружены в выбранном наборе")
        files_inspected = report.get("files_inspected", 0)
        if files_inspected:
            self._set_stage(4, "complete", f"Проверено файловых записей: {files_inspected}")
        else:
            self._set_stage(4, "warning", "Инвентаризация не вернула файловых записей")
        self._show_details("Анализ игры", update_nav=True)
        self._log("SUCCESS", "Отчёт Game Inspector отображён в интерфейсе.")

    def save_history(self) -> None:
        """Persist the most recent completed diagnostic or native GPU report."""
        if self.gpu_report is not None:
            report, kind = self.gpu_report, "native_d3d12_probe"
        elif self.report is not None:
            report, kind = self.report, "system_diagnostics"
        else:
            messagebox.showinfo("Orion-Core", "Сначала выполните системную диагностику или D3D12-тест.")
            return
        try:
            record = self.history_store.add_report(report, kind=kind)
        except (HistoryStoreError, OSError) as exc:
            self._log("ERROR", f"Не удалось сохранить историю: {type(exc).__name__}: {exc}")
            messagebox.showerror("Orion-Core", f"Не удалось сохранить результат: {exc}")
            return
        self._log("SUCCESS", f"Снимок сохранён в историю: {kind}, ID {record['id']}.")
        self.refresh_history()

    def refresh_history(self) -> None:
        """Render saved history metadata without loading every full report into the UI."""
        try:
            records = self.history_store.list_reports()
        except (HistoryStoreError, OSError) as exc:
            self._set_detail("История", f"Ошибка чтения истории: {type(exc).__name__}: {exc}")
            self._log("ERROR", f"История недоступна: {type(exc).__name__}: {exc}")
            return
        if not records:
            view = "История пока пуста. Выполните диагностику и нажмите «Сохранить в историю»."
        else:
            lines = [f"Сохранено снимков: {len(records)}", ""]
            for item in records:
                lines.append(f"{item['created_at']} | {item['kind']} | ID: {item['id']}")
            view = "\n".join(lines)
        self._set_detail("История", view)
        self._show_details("История", update_nav=False)
        self._log("INFO", f"История обновлена: записей {len(records)}.")

    def choose_gpu_probe(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Orion-Core", "Дождитесь завершения текущей операции.")
            return
        path = filedialog.askopenfilename(
            title="Выберите собранный native D3D12 probe",
            filetypes=[("Windows executable", "*.exe"), ("All files", "*.*")],
        )
        if not path:
            return
        if not path.lower().endswith(".exe"):
            messagebox.showerror("Orion-Core", "Выберите исполняемый файл .exe.")
            return
        self.gpu_button.configure(state="disabled")
        self.scan_button.configure(state="disabled")
        self.status.set("Выполняется нативный D3D12-тест…")
        self.header_status.set("D3D12 PROBE")
        self._set_stage(2, "running", "Создание D3D12 device и runtime-тесты")
        self._set_stage(5, "running", "Проверка очереди, ресурсов и рендера")
        self._log("WARNING", "D3D12 probe выполняет реальные read-only GPU-команды; сохраните работу перед запуском.")
        self._log("INFO", f"Запуск выбранного пользователем файла: {path}")
        self.worker = threading.Thread(target=self._gpu_probe_worker, args=(path,), daemon=True)
        self.worker.start()

    def _gpu_probe_worker(self, executable: str) -> None:
        try:
            self._emit("INFO", "D3D12: запуск процесса с аргументом --json; ожидание аппаратного отчёта.")
            process = subprocess.Popen(
                [executable, "--json"], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace", shell=False,
            )
            stdout_lines: list[str] = []

            def read_stdout() -> None:
                assert process.stdout is not None
                stdout_lines.extend(process.stdout.readlines())

            def read_stderr() -> None:
                assert process.stderr is not None
                for raw_line in process.stderr:
                    line = raw_line.strip()
                    if line.startswith("[ORION_PROGRESS]"):
                        self._emit("INFO", "D3D12: " + line.removeprefix("[ORION_PROGRESS]").strip())
                    elif line:
                        self._emit("WARNING", f"D3D12 stderr: {line[:500]}")

            stdout_thread = threading.Thread(target=read_stdout, daemon=True)
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stdout_thread.start()
            stderr_thread.start()
            try:
                return_code = process.wait(timeout=180)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                raise
            stdout_thread.join(timeout=5)
            stderr_thread.join(timeout=5)
            if return_code not in (0, 3):
                raise RuntimeError(f"probe завершился с кодом {return_code}")
            try:
                raw = json.loads("".join(stdout_lines))
            except json.JSONDecodeError as exc:
                raise ProbeReportError("probe не вернул корректный JSON в stdout") from exc
            report = validate_probe_report(raw)
            self.events.put(("gpu_report", report))
            self._emit("SUCCESS", f"D3D12: отчёт получен; аппаратных D3D12-адаптеров: {report.get('hardware_d3d12_adapters', 0)}.")
            if return_code == 3:
                self._emit("WARNING", "D3D12: совместимый аппаратный адаптер не создан (код 3).")
            self.events.put(("gpu_done", True))
        except subprocess.TimeoutExpired:
            self._emit("ERROR", "D3D12: превышено время ожидания 180 секунд.")
            self.events.put(("gpu_done", False))
        except Exception as exc:
            self._emit("ERROR", f"D3D12-тест не завершён: {type(exc).__name__}: {exc}")
            self.events.put(("gpu_done", False))

    def clear_console(self) -> None:
        self.console.configure(state="normal")
        self.console.delete("1.0", "end")
        self.console.configure(state="disabled")
        self.log_lines.clear()
        self._log("INFO", "Консоль очищена.")

    def save_log(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".log", filetypes=[("Log files", "*.log"), ("Text files", "*.txt")])
        if path:
            self._log("SUCCESS", f"Журнал сохранён: {path}")
            try:
                Path(path).write_text("\n".join(self.log_lines) + "\n", encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Orion-Core", f"Не удалось сохранить журнал: {exc}")

    def export_game_report(self) -> None:
        report = getattr(self, "game_inspection_report", None)
        if not report:
            messagebox.showinfo("Orion-Core", "Сначала выполните анализ игры.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            try:
                Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._log("SUCCESS", f"Отчёт Game Inspector экспортирован: {path}")
            except OSError as exc:
                messagebox.showerror("Orion-Core", f"Не удалось экспортировать отчёт: {exc}")

    def export_report(self) -> None:
        if not self.report:
            messagebox.showinfo("Orion-Core", "Сначала запустите диагностику.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if path:
            payload = {"system_diagnostics": self.report, "native_d3d12_probe": self.gpu_report}
            try:
                Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                self._log("SUCCESS", "Объединённый JSON-отчёт экспортирован.")
            except OSError as exc:
                messagebox.showerror("Orion-Core", f"Не удалось экспортировать отчёт: {exc}")

def main() -> None:
    root = tk.Tk()
    OrionDashboard(root)
    root.mainloop()


if __name__ == "__main__":
    main()
