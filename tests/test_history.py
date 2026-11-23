import json

import pytest

from orion_core.history import HistoryStore, HistoryStoreError


def test_history_round_trip_and_newest_first(tmp_path):
    store = HistoryStore(tmp_path / "history")
    first = store.add_report({"system": {"cpu": "A"}})
    second = store.add_report({"system": {"cpu": "B"}})

    assert store.load_report(first["id"])["report"]["system"]["cpu"] == "A"
    entries = store.list_reports()
    assert {item["id"] for item in entries} == {first["id"], second["id"]}
    assert entries[0]["created_at"] >= entries[1]["created_at"]


def test_history_rejects_non_json_data_without_creating_record(tmp_path):
    store = HistoryStore(tmp_path)
    with pytest.raises(HistoryStoreError, match="valid JSON"):
        store.add_report({"bad": object()})
    assert store.list_reports() == []


def test_history_reports_corrupt_record_instead_of_silently_skipping(tmp_path):
    store = HistoryStore(tmp_path)
    store.directory.mkdir(parents=True)
    (store.directory / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(HistoryStoreError, match="cannot read"):
        store.list_reports()


def test_history_validates_filename_and_record_id(tmp_path):
    store = HistoryStore(tmp_path)
    record = store.add_report({"ok": True})
    path = store.directory / f"{record['id']}.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["id"] = "different"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(HistoryStoreError, match="do not match"):
        store.load_report(record["id"])


def test_history_missing_record_is_clear_error(tmp_path):
    with pytest.raises(HistoryStoreError, match="not found"):
        HistoryStore(tmp_path).load_report("missing")
