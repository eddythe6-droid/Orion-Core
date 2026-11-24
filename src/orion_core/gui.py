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
        self.root.geometry("1180x780")
        self.root.minsize(900, 620)
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
        self.root.configure(bg="#101722")
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background="#101722")
        style.configure("Card.TFrame", background="#192535")
        style.configure("TLabel", background="#101722", foreground="#e7eef7", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 22), foreground="#f2f6fc")
        style.configure("Muted.TLabel", foreground="#9fb0c4")
        style.configure("CardTitle.TLabel", background="#192535", foreground="#9fb0c4", font=("Segoe UI", 9))
        style.configure("CardValue.TLabel", background="#192535", foreground="#f2f6fc", font=("Segoe UI Semibold", 15))
        style.configure("Accent.TButton", font=("Segoe UI Semibold", 10), padding=9)
        style.configure("TButton", padding=8)

    def _build_layout(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        ttk.Label(header, text="ORION-CORE", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="XBOX → WINDOWS COMPATIBILITY RESEARCH LAB", style="Muted.TLabel").pack(side="left", padx=18, pady=(9, 0))
        self.status = tk.StringVar(value="Ожидание запуска")
        ttk.Label(header, textvariable=self.status, style="Muted.TLabel").pack(side="right", pady=(9, 0))

        cards = ttk.Frame(outer)
        cards.pack(fill="x", pady=(0, 14))
        self.card_values: dict[str, tk.StringVar] = {}
        for key, title, initial in (
            ("os", "ОПЕРАЦИОННАЯ СИСТЕМА", "Не проверено"),
            ("cpu", "ПРОЦЕССОР", "Не проверено"),
            ("gpu", "ВИДЕОАДАПТЕР", "Не проверено"),
            ("ram", "ОПЕРАТИВНАЯ ПАМЯТЬ", "Не проверено"),
        ):
            card = ttk.Frame(cards, style="Card.TFrame", padding=12)
            card.pack(side="left", fill="both", expand=True, padx=(0, 8))
            ttk.Label(card, text=title, style="CardTitle.TLabel").pack(anchor="w")
            value = tk.StringVar(value=initial)
            self.card_values[key] = value
            ttk.Label(card, textvariable=value, style="CardValue.TLabel", wraplength=220).pack(anchor="w", pady=(7, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(0, 10))
        self.scan_button = ttk.Button(actions, text="▶  Запустить диагностику", style="Accent.TButton", command=self.start_scan)
        self.scan_button.pack(side="left")
        ttk.Button(actions, text="Сохранить лог", command=self.save_log).pack(side="left", padx=8)
        ttk.Button(actions, text="Экспорт отчёта JSON", command=self.export_report).pack(side="left")
        self.gpu_button = ttk.Button(actions, text="▶  Запустить D3D12-тест", command=self.choose_gpu_probe)
        self.gpu_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Сохранить в историю", command=self.save_history).pack(side="left", padx=8)
        ttk.Button(actions, text="История", command=self.refresh_history).pack(side="left")
        ttk.Button(actions, text="Очистить консоль", command=self.clear_console).pack(side="right")

        split = ttk.Panedwindow(outer, orient="vertical")
        split.pack(fill="both", expand=True)
        overview = ttk.Frame(split, style="Card.TFrame", padding=12)
        self.overview_text = tk.StringVar(value="Запустите диагностику, чтобы получить сведения о системе.")
        self.detail_notebook = ttk.Notebook(overview)
        self.detail_notebook.pack(fill="both", expand=True)
        self.detail_views = {}
        for tab_name in ("Обзор", "Анализ игры", "CPU и память", "GPU / D3D12", "Совместимость", "История"):
            tab = ttk.Frame(self.detail_notebook, padding=10)
            text_view = tk.Text(tab, bg="#192535", fg="#e7eef7", insertbackground="white", relief="flat", wrap="word", font=("Segoe UI", 10), state="disabled")
            text_view.pack(fill="both", expand=True)
            self.detail_notebook.add(tab, text=tab_name)
            self.detail_views[tab_name] = text_view
        self.game_inspection_report = None
        self._set_detail("Анализ игры", "Выберите папку игры, EXE/DLL или образ ISO/XISO. Анализ выполняется локально, только для чтения; файлы не запускаются и не распаковываются.")
        self.game_path = tk.StringVar()
        game_controls = ttk.Frame(self.detail_notebook.nametowidget(self.detail_notebook.tabs()[1]), padding=8)
        game_controls.pack(fill="x", before=self.detail_views["Анализ игры"])
        ttk.Label(game_controls, text="Файл или папка игры:").pack(side="left")
        ttk.Entry(game_controls, textvariable=self.game_path).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(game_controls, text="Обзор…", command=self.choose_game_path).pack(side="left")
        self.game_button = ttk.Button(game_controls, text="Анализировать", style="Accent.TButton", command=self.start_game_inspection)
        self.game_button.pack(side="left", padx=(8, 0))
        ttk.Button(game_controls, text="Экспорт JSON", command=self.export_game_report).pack(side="left", padx=8)
        self._set_detail("Обзор", "Запустите диагностику, чтобы получить сведения о системе.")
        self._set_detail("CPU и память", "Данные появятся после системной диагностики.")
        self._set_detail("GPU / D3D12", "Запустите D3D12 probe для подробного отчёта.")
        self._set_detail("Совместимость", "Каталог содержит документированные контракты платформ, а не оценку конкретной игры.")
        self._set_detail("История", "Нажмите «История», чтобы просмотреть сохранённые диагностические снимки.")
        console = ttk.Frame(split, style="Card.TFrame", padding=10)
        console_header = ttk.Frame(console, style="Card.TFrame")
        console_header.pack(fill="x", pady=(0, 7))
        ttk.Label(console_header, text="ЖУРНАЛ РАБОТЫ / LIVE CONSOLE", style="CardTitle.TLabel").pack(side="left")
        ttk.Label(console_header, text="INFO  •  SUCCESS  •  WARNING  •  ERROR", style="CardTitle.TLabel").pack(side="right")
        self.console = tk.Text(console, bg="#0b111a", fg="#d7e2ef", insertbackground="white",
                               relief="flat", wrap="word", font=("Consolas", 9), state="disabled")
        self.console.tag_configure("INFO", foreground="#78b7ff")
        self.console.tag_configure("SUCCESS", foreground="#62d69b")
        self.console.tag_configure("WARNING", foreground="#f3c969")
        self.console.tag_configure("ERROR", foreground="#ff7777")
        scrollbar = ttk.Scrollbar(console, orient="vertical", command=self.console.yview)
        self.console.configure(yscrollcommand=scrollbar.set)
        self.console.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        split.add(overview, weight=1)
        split.add(console, weight=4)

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
        self.status.set("Выполняется диагностика…")
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
                elif kind == "game_report":
                    self.game_inspection_report = payload
                    self._render_game_report(payload)
                elif kind == "game_done":
                    self.game_button.configure(state="normal")
                    self.status.set("Анализ игры завершён" if payload else "Анализ игры завершился с ошибкой")
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
                elif kind == "gpu_done":
                    self.scan_button.configure(state="normal")
                    self.gpu_button.configure(state="normal")
                    self.status.set("D3D12-тест завершён" if payload else "D3D12-тест завершился с ошибкой")
        except queue.Empty:
            pass
        self.root.after(100, self._drain_events)

    def _update_dashboard(self, report: dict[str, Any]) -> None:
        system = report["system"]
        os_info = system["os"]
        self.card_values["os"].set(f"{os_info['system']} {os_info['release']}")
        cpu = system.get("processor") or "Модель не сообщена ОС"
        win = report.get("windows_diagnostics", {})
        hardware = win.get("hardware", {})
        cpu_info = hardware.get("cpu") or {}
        cpu = cpu_info.get("Name") or cpu
        gpus = hardware.get("gpus") or []
        self.card_values["cpu"].set(str(cpu))
        self.card_values["gpu"].set(str(gpus[0].get("Name") or "Не обнаружена") if gpus else "Нет данных")
        memory = system.get("memory_total_bytes")
        self.card_values["ram"].set(f"{memory / (1024 ** 3):.1f} GiB" if memory else "Нет данных")
        self.overview_text.set(
            "Инвентаризация завершена. Это базовый отчёт о системе, а не проверка совместимости конкретной игры. "
            "Нативный D3D12 GPU-тест пока запускается отдельно и здесь не имитируется."
        )
        self._set_detail("Обзор", self.overview_text.get())
        win = report.get("windows_diagnostics", {})
        cpu_info = (win.get("hardware", {}).get("cpu") or {})
        memory_text = f"{memory / (1024 ** 3):.2f} GiB" if isinstance(memory, int) else "Нет данных"
        self._set_detail("CPU и память", f"CPU: {cpu}\nЯдер: {cpu_info.get('NumberOfCores', '—')}\nПотоков: {cpu_info.get('NumberOfLogicalProcessors', '—')}\nRAM: {memory_text}")
        self._set_detail("Совместимость", "Каталог платформ описывает документированные API-контракты Windows PC и Xbox. Он не подтверждает совместимость конкретной игры, её бинарного файла или аппаратной конфигурации.")
        self._log("SUCCESS", f"Система: {os_info['system']} {os_info['release']}; CPU: {cpu}; GPU: {self.card_values['gpu'].get()}.")



    def choose_game_path(self) -> None:
        path = filedialog.askdirectory(title="Выберите папку игры")
        if not path:
            path = filedialog.askopenfilename(
                title="Выберите EXE, DLL или образ игры",
                filetypes=[("Поддерживаемые файлы", "*.exe *.dll *.iso *.xiso *.xex *.zip"),
                           ("Все файлы", "*.*")],
            )
        if path:
            self.game_path.set(path)

    def start_game_inspection(self) -> None:
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Orion-Core", "Дождитесь завершения текущей операции.")
            return
        path = self.game_path.get().strip()
        if not path:
            messagebox.showinfo("Orion-Core", "Сначала выберите файл или папку игры.")
            return
        self.game_button.configure(state="disabled")
        self.status.set("Выполняется анализ игры…")
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
            lines.extend([
            ])
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
                      "Наличие DLL или экспортов не доказывает совместимость с Windows."])
        self._set_detail("Анализ игры", "\n".join(lines))
        self.detail_notebook.select(list(self.detail_views).index("Анализ игры"))
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
        self.detail_notebook.select(list(self.detail_views).index("История"))
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
