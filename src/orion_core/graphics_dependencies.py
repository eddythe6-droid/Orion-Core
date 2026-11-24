"""Conservative graphics-stack evidence extracted from PE imports and file inventory.

This module reports observed names only; it does not infer runtime use or compatibility.
"""
from __future__ import annotations

from typing import Any

_GRAPHICS_MODULES = {
    "d3d12.dll": ("direct3d_12", "high"),
    "d3d11.dll": ("direct3d_11", "high"),
    "dxgi.dll": ("dxgi", "high"),
    "d3d11on12.dll": ("d3d11_on_12", "high"),
    "d3dcompiler_47.dll": ("shader_compiler_runtime", "medium"),
    "dxcompiler.dll": ("dxil_shader_compiler", "medium"),
    "dxil.dll": ("dxil_runtime", "medium"),
    "vulkan-1.dll": ("vulkan", "high"),
    "opengl32.dll": ("opengl", "high"),
    "nvapi64.dll": ("vendor_nvapi", "medium"),
    "amd_ags_x64.dll": ("vendor_amd_ags", "medium"),
}
_GRAPHICS_SYMBOLS = {
    "d3d12createdevice": "d3d12_device_creation",
    "createdxgifactory": "dxgi_factory_creation",
    "createdxgifactory1": "dxgi_factory_creation",
    "createdxgifactory2": "dxgi_factory_creation",
    "d3d11createdevice": "d3d11_device_creation",
    "d3d11createdeviceandswapchain": "d3d11_device_creation",
    "vkcreateinstance": "vulkan_instance_creation",
    "vkcreatedevice": "vulkan_device_creation",
}
_SHADER_EXTENSIONS = {".cso", ".dxil", ".dxbc", ".spv", ".metallib"}
_TEXTURE_EXTENSIONS = {".dds", ".ktx", ".ktx2", ".astc", ".png", ".jpg", ".jpeg", ".tga", ".bmp"}


def assess_graphics_dependencies(pe_analysis: dict[str, Any],
                                 inventory_records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Summarize graphics DLL/API evidence and related asset-file counts."""
    modules = []
    module_counts: dict[str, int] = {}
    symbol_counts: dict[str, int] = {}
    for imported_module in pe_analysis.get("import_modules", []):
        dll = str(imported_module.get("dll", "")).casefold()
        if dll not in _GRAPHICS_MODULES:
            continue
        family, confidence = _GRAPHICS_MODULES[dll]
        module_counts[family] = module_counts.get(family, 0) + 1
        symbols = []
        for imported in imported_module.get("functions", []):
            name = str(imported.get("name", "")) if imported.get("kind") == "name" else ""
            symbol_family = _GRAPHICS_SYMBOLS.get(name.casefold())
            if symbol_family:
                symbol_counts[symbol_family] = symbol_counts.get(symbol_family, 0) + 1
            symbols.append({
                "import": imported,
                "classification": symbol_family or "unclassified_symbol",
            })
        modules.append({
            "module": imported_module.get("dll", ""),
            "family": family,
            "evidence_confidence": confidence,
            "symbols": symbols,
        })

    shader_files = []
    texture_files = []
    for record in inventory_records or []:
        path = str(record.get("path", ""))
        suffix = path.rsplit(".", 1)[-1].casefold() if "." in path else ""
        ext = "." + suffix if suffix else ""
        if ext in _SHADER_EXTENSIONS:
            shader_files.append(path)
        if ext in _TEXTURE_EXTENSIONS:
            texture_files.append(path)

    if modules:
        assessment = "graphics_dependencies_observed"
    else:
        assessment = "no_known_graphics_imports_observed"
    return {
        "schema_version": 1,
        "assessment": assessment,
        "modules": modules,
        "module_family_counts": module_counts,
        "symbol_family_counts": symbol_counts,
        "asset_inventory": {
            "shader_like_file_count": len(shader_files),
            "shader_like_files": shader_files[:200],
            "texture_like_file_count": len(texture_files),
            "texture_like_files": texture_files[:200],
            "paths_truncated": len(shader_files) > 200 or len(texture_files) > 200,
        },
        "evidence_level": "static_import_names_and_filename_extensions",
        "limitations": [
            "An imported DLL does not prove that the code path is used at runtime.",
            "A missing import does not exclude dynamically loaded graphics APIs.",
            "Shader and texture classifications use filename extensions only; contents are not decoded.",
            "No shader bytecode, root signature, pipeline state, GPU feature requirement, or API ABI is validated here.",
            "Graphics API names do not establish Xbox-to-Windows compatibility or porting feasibility.",
        ],
        "compatibility_established": False,
        "execution_performed": False,
    }
