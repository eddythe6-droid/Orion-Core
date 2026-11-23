"""Persistent, versioned history for Orion-Core diagnostic snapshots.

History is stored outside the repository in the user's application-data directory.
Writes are atomic; malformed records are reported rather than silently discarded.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HISTORY_SCHEMA_VERSION = 1


class HistoryStoreError(ValueError):
    """Raised when a history record cannot be read or validated."""


def default_history_dir() -> Path:
    """Return a per-user writable data directory without third-party dependencies."""
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "Orion-Core" / "history"
    if os.environ.get("XDG_DATA_HOME"):
        return Path(os.environ["XDG_DATA_HOME"]) / "orion-core" / "history"
    return Path.home() / ".local" / "share" / "orion-core" / "history"


class HistoryStore:
    """Store immutable JSON snapshots and retrieve them by stable ID."""

    def __init__(self, directory: str | Path | None = None) -> None:
        self.directory = Path(directory) if directory is not None else default_history_dir()

    @staticmethod
    def _validate_record(record: Any, expected_id: str | None = None) -> dict[str, Any]:
        if not isinstance(record, dict):
            raise HistoryStoreError("history record must be a JSON object")
        if record.get("schema_version") != HISTORY_SCHEMA_VERSION:
            raise HistoryStoreError("unsupported or missing history schema_version")
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id or Path(record_id).name != record_id:
            raise HistoryStoreError("history record id is malformed")
        if expected_id is not None and record_id != expected_id:
            raise HistoryStoreError("history filename and record id do not match")
        if not isinstance(record.get("created_at"), str):
            raise HistoryStoreError("history created_at must be a string")
        if not isinstance(record.get("kind"), str) or not record["kind"]:
            raise HistoryStoreError("history kind must be a non-empty string")
        if not isinstance(record.get("report"), dict):
            raise HistoryStoreError("history report must be a JSON object")
        return record

    def add_report(self, report: dict[str, Any], kind: str = "system_diagnostics") -> dict[str, Any]:
        if not isinstance(report, dict):
            raise HistoryStoreError("report must be a JSON object")
        if not isinstance(kind, str) or not kind.strip():
            raise HistoryStoreError("kind must be a non-empty string")
        record_id = uuid.uuid4().hex
        record = {
            "schema_version": HISTORY_SCHEMA_VERSION,
            "id": record_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "kind": kind.strip(),
            "report": report,
        }
        # Ensure the report is JSON-compatible before touching the filesystem.
        try:
            payload = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        except (TypeError, ValueError) as exc:
            raise HistoryStoreError(f"report is not valid JSON data: {type(exc).__name__}") from exc
        self.directory.mkdir(parents=True, exist_ok=True)
        destination = self.directory / f"{record_id}.json"
        temporary = self.directory / f".{record_id}.{uuid.uuid4().hex}.tmp"
        try:
            with temporary.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return record

    def load_report(self, record_id: str) -> dict[str, Any]:
        if not isinstance(record_id, str) or not record_id or Path(record_id).name != record_id:
            raise HistoryStoreError("history record id is malformed")
        path = self.directory / f"{record_id}.json"
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise HistoryStoreError(f"history record not found: {record_id}") from exc
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise HistoryStoreError(f"cannot read history record {record_id}: {type(exc).__name__}") from exc
        return self._validate_record(raw, expected_id=record_id)

    def list_reports(self) -> list[dict[str, Any]]:
        if not self.directory.exists():
            return []
        if not self.directory.is_dir():
            raise HistoryStoreError("history path is not a directory")
        records = []
        for path in self.directory.glob("*.json"):
            record = self.load_report(path.stem)
            records.append({
                "id": record["id"],
                "created_at": record["created_at"],
                "kind": record["kind"],
            })
        return sorted(records, key=lambda item: (item["created_at"], item["id"]), reverse=True)
