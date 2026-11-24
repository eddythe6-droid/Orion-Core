from orion_core.api_catalog import assess_imported_symbols


def test_catalogue_matches_exact_module_and_symbol_names():
    report = assess_imported_symbols({
        "import_modules": [
            {"dll": "KERNEL32.DLL", "functions": [
                {"kind": "name", "name": "CreateFileW"},
                {"kind": "name", "name": "VirtualAlloc"},
                {"kind": "name", "name": "CreateFileA"},
                {"kind": "ordinal", "ordinal": 12},
            ]},
            {"dll": "xgameplatform.dll", "functions": [
                {"kind": "name", "name": "CreateFileW"},
            ]},
        ]
    })
    first = report["modules"][0]["symbols"]
    assert first[0]["status"] == "known_win32_api_family"
    assert first[1]["family"] == "virtual_memory"
    assert first[2]["status"] == "not_in_curated_catalogue"
    assert first[3]["status"] == "ordinal_not_catalogued"
    assert report["modules"][1]["symbols"][0]["status"] == "not_in_curated_catalogue"
    assert report["platform_equivalence_established"] is False
