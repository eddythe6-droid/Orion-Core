"""Versioned, reproducible diagnostic report envelope."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from orion_core import __version__
from .system_info import collect_system_info
from .windows_info import collect_windows_diagnostics

REPORT_SCHEMA_VERSION = "1.0"


def collect_diagnostics_report() -> dict[str, Any]:
    """Collect a timestamped, read-only report with environment metadata."""
    return {
        "report_schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "collector": {
            "name": "Orion-Core",
            "version": __version__,
        },
        "environment": {
            "python_version": collect_system_info()["python"]["version"],
            "python_implementation": collect_system_info()["python"]["implementation"],
        },
        "system": collect_system_info(),
        "windows_diagnostics": collect_windows_diagnostics(),
        "validation": {
            "hardware_runtime_tests_performed": False,
            "notes": [
                "This report contains read-only host inventory, not a GPU workload benchmark.",
                "Registry indicators and device names do not prove support for a specific game.",
                "Hardware-dependent compatibility requires separate runtime tests.",
            ],
        },
    }
