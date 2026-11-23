"""Command-line interface for Orion-Core."""

from __future__ import annotations

import argparse
import json

from .system_info import collect_system_info


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a read-only system report.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    args = parser.parse_args()

    report = collect_system_info()
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    print("Orion-Core system report")
    print(f"OS: {report['os']['system']} {report['os']['release']}")
    print(f"Architecture: {report['architecture']}")
    print(f"Processor: {report['processor'] or 'not reported by system'}")
    print(f"Logical CPUs: {report['logical_cpu_count']}")
    memory = report["memory_total_bytes"]
    print(f"Physical memory: {memory / (1024 ** 3):.2f} GiB" if memory else "Physical memory: unavailable")
