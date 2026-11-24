from orion_core.dependency_analysis import build_dependency_report


def test_classifies_windows_xbox_and_unknown_imports():
    report = build_dependency_report({
        "imported_dlls": ["KERNEL32.DLL", "xgameruntime.dll", "custom_rt.dll"],
        "import_modules": [
            {"dll": "KERNEL32.DLL", "functions": [{"kind": "name", "name": "CreateFileW"}]},
            {"dll": "xgameruntime.dll", "functions": []},
            {"dll": "custom_rt.dll", "functions": []},
        ],
        "delay_import_modules": [{"dll": "D3D12_XS.DLL"}],
    })
    by_name = {item["module"].casefold(): item for item in report["modules"]}
    assert by_name["kernel32.dll"]["classification"] == "windows_module_name_candidate"
    assert by_name["xgameruntime.dll"]["classification"] == "xbox_platform_module_hint"
    assert by_name["custom_rt.dll"]["classification"] == "unclassified_module"
    assert by_name["d3d12_xs.dll"]["delay_load_import"] is True
    assert report["execution_performed"] is False
    assert report["compatibility_established"] is False


def test_handles_empty_or_partial_pe_report():
    report = build_dependency_report({})
    assert report["module_count"] == 0
    assert report["classification_counts"] == {
        "windows_module_name_candidate": 0,
        "xbox_platform_module_hint": 0,
        "unclassified_module": 0,
    }
