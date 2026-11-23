"""Windows hardware and graphics-runtime inventory.

All queries are read-only. No registry values or system configuration are changed.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def _powershell_inventory() -> dict[str, Any]:
    """Query selected CIM properties using a fixed, non-user-controlled script."""
    if os.name != "nt":
        return {"available": False, "reason": "Windows-only inventory"}

    script = r"""
$cpu = Get-CimInstance Win32_Processor -ErrorAction Stop |
  Select-Object -First 1 Name, Manufacturer, NumberOfCores, NumberOfLogicalProcessors, MaxClockSpeed
$gpus = @(Get-CimInstance Win32_VideoController -ErrorAction Stop |
  Select-Object Name, DriverVersion, DriverDate, VideoModeDescription, CurrentHorizontalResolution, CurrentVerticalResolution)
$result = [ordered]@{ cpu = $cpu; gpus = $gpus }
$result | ConvertTo-Json -Depth 4 -Compress
"""
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=20,
            check=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(completed.stdout)
        if not isinstance(data, dict):
            raise ValueError("Unexpected PowerShell response")
        gpus = data.get("gpus")
        if isinstance(gpus, dict):
            data["gpus"] = [gpus]
        elif not isinstance(gpus, list):
            data["gpus"] = []
        return {"available": True, **data}
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError, ValueError) as exc:
        return {"available": False, "reason": type(exc).__name__}


def _graphics_runtime_inventory() -> dict[str, Any]:
    """Read selected DirectX/Vulkan registration facts without exposing paths."""
    if os.name != "nt":
        return {"available": False, "reason": "Windows-only inventory"}

    result: dict[str, Any] = {
        "directx": {"registry_version": None},
        "vulkan": {"registered_icd_manifests": 0},
    }
    try:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\DirectX"
            ) as key:
                for value_name in ("Version", "InstalledVersion"):
                    try:
                        value, _ = winreg.QueryValueEx(key, value_name)
                        result["directx"]["registry_version"] = str(value)
                        break
                    except FileNotFoundError:
                        continue
        except OSError:
            pass

        manifest_count = 0
        for subkey in (
            r"SOFTWARE\Khronos\Vulkan\Drivers",
            r"SOFTWARE\WOW6432Node\Khronos\Vulkan\Drivers",
        ):
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as key:
                    index = 0
                    while True:
                        try:
                            _, value, _ = winreg.EnumValue(key, index)
                        except OSError:
                            break
                        index += 1
                        if isinstance(value, str) and value.strip():
                            manifest_count += 1
            except OSError:
                continue
        result["vulkan"]["registered_icd_manifests"] = manifest_count
        result["available"] = True
    except ImportError:
        result["available"] = False
        result["reason"] = "Windows registry module unavailable"
    return result


def collect_windows_diagnostics() -> dict[str, Any]:
    """Return CPU, GPU, and graphics-runtime facts on Windows."""
    if os.name != "nt":
        return {"supported": False, "reason": "Available only on Windows"}
    return {
        "supported": True,
        "hardware": _powershell_inventory(),
        "graphics_runtimes": _graphics_runtime_inventory(),
        "notes": [
            "DirectX registry version is not a complete DirectX feature-level report.",
            "Vulkan registry entries indicate registered ICD manifests, not guaranteed device support.",
            "No serial numbers, device identifiers, usernames, or manifest paths are collected.",
        ],
    }
