"""Command-line interface for Orion-Core."""

from __future__ import annotations

import argparse
import json

from .system_info import collect_system_info
from .platform_catalog import load_platform_inventory
from .capability import assess_compatibility
from .windows_info import collect_windows_diagnostics
from .report import collect_diagnostics_report
from .gpu_probe import load_probe_report, summarize_probe_report, compare_gpu_adapters, summarize_gpu_memory


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect a read-only system report.")
    parser.add_argument("--json", action="store_true", help="Print the system report as JSON.")
    parser.add_argument("--gpu-probe-json", help="Validate and summarize a JSON report produced by the native D3D12 probe.")
    parser.add_argument("--gpu-memory-json", help="Analyze local and non-local GPU memory budgets from a native probe JSON report.")
    parser.add_argument("--compare-gpus", nargs=2, metavar=("LEFT_JSON", "RIGHT_JSON"), help="Compare two native D3D12 probe JSON reports.")
    parser.add_argument("--capabilities-json", action="store_true", help="Export the curated Xbox/Windows platform capability catalogue as JSON.")
    parser.add_argument("--assess-target", choices=("windows_pc", "xbox"), help="Create an evidence-linked compatibility assessment for a target platform.")
    parser.add_argument("--subsystem", help="Limit a capability export or assessment to one subsystem.")
    parser.add_argument(
        "--basic-only",
        action="store_true",
        help="Skip Windows-specific hardware and graphics inventory.",
    )
    args = parser.parse_args()

    if args.gpu_probe_json:
        report = load_probe_report(args.gpu_probe_json)
        print(json.dumps(summarize_probe_report(report), indent=2, ensure_ascii=False))
        return

    if args.gpu_memory_json:
        report = load_probe_report(args.gpu_memory_json)
        print(json.dumps(summarize_gpu_memory(report), indent=2, ensure_ascii=False))
        return

    if args.capabilities_json:
        inventory = load_platform_inventory()
        if args.subsystem:
            inventory = inventory.for_subsystem(args.subsystem)
        print(json.dumps(inventory.to_dict(), indent=2, ensure_ascii=False))
        return

    if args.assess_target:
        report = assess_compatibility(load_platform_inventory(), args.assess_target, args.subsystem)
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return

    report = collect_diagnostics_report(include_windows=not args.basic_only)

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
