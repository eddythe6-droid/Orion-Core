"""Conservative static import-to-export matching for files in one inspected folder."""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


def build_local_export_index(files: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Index exports by case-insensitive basename; never loads a binary."""
    index: dict[str, list[dict[str, Any]]] = {}
    for record in files:
        pe = record.get("pe_analysis") or {}
        if not pe.get("valid_pe_structure"):
            continue
        name = PurePosixPath(str(record.get("path", "")).replace("\\\\", "/")).name.casefold()
        if not name:
            continue
        exports = pe.get("exported_functions", [])
        index.setdefault(name, []).append({
            "path": record.get("path", name),
            "architecture": pe.get("architecture", "unknown"),
            "exports": exports,
            "exports_incomplete": bool(pe.get("exports_truncated_or_unavailable")),
        })
    return index


def resolve_imports_against_local_files(
    pe_analysis: dict[str, Any], local_index: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    """Match named/ordinal imports against local PE exports, without claiming ABI compatibility."""
    results: list[dict[str, Any]] = []
    counts = {"resolved_name_match": 0, "resolved_ordinal_match": 0, "forwarded_export": 0,
              "missing_module": 0, "missing_symbol": 0, "ambiguous_module": 0,
              "incomplete_or_unknown": 0}
    imports = pe_analysis.get("import_modules", [])
    for module in imports:
        if not isinstance(module, dict) or not isinstance(module.get("dll"), str):
            continue
        dll = module["dll"]
        candidates = local_index.get(dll.casefold(), [])
        if not candidates:
            counts["missing_module"] += 1
            results.append({"module": dll, "status": "missing_module", "symbols": []})
            continue
        if len(candidates) != 1:
            counts["ambiguous_module"] += 1
            results.append({"module": dll, "status": "ambiguous_module",
                            "candidate_paths": [item["path"] for item in candidates], "symbols": []})
            continue
        candidate = candidates[0]
        if candidate["architecture"] != pe_analysis.get("architecture") and candidate["architecture"] != "unknown" and pe_analysis.get("architecture") != "unknown":
            counts["incomplete_or_unknown"] += 1
            results.append({"module": dll, "status": "architecture_mismatch",
                            "candidate_path": candidate["path"], "symbols": []})
            continue
        by_name = {name.casefold(): export for export in candidate["exports"]
                   for name in export.get("names", [])}
        by_ordinal = {export.get("ordinal"): export for export in candidate["exports"]}
        symbol_results = []
        for symbol in module.get("functions", []):
            if symbol.get("kind") == "name":
                found = by_name.get(str(symbol.get("name", "")).casefold())
                key = "resolved_name_match"
            elif symbol.get("kind") == "ordinal":
                found = by_ordinal.get(symbol.get("ordinal"))
                key = "resolved_ordinal_match"
            else:
                found, key = None, "incomplete_or_unknown"
            if found and found.get("is_forwarder"):
                status = "forwarded_export"
                counts["forwarded_export"] += 1
            elif found:
                status = key
                counts[key] += 1
            elif candidate["exports_incomplete"]:
                status = "incomplete_or_unknown"
                counts["incomplete_or_unknown"] += 1
            else:
                status = "missing_symbol"
                counts["missing_symbol"] += 1
            symbol_results.append({"import": symbol, "status": status,
                                   "export_ordinal": found.get("ordinal") if found else None,
                                   "forwarder": found.get("forwarder") if found else None})
        results.append({"module": dll, "status": "candidate_file_found",
                        "candidate_path": candidate["path"], "symbols": symbol_results})
    total = sum(counts.values())
    return {
        "schema_version": 1, "modules": results, "counts": counts, "symbol_results": total,
        "resolution_performed": True, "execution_performed": False,
        "compatibility_established": False,
        "limitations": [
            "Matching is limited to PE files present in the inspected folder and exact DLL basenames.",
            "A matching name or ordinal does not validate ABI, calling convention, structure layout, version, or runtime behavior.",
            "Forwarded exports are reported but their forwarding chains are not followed.",
            "API-set contracts, system search order, transitive dependencies, dynamically loaded modules, and delay-load symbol tables are not resolved.",
            "Missing local files are not proof that a dependency is unavailable on the target operating system.",
        ],
    }
