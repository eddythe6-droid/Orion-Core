"""Evidence-conservative classification of PE import module dependencies.

This is static triage only: module names are not proof that an API is
available or compatible on a particular Windows build.
"""
from __future__ import annotations

from typing import Any

WINDOWS_MODULES = {
    "advapi32.dll", "bcrypt.dll", "cfgmgr32.dll", "combase.dll",
    "comdlg32.dll", "crypt32.dll", "d3d11.dll", "d3d12.dll", "dcomp.dll",
    "dinput8.dll", "dwmapi.dll", "dxgi.dll", "gdi32.dll", "gdi32full.dll",
    "imm32.dll", "kernel32.dll", "kernelbase.dll", "msvcp_win.dll",
    "msvcrt.dll", "ntdll.dll", "ole32.dll", "oleaut32.dll", "powrprof.dll",
    "sechost.dll", "setupapi.dll", "shell32.dll", "shlwapi.dll",
    "user32.dll", "uxtheme.dll", "version.dll", "winhttp.dll",
    "winmm.dll", "wintrust.dll", "ws2_32.dll", "xaudio2_9.dll",
    "xinput1_4.dll",
}

XBOX_MODULE_HINTS = {
    "d3d12_xs.dll": "scarlett_d3d12_xs_graphics_interface",
    "xgameruntime.dll": "xbox_gaming_runtime",
    "xgameplatform.dll": "xbox_game_platform",
    "xboxservices.dll": "xbox_services",
    "xboxservices.config.dll": "xbox_services",
    "xmem.dll": "xbox_memory_api",
    "xma2dsp.dll": "xbox_audio",
    "xinputuap.dll": "xbox_input",
    "xboxkrnl.exe": "xbox_kernel_import_module",
}


def build_dependency_report(pe_analysis: dict[str, Any]) -> dict[str, Any]:
    """Classify normal and delay-load imports without loading or resolving them."""
    modules: dict[str, dict[str, Any]] = {}

    def add(name: str, kind: str, functions: list[dict[str, Any]] | None = None) -> None:
        key = name.casefold()
        item = modules.setdefault(key, {
            "module": name,
            "classification": (
                "windows_module_name_candidate" if key in WINDOWS_MODULES
                else "xbox_platform_module_hint" if key in XBOX_MODULE_HINTS
                else "unclassified_module"
            ),
            "platform_hint": XBOX_MODULE_HINTS.get(key),
            "normal_import": False,
            "delay_load_import": False,
            "symbols": [],
        })
        item[kind] = True
        for symbol in functions or []:
            if symbol not in item["symbols"]:
                item["symbols"].append(symbol)

    for module in pe_analysis.get("import_modules", []):
        if isinstance(module, dict) and isinstance(module.get("dll"), str):
            add(module["dll"], "normal_import", module.get("functions", []))
    known_normal = {m.casefold() for m in pe_analysis.get("imported_dlls", [])}
    for name in known_normal:
        if name not in modules:
            add(name, "normal_import")
    for module in pe_analysis.get("delay_import_modules", []):
        if isinstance(module, dict) and isinstance(module.get("dll"), str):
            add(module["dll"], "delay_load_import")

    result = sorted(modules.values(), key=lambda item: item["module"].casefold())
    counts = {
        label: sum(1 for item in result if item["classification"] == label)
        for label in ("windows_module_name_candidate", "xbox_platform_module_hint", "unclassified_module")
    }
    return {
        "schema_version": 1,
        "modules": result,
        "module_count": len(result),
        "classification_counts": counts,
        "unresolved_symbols": [],
        "resolution_performed": False,
        "execution_performed": False,
        "compatibility_established": False,
        "limitations": [
            "A Windows module name does not prove that every imported symbol or required version is available.",
            "An Xbox module hint does not reveal its ABI, implementation, or replacement.",
            "Exports are not parsed and import symbols are not linked to DLL exports.",
            "API-set forwarding, ordinal resolution, runtime-loaded modules, and transitive dependencies are not resolved.",
            "No binary is loaded, executed, modified, decrypted, or unpacked.",
        ],
    }
