"""Render-target/texture format report analysis without guessing SDK flag meanings."""
from __future__ import annotations

from typing import Any


def assess_format_requirements(required_formats: list[str], adapter: dict[str, Any]) -> dict[str, Any]:
    """Check whether named format queries were returned; do not decode raw masks."""
    records = {item["format"]: item for item in adapter.get("formats", [])
               if isinstance(item, dict) and isinstance(item.get("format"), str)}
    results = []
    for name in required_formats:
        record = records.get(name)
        if record is None:
            status, reason = "unknown", "format is absent from the probe report"
        elif record.get("query_available") is not True:
            status, reason = "unknown", "native format-support query was unavailable"
        elif not isinstance(record.get("support1"), int):
            status, reason = "unknown", "raw support mask is unavailable"
        else:
            status, reason = "hardware_validation_needed", "query returned a raw SDK mask; usage flags are intentionally not decoded"
        results.append({"format": name, "status": status, "reason": reason,
                        "support1": record.get("support1") if record else None,
                        "support2": record.get("support2") if record else None})
    overall = ("unknown" if any(x["status"] == "unknown" for x in results) else
               "hardware_validation_needed")
    return {
        "schema_version": 1, "adapter": adapter.get("name", "unknown"),
        "overall": overall, "results": results,
        "limitations": [
            "Raw D3D12 format support masks are preserved and not decoded.",
            "No render-target, depth-stencil, sampling, typed-UAV, or resolve workload is executed.",
            "A successful query does not prove a particular pipeline configuration will work.",
        ],
    }


def compare_format_reports(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """Compare raw masks for matching format names without interpreting bit semantics."""
    def index(adapter: dict[str, Any]) -> dict[str, dict[str, Any]]:
        return {item["format"]: item for item in adapter.get("formats", [])
                if isinstance(item, dict) and isinstance(item.get("format"), str)}
    a, b = index(left), index(right)
    rows = []
    for name in sorted(set(a) | set(b)):
        x, y = a.get(name), b.get(name)
        if x is None or y is None or x.get("query_available") is not True or y.get("query_available") is not True:
            status = "unknown"
        elif x.get("support1") is None or y.get("support1") is None:
            status = "unknown"
        else:
            status = "same_raw_masks" if (x.get("support1"), x.get("support2")) == (y.get("support1"), y.get("support2")) else "different_raw_masks"
        rows.append({"format": name, "status": status,
                     "left_support1": x.get("support1") if x else None,
                     "right_support1": y.get("support1") if y else None,
                     "left_support2": x.get("support2") if x else None,
                     "right_support2": y.get("support2") if y else None})
    return {"schema_version": 1, "formats": rows,
            "interpretation": "Raw mask comparison only; no usage-flag or compatibility inference."}
