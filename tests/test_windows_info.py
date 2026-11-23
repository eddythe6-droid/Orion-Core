from unittest.mock import patch

from orion_core import windows_info


def test_windows_diagnostics_is_guarded_off_windows():
    with patch.object(windows_info.os, "name", "posix"):
        report = windows_info.collect_windows_diagnostics()
    assert report == {"supported": False, "reason": "Available only on Windows"}


def test_powershell_inventory_is_not_run_off_windows():
    with patch.object(windows_info.os, "name", "posix"):
        report = windows_info._powershell_inventory()
    assert report["available"] is False
