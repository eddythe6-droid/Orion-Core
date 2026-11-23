from datetime import datetime

from orion_core.report import REPORT_SCHEMA_VERSION, collect_diagnostics_report


def test_report_has_version_timestamp_environment_and_validation_scope():
    report = collect_diagnostics_report(include_windows=False)
    assert report["report_schema_version"] == REPORT_SCHEMA_VERSION
    parsed = datetime.fromisoformat(report["generated_at"].replace("Z", "+00:00"))
    assert parsed.tzinfo is not None
    assert report["collector"]["name"] == "Orion-Core"
    assert report["collector"]["version"]
    assert report["environment"]["python_version"]
    assert report["system"]["os"]["system"]
    assert report["windows_diagnostics"]["reason"] == "Skipped by --basic-only"
    assert report["validation"]["hardware_runtime_tests_performed"] is False


def test_report_does_not_claim_runtime_validation():
    report = collect_diagnostics_report(include_windows=False)
    assert "read-only host inventory" in report["validation"]["notes"][0]
