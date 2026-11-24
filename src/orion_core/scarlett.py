"""Read-only Xbox Series / Scarlett PE candidate assessment.

This module does not identify a file as an authentic Xbox title. It combines
ordinary PE metadata with conservative, documented GDK import-name hints.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .pe_analyzer import analyze_pe, PEFormatError

# Names are hints only. A DLL name alone does not prove target platform.
SCARLETT_IMPORT_HINTS = {
    "d3d12_xs.dll": "scarlett_d3d12_xs_graphics_interface",
    "xgameruntime.dll": "xbox_gaming_runtime",
    "xgameplatform.dll": "xbox_game_platform",
    "xboxservices.dll": "xbox_services",
    "xboxservices.config.dll": "xbox_services",
    "xmem.dll": "xbox_memory_api",
    "xma2dsp.dll": "xbox_audio",
    "xact3.dll": "xbox_audio_legacy",
    "xinputuap.dll": "xbox_input",
    "xboxkrnl.exe": "xbox_kernel_import_module",
}

def inspect_scarlett_pe(
    path: str | Path,
    *,
    pe_report: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Inspect PE metadata and report Xbox Series/GDK import clues, without execution.

    A caller that already parsed the same PE can pass pe_report to avoid a second
    disk scan. The supplied report is treated as parser output, not as trusted
    platform identity evidence.
    """
    pe = pe_report if pe_report is not None else analyze_pe(path)
    normal_modules = pe.get("import_modules", [])
    delay_modules = pe.get("delay_import_modules", [])
    module_evidence: list[dict[str, Any]] = []
    for load_kind, modules in (("normal_import", normal_modules), ("delay_load_import", delay_modules)):
        for module in modules:
            name = str(module.get("dll", ""))
            category = SCARLETT_IMPORT_HINTS.get(name.casefold())
            if not category:
                continue
            symbols = module.get("functions", [])
            module_evidence.append({
                "module": name,
                "category": category,
                "load_kind": load_kind,
                "imported_symbol_count": len(symbols),
                "imported_symbols": symbols[:256] if load_kind == "normal_import" else [],
                "symbol_inventory_truncated": len(symbols) > 256,
            })

    imports = pe.get("imported_dlls", [])
    normalized = {str(name).casefold() for name in imports}
    normalized.update(str(item.get("dll", "")).casefold() for item in delay_modules)
    hints = [
        {"module": name, "category": category}
        for name, category in sorted(SCARLETT_IMPORT_HINTS.items())
        if name in normalized
    ]
    is_pe64_x64 = pe.get("optional_header") == "PE32+" and pe.get("machine") == 0x8664
    categories = sorted({item["category"] for item in hints})
    return {
        "candidate_format": "PE32+ x86-64" if is_pe64_x64 else "other_pe",
        "architecture_matches_xbox_series_cpu": is_pe64_x64,
        "normal_import_module_count": len(normal_modules),
        "delay_load_module_count": len(delay_modules),
        "scarlett_gdk_import_hints": hints,
        "module_evidence": module_evidence,
        "hint_categories": categories,
        "assessment": (
            "xbox_series_gdk_candidate" if is_pe64_x64 and hints
            else "x64_pe_candidate_no_specific_gdk_imports" if is_pe64_x64
            else "not_xbox_series_x64_shape"
        ),
        "authenticity_verified": False,
        "platform_identity_verified": False,
        "imports_are_hints_not_proof": True,
        "pe_metadata": pe,
        "execution_performed": False,
        "payload_decryption_or_unpacking": False,
    }
