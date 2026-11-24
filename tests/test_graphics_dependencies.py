from orion_core.graphics_dependencies import assess_graphics_dependencies


def test_graphics_dependencies_classify_imports_and_inventory():
    report = assess_graphics_dependencies({
        "import_modules": [
            {"dll": "D3D12.DLL", "functions": [
                {"kind": "name", "name": "D3D12CreateDevice"},
                {"kind": "name", "name": "UnknownGraphicsThing"},
            ]},
            {"dll": "dxgi.dll", "functions": [
                {"kind": "name", "name": "CreateDXGIFactory2"},
            ]},
            {"dll": "kernel32.dll", "functions": []},
        ]
    }, [
        {"path": "shaders/postprocess.dxil"},
        {"path": "textures/albedo.dds"},
        {"path": "readme.txt"},
    ])
    assert report["assessment"] == "graphics_dependencies_observed"
    assert report["module_family_counts"] == {"direct3d_12": 1, "dxgi": 1}
    assert report["symbol_family_counts"] == {
        "d3d12_device_creation": 1, "dxgi_factory_creation": 1
    }
    assert report["asset_inventory"]["shader_like_files"] == ["shaders/postprocess.dxil"]
    assert report["asset_inventory"]["texture_like_file_count"] == 1
    assert report["compatibility_established"] is False


def test_graphics_dependencies_keep_unknown_and_empty_evidence_conservative():
    report = assess_graphics_dependencies({"import_modules": []})
    assert report["assessment"] == "no_known_graphics_imports_observed"
    assert report["modules"] == []
    assert report["symbol_family_counts"] == {}
    assert report["execution_performed"] is False
