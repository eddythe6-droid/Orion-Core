"""Command-line interface for Orion-Core."""

from __future__ import annotations

import argparse
import json

from .system_info import collect_system_info
from .windows_info import collect_windows_diagnostics


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a read-only system report.")
    parser.add_argument("--json", action="store_true", help="Print the report as JSON.")
    parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Skip Windows-specific hardware and graphics inventory.",
    )
    args = parser.parse_args()

    report = {"system": collect_system_info()}
    if not args.basic_only:
        report["windows_diagnostics"] = collect_windows_diagnostics()

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    system = report["system"]
    print("Orion-Core system report")
    print(f"OS: {system['os']['system']} {system['os']['release']}")
    print(f"Architecture: {system['architecture']}")
    print(f"Processor: {system['processor'] or 'not reported by system'}")
    print(f"Logical CPUs: {system['logical_cpu_count']}")
    memory = system["memory_total_bytes"]
    print(f"Physical memory: {memory / (1024 ** 3):.2f} GiB" if memory else "Physical memory: unavailable")

    windows = report.get("windows_diagnostics", {})
    if windows.get("supported"):
        hardware = windows.get("hardware", {})
        cpu = hardware.get("cpu") or {}
        if cpu:
            print(f"CPU model: {cpu.get('Name') or 'unknown'}")
            print(f"CPU cores/threads: {cpu.get('NumberOfCores', '?')}/{cpu.get('NumberOfLogicalProcessors', '?')}")
        if hardware.get("available"):
            for index, gpu in enumerate(hardware.get("gpus", []), start=1):
                print(f"GPU {index}: {gpu.get('Name') or 'unknown'}")
                print(f"  Driver: {gpu.get('DriverVersion') or 'unknown'}")
        else:
            print(f"Windows hardware inventory unavailable: {hardware.get('reason', 'unknown error')}")
        runtimes = windows.get("graphics_runtimes", {})
        print(f"DirectX registry version: {runtimes.get('directx', {}).get('registry_version') or 'not found'}")
        print(f"Vulkan ICD registrations: {runtimes.get('vulkan', {}).get('registered_icd_manifests', 0)}")
