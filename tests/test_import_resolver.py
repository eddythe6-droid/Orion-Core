from orion_core.import_resolver import build_local_export_index, resolve_imports_against_local_files


def test_matches_named_ordinal_and_forwarded_exports():
    index = build_local_export_index([
        {"path": "bin/engine.dll", "pe_analysis": {
            "valid_pe_structure": True, "architecture": "x86_64",
            "exports_truncated_or_unavailable": False,
            "exported_functions": [
                {"ordinal": 7, "names": ["CreateThing"], "is_forwarder": False},
                {"ordinal": 8, "names": [], "is_forwarder": False},
                {"ordinal": 9, "names": ["Forwarded"], "is_forwarder": True,
                 "forwarder": "OTHER.Real"},
            ],
        }},
    ])
    result = resolve_imports_against_local_files({
        "architecture": "x86_64",
        "import_modules": [{"dll": "ENGINE.DLL", "functions": [
            {"kind": "name", "name": "CreateThing"},
            {"kind": "ordinal", "ordinal": 8},
            {"kind": "name", "name": "Forwarded"},
            {"kind": "name", "name": "Missing"},
        ]}],
    }, index)
    statuses = [item["status"] for item in result["modules"][0]["symbols"]]
    assert statuses == ["resolved_name_match", "resolved_ordinal_match",
                        "forwarded_export", "missing_symbol"]
    assert result["counts"]["forwarded_export"] == 1
    assert result["compatibility_established"] is False


def test_reports_missing_ambiguous_and_architecture_mismatch():
    index = build_local_export_index([
        {"path": "a/foo.dll", "pe_analysis": {"valid_pe_structure": True,
         "architecture": "x86", "exported_functions": []}},
        {"path": "b/foo.dll", "pe_analysis": {"valid_pe_structure": True,
         "architecture": "x86", "exported_functions": []}},
        {"path": "bar.dll", "pe_analysis": {"valid_pe_structure": True,
         "architecture": "x86", "exported_functions": []}},
    ])
    result = resolve_imports_against_local_files({
        "architecture": "x86_64",
        "import_modules": [
            {"dll": "absent.dll", "functions": []},
            {"dll": "foo.dll", "functions": []},
            {"dll": "bar.dll", "functions": [{"kind": "name", "name": "X"}]},
        ],
    }, index)
    assert [item["status"] for item in result["modules"]] == [
        "missing_module", "ambiguous_module", "architecture_mismatch"
    ]
    assert result["execution_performed"] is False
