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

def inspect_scarlett_pe(path: str | Path) -> dict[str, Any]:
    """Inspect PE headers and report Scarlett/GDK import clues, without execution."""
    pe = analyze_pe(path)
    imports = pe.get("imported_dlls", [])
    normalized = {name.casefold() for name in imports}
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
        "scarlett_gdk_import_hints": hints,
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
