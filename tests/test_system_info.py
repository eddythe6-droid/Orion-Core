from orion_core.system_info import collect_system_info


def test_collect_system_info_has_expected_sections():
    report = collect_system_info()
    assert set(report) == {
        "os",
        "architecture",
        "processor",
        "logical_cpu_count",
        "memory_total_bytes",
        "python",
    }
    assert report["os"]["system"]
    assert report["architecture"]
    assert report["python"]["version"]


def test_cpu_count_is_positive_or_unavailable():
    count = collect_system_info()["logical_cpu_count"]
    assert count is None or count >= 1
