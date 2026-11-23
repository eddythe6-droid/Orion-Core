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
        ttk.Button(actions, text="Очистить консоль", command=self.clear_console).pack(side="right")

        split = ttk.Panedwindow(outer, orient="vertical")
        split.pack(fill="both", expand=True)
        overview = ttk.Frame(split, style="Card.TFrame", padding=12)
        ttk.Label(overview, text="СОСТОЯНИЕ ИССЛЕДОВАНИЯ", style="CardTitle.TLabel").pack(anchor="w")
        self.overview_text = tk.StringVar(value="Запустите диагностику, чтобы получить сведения о системе.")
        ttk.Label(overview, textvariable=self.overview_text, background="#192535", wraplength=1000, justify="left").pack(anchor="w", pady=(8, 0))
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
                elif kind == "gpu_report":
                    self.gpu_report = payload
                    adapters = payload.get("adapters", [])
                    hardware = [item for item in adapters if not item.get("software") and item.get("d3d12_device")]
                    if hardware:
                        self.card_values["gpu"].set(hardware[0]["name"])
                    self.overview_text.set(
                        "Нативный D3D12-отчёт получен. Это проверка возможностей Windows/D3D12 и smoke-тестов; "
                        "совместимость Xbox-игр не устанавливается."
                    )
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
        self._log("SUCCESS", f"Система: {os_info['system']} {os_info['release']}; CPU: {cpu}; GPU: {self.card_values['gpu'].get()}.")


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
            completed = subprocess.run(
                [executable, "--json"], capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=180, check=False, shell=False,
            )
            if completed.stderr.strip():
                for line in completed.stderr.strip().splitlines():
                    self._emit("WARNING", f"D3D12 stderr: {line[:500]}")
            if completed.returncode not in (0, 3):
                raise RuntimeError(f"probe завершился с кодом {completed.returncode}")
            try:
                raw = json.loads(completed.stdout)
            except json.JSONDecodeError as exc:
                raise ProbeReportError("probe не вернул корректный JSON в stdout") from exc
            report = validate_probe_report(raw)
            self.events.put(("gpu_report", report))
            self._emit("SUCCESS", f"D3D12: отчёт получен; аппаратных D3D12-адаптеров: {report.get('hardware_d3d12_adapters', 0)}.")
            if completed.returncode == 3:
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
