"""Read-only inventory and signature inspection for game files.

No archive extraction, execution, decryption, or DRM handling is performed.
"""
from __future__ import annotations

import hashlib
import json
import os
import zipfile
from pathlib import Path
from typing import Any

from .pe_analyzer import analyze_pe, PEFormatError
from .iso9660 import inspect_iso9660, ISO9660Error
from .xdvdfs import inspect_xdvdfs, XDVDFSError
from .stfs import inspect_stfs, inspect_svod_directory, STFSError
from .xex import inspect_xex, XEXError
from .scarlett import inspect_scarlett_pe
from .dependency_analysis import build_dependency_report
from .import_resolver import build_local_export_index, resolve_imports_against_local_files
from .api_catalog import assess_imported_symbols
from .graphics_dependencies import assess_graphics_dependencies
from .shader_inspector import inspect_shader_file, ShaderFormatError

INSPECTOR_SCHEMA_VERSION = 1
MAX_FILES = 100_000
MAX_ARCHIVE_MEMBERS = 50_000
HASH_LIMIT_BYTES = 64 * 1024 * 1024

_SIGNATURES = (
    (b"MZ", "pe_dos_header"),
    (b"\x7fELF", "elf"),
    (b"PK\x03\x04", "zip"),
    (b"XEX2", "xex2"),
    (b"CON ", "xbox_stfs"),
    (b"RIFF", "riff"),
    (b"DDS ", "dds"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"\xff\xd8\xff", "jpeg"),
    (b"OggS", "ogg"),
    (b"ID3", "mp3"),
)

_EXTENSION_HINTS = {
    ".xex": "xbox_360_executable_extension",
    ".xbe": "original_xbox_executable_extension",
    ".pak": "game_archive_extension",
    ".rpf": "game_archive_extension",
    ".wad": "game_archive_extension",
    ".arc": "game_archive_extension",
    ".bundle": "game_archive_extension",
    ".assets": "game_asset_container_extension",
    ".bank": "audio_bank_extension",
    ".wem": "wwise_audio_extension",
    ".bnk": "wwise_audio_bank_extension",
    ".dds": "dds_texture_extension",
    ".ktx": "ktx_texture_extension",
    ".ktx2": "ktx2_texture_extension",
    ".gltf": "gltf_model_extension",
    ".glb": "glb_model_extension",
    ".fbx": "fbx_model_extension",
    ".obj": "obj_model_extension",
    ".wav": "wav_audio_extension",
    ".xma": "xma_audio_extension",
    ".pdb": "debug_symbols_extension",
    ".dll": "windows_library_extension",
    ".exe": "windows_executable_extension",
}


class GameInspectionError(ValueError):
    """Raised when an inspection request cannot be completed safely."""


def _classify(path: Path, header: bytes) -> str:
    for signature, label in _SIGNATURES:
        if header.startswith(signature):
            if label == "riff":
                subtype = header[8:12].decode("ascii", errors="replace").strip() if len(header) >= 12 else ""
                return f"riff_{subtype.lower()}" if subtype else "riff"
            return label
    return _EXTENSION_HINTS.get(path.suffix.lower(), "unknown")


def _sha256(path: Path, size: int, *, allow_large: bool = False) -> str | None:
    if size > HASH_LIMIT_BYTES and not allow_large:
        return None
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_game_path(
    path: str | Path,
    *,
    max_files: int = MAX_FILES,
    hash_files: bool = False,
    hash_large_executables: bool = False,
) -> dict[str, Any]:
    """Inventory a file, directory, or ZIP-compatible archive without extracting it."""
    target = Path(path)
    if not target.exists():
        raise GameInspectionError(f"path does not exist: {target}")
    if target.is_symlink():
        raise GameInspectionError("symbolic-link targets are not followed")
    if max_files < 1:
        raise GameInspectionError("max_files must be positive")

    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    counts: dict[str, int] = {}

    def add_file(file_path: Path, relative: str) -> None:
        if len(records) >= max_files:
            raise GameInspectionError(f"file limit reached ({max_files}); narrow the inspection path")
        try:
            stat = file_path.stat()
            with file_path.open("rb") as stream:
                header = stream.read(16)
            kind = _classify(file_path, header)
            pe_analysis = None
            scarlett_analysis = None
            dependency_analysis = None
            stfs_metadata = None
            xex_metadata = None
            if kind == "xex2":
                try:
                    xex_metadata = inspect_xex(file_path)
                except XEXError as exc:
                    xex_metadata = {"valid_header": False, "error": str(exc)}
            if kind == "xbox_stfs":
                try:
                    stfs_metadata = inspect_stfs(file_path)
                except STFSError as exc:
                    stfs_metadata = {"valid_header": False, "error": str(exc)}
            shader_analysis = None
            shader_suffix = file_path.suffix.lower() in {".cso", ".dxil", ".dxbc", ".spv"}
            shader_magic = header[:4] in {b"\x03\x02#\x07", b"\x07#\x02\x03"}
            if shader_suffix or shader_magic:
                try:
                    shader_analysis = inspect_shader_file(file_path)
                except (ShaderFormatError, OSError) as exc:
                    shader_analysis = {"assessment": "unrecognized_or_malformed_shader_container",
                                       "error": str(exc), "bytecode_validated": False,
                                       "execution_performed": False}
            if kind == "pe_dos_header":
                try:
                    pe_analysis = analyze_pe(file_path)
                    scarlett_analysis = inspect_scarlett_pe(file_path, pe_report=pe_analysis)
                    dependency_analysis = build_dependency_report(pe_analysis)
                except PEFormatError as exc:
                    pe_analysis = {"valid_pe_structure": False, "error": str(exc)}
                    scarlett_analysis = {"assessment": "invalid_or_unsupported_pe", "error": str(exc),
                                         "authenticity_verified": False, "execution_performed": False}
            should_hash = (
                (hash_files and stat.st_size <= HASH_LIMIT_BYTES)
                or (hash_large_executables and kind in {"pe_dos_header", "xex2", "xbox_stfs"})
            )
            digest = (
                _sha256(
                    file_path,
                    stat.st_size,
                    allow_large=hash_large_executables and kind in {"pe_dos_header", "xex2", "xbox_stfs"},
                )
                if should_hash else None
            )
            records.append({
                "path": relative,
                "size_bytes": stat.st_size,
                "extension": file_path.suffix.lower(),
                "detected_type": kind,
                "sha256": digest,
                "sha256_status": (
                    "computed" if digest else
                    "not_requested" if not (hash_files or hash_large_executables) else
                    "over_64_mib_limit"
                ),
                "pe_analysis": pe_analysis,
                "scarlett_analysis": scarlett_analysis,
                "dependency_analysis": dependency_analysis,
                "stfs_metadata": stfs_metadata,
                "xex_metadata": xex_metadata,
                "shader_analysis": shader_analysis,
            })
            counts[kind] = counts.get(kind, 0) + 1
        except OSError as exc:
            warnings.append(f"{relative}: {type(exc).__name__}: {exc}")

    iso_report = None
    xdvdfs_report = None
    stfs_report = None
    svod_report = None
    if target.is_file():
        if target.suffix.lower() in (".iso", ".xiso"):
            try:
                xdvdfs_report = inspect_xdvdfs(target, max_entries=max_files)
                for entry in xdvdfs_report["entries"]:
                    if entry["directory"]:
                        continue
                    kind = _EXTENSION_HINTS.get(Path(entry["path"]).suffix.lower(), "unknown")
                    records.append({"path": entry["path"], "size_bytes": entry["size_bytes"],
                                    "extension": Path(entry["path"]).suffix.lower(), "detected_type": kind,
                                    "sha256": None, "xdvdfs_member": True, "extent_sector": entry["extent_sector"]})
                    counts[kind] = counts.get(kind, 0) + 1
            except XDVDFSError as xdvdfs_exc:
                warnings.append(f"XDVDFS parser: {xdvdfs_exc}")
                if target.suffix.lower() == ".iso":
                    try:
                        iso_report = inspect_iso9660(target, max_entries=max_files)
                        for entry in iso_report["entries"]:
                            if entry["directory"]:
                                continue
                            kind = _EXTENSION_HINTS.get(Path(entry["path"]).suffix.lower(), "unknown")
                            records.append({"path": entry["path"], "size_bytes": entry["size_bytes"],
                                            "extension": Path(entry["path"]).suffix.lower(), "detected_type": kind,
                                            "sha256": None, "iso9660_member": True, "extent_sector": entry["extent_sector"]})
                            counts[kind] = counts.get(kind, 0) + 1
                    except ISO9660Error as exc:
                        warnings.append(f"ISO9660 parser: {exc}")
                        add_file(target, target.name)
                else:
                    add_file(target, target.name)
        elif zipfile.is_zipfile(target):
            try:
                with zipfile.ZipFile(target) as archive:
                    infos = archive.infolist()
                    if len(infos) > MAX_ARCHIVE_MEMBERS:
                        raise GameInspectionError(f"archive member limit exceeded ({MAX_ARCHIVE_MEMBERS})")
                    for info in infos:
                        if info.is_dir():
                            continue
                        if len(records) >= max_files:
                            raise GameInspectionError(f"file limit reached ({max_files}); narrow the inspection")
                        name = info.filename.replace("\\", "/")
                        kind = _EXTENSION_HINTS.get(Path(name).suffix.lower(), "unknown")
                        records.append({
                            "path": name,
                            "size_bytes": info.file_size,
                            "compressed_size_bytes": info.compress_size,
                            "extension": Path(name).suffix.lower(),
                            "detected_type": kind,
                            "sha256": None,
                            "archive_member": True,
                        })
                        counts[kind] = counts.get(kind, 0) + 1
            except (OSError, zipfile.BadZipFile) as exc:
                raise GameInspectionError(f"cannot inspect archive: {type(exc).__name__}") from exc
        elif target.open("rb").read(4) in (b"CON ", b"LIVE", b"PIRS"):
            try:
                stfs_report = inspect_stfs(target)
                stat = target.stat()
                records.append({
                    "path": target.name,
                    "size_bytes": stat.st_size,
                    "extension": target.suffix.lower(),
                    "detected_type": "xbox_stfs",
                    "sha256": (
                        _sha256(target, stat.st_size, allow_large=hash_large_executables)
                        if (hash_files and stat.st_size <= HASH_LIMIT_BYTES) or hash_large_executables
                        else None
                    ),
                    "sha256_status": (
                        "computed" if (hash_files and stat.st_size <= HASH_LIMIT_BYTES) or hash_large_executables
                        else "not_requested" if not (hash_files or hash_large_executables)
                        else "over_64_mib_limit"
                    ),
                    "pe_analysis": None,
                    "scarlett_analysis": None,
                    "dependency_analysis": None,
                    "stfs_metadata": stfs_report,
                    "xex_metadata": None,
                    "shader_analysis": None,
                })
                counts["xbox_stfs"] = 1
            except STFSError as exc:
                warnings.append(f"STFS parser: {exc}")
                add_file(target, target.name)
        else:
            add_file(target, target.name)
    elif target.is_dir():
        try:
            svod_report = inspect_svod_directory(target)
            if not svod_report["containers"]:
                svod_report = None
        except STFSError as exc:
            warnings.append(f"SVOD parser: {exc}")
        for root, dirs, files in os.walk(target, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not (Path(root) / d).is_symlink())
            for filename in sorted(files):
                file_path = Path(root) / filename
                if file_path.is_symlink():
                    warnings.append(f"{file_path.relative_to(target)}: symbolic link skipped")
                    continue
                add_file(file_path, str(file_path.relative_to(target)))
    else:
        raise GameInspectionError("path is neither a regular file nor a directory")

    records.sort(key=lambda item: item["path"].casefold())
    shader_records = [item for item in records if item.get("shader_analysis") is not None]
    shader_formats: dict[str, int] = {}
    shader_assessments: dict[str, int] = {}
    shader_stages: dict[str, int] = {}
    shader_resource_types: dict[str, int] = {}
    shader_resource_bindings = 0
    spirv_capabilities: dict[str, int] = {}
    spirv_extensions: dict[str, int] = {}
    spirv_entry_points = 0
    for item in shader_records:
        analysis = item["shader_analysis"]
        fmt = analysis.get("format", "unrecognized")
        shader_formats[fmt] = shader_formats.get(fmt, 0) + 1
        for capability in analysis.get("capabilities", []):
            key = str(capability)
            spirv_capabilities[key] = spirv_capabilities.get(key, 0) + 1
        for extension in analysis.get("extensions", []):
            spirv_extensions[extension] = spirv_extensions.get(extension, 0) + 1
        spirv_entry_points += len(analysis.get("entry_points", []))
        assessment = analysis.get("assessment", analysis.get("header_assessment", "metadata_inspected"))
        shader_assessments[assessment] = shader_assessments.get(assessment, 0) + 1
        for program in analysis.get("shader_programs", []):
            stage = program.get("stage", "unknown")
            shader_stages[stage] = shader_stages.get(stage, 0) + 1
        for chunk in analysis.get("chunks", []):
            reflection = chunk.get("resource_reflection", {})
            for resource in reflection.get("resources", []):
                shader_resource_bindings += 1
                resource_type = resource.get("input_type", "unknown")
                shader_resource_types[resource_type] = shader_resource_types.get(resource_type, 0) + 1
    shader_summary = {
        "files_with_shader_analysis": len(shader_records),
        "formats": dict(sorted(shader_formats.items())),
        "assessments": dict(sorted(shader_assessments.items())),
        "dxbc_shader_stages": dict(sorted(shader_stages.items())),
        "rdef_resource_binding_count": shader_resource_bindings,
        "rdef_resource_types": dict(sorted(shader_resource_types.items())),
        "spirv_capability_occurrences": dict(sorted(spirv_capabilities.items())),
        "spirv_extension_occurrences": dict(sorted(spirv_extensions.items())),
        "spirv_entry_point_count": spirv_entry_points,
        "bytecode_validated": False,
        "compatibility_established": False,
    }
    # Resolve only against PE files already inventoried in this same folder.
    local_export_index = build_local_export_index(records)
    for record in records:
        pe = record.get("pe_analysis")
        dependencies = record.get("dependency_analysis")
        if pe and pe.get("valid_pe_structure") and dependencies is not None:
            dependencies["local_resolution"] = resolve_imports_against_local_files(pe, local_export_index)
            dependencies["api_catalog_assessment"] = assess_imported_symbols(pe)
            dependencies["graphics_assessment"] = assess_graphics_dependencies(pe, records)
    is_archive = target.is_file() and zipfile.is_zipfile(target)
    return {
        "schema_version": INSPECTOR_SCHEMA_VERSION,
        "tool": "orion_game_inspector",
        "source_name": target.name,
        "source_kind": (
            "directory" if target.is_dir()
            else "xdvdfs" if xdvdfs_report
            else "iso9660" if iso_report
            else "xcontent_package" if stfs_report
            else "zip_archive" if is_archive
            else "file"
        ),
        "files_inspected": len(records),
        "type_counts": dict(sorted(counts.items())),
        "shader_summary": shader_summary,
        "files": records,
        "iso9660": iso_report,
        "xdvdfs": xdvdfs_report,
        "stfs": stfs_report,
        "svod": svod_report,
        "warnings": warnings,
        "scope": "read_only_file_inventory_and_basic_signatures",
        "extraction_performed": False,
        "execution_performed": False,
        "drm_or_encryption_bypassed": False,
        "compatibility_established": False,
    }


def save_inspection_report(report: dict[str, Any], output: str | Path) -> Path:
    """Write an inspection report as UTF-8 JSON using atomic replacement."""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    try:
        with temporary.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    except OSError:
        temporary.unlink(missing_ok=True)
        raise
    return destination
