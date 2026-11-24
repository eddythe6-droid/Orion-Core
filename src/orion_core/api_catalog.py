"""Small evidence-labelled Win32 symbol catalogue for static triage.

Entries identify API families only; they are not Xbox-to-Windows replacements.
"""
from __future__ import annotations

from typing import Any

WIN32_SYMBOLS: dict[str, dict[str, str]] = {
    "createfilew": {"family": "file_io", "module": "kernel32.dll", "description": "Open/create a file or device handle"},
    "readfile": {"family": "file_io", "module": "kernel32.dll", "description": "Read from a file or handle"},
    "writefile": {"family": "file_io", "module": "kernel32.dll", "description": "Write to a file or handle"},
    "closehandle": {"family": "handle_lifetime", "module": "kernel32.dll", "description": "Close an object handle"},
    "getoverlappedresult": {"family": "async_io", "module": "kernel32.dll", "description": "Retrieve overlapped I/O completion"},
    "createiocp": {"family": "async_io", "module": "kernel32.dll", "description": "Create an I/O completion port"},
    "getqueuedcompletionstatus": {"family": "async_io", "module": "kernel32.dll", "description": "Wait for I/O completion packets"},
    "virtualalloc": {"family": "virtual_memory", "module": "kernel32.dll", "description": "Reserve/commit virtual address space"},
    "virtualfree": {"family": "virtual_memory", "module": "kernel32.dll", "description": "Release/decommit virtual address space"},
    "virtualprotect": {"family": "virtual_memory", "module": "kernel32.dll", "description": "Change virtual-memory protection"},
    "heapalloc": {"family": "heap", "module": "kernel32.dll", "description": "Allocate from a heap"},
    "heapfree": {"family": "heap", "module": "kernel32.dll", "description": "Free a heap allocation"},
    "createthread": {"family": "threads", "module": "kernel32.dll", "description": "Create a thread"},
    "createthreadpoolwork": {"family": "thread_pool", "module": "kernel32.dll", "description": "Create a thread-pool work object"},
    "waitforsingleobject": {"family": "synchronization", "module": "kernel32.dll", "description": "Wait on a dispatcher object"},
    "waitformultipleobjects": {"family": "synchronization", "module": "kernel32.dll", "description": "Wait on multiple dispatcher objects"},
    "createmutexw": {"family": "synchronization", "module": "kernel32.dll", "description": "Create/open a mutex"},
    "createsemaphorew": {"family": "synchronization", "module": "kernel32.dll", "description": "Create/open a semaphore"},
    "queryperformancecounter": {"family": "timing", "module": "kernel32.dll", "description": "Read the high-resolution performance counter"},
    "gettickcount64": {"family": "timing", "module": "kernel32.dll", "description": "Read monotonic system tick count"},
    "getsystemtimeasfiletime": {"family": "timing", "module": "kernel32.dll", "description": "Read system time as FILETIME"},
    "getmodulehandlew": {"family": "module_loader", "module": "kernel32.dll", "description": "Get a loaded module handle"},
    "loadlibraryw": {"family": "module_loader", "module": "kernel32.dll", "description": "Load a module by name"},
    "getprocaddress": {"family": "module_loader", "module": "kernel32.dll", "description": "Resolve an exported procedure address"},
    "outputdebugstringw": {"family": "debug", "module": "kernel32.dll", "description": "Send a string to a debugger"},
    "getlasterror": {"family": "error_reporting", "module": "kernel32.dll", "description": "Retrieve calling-thread last-error value"},
    "coinitializeex": {"family": "com", "module": "combase.dll", "description": "Initialize COM for the calling thread"},
    "cocreateinstance": {"family": "com", "module": "combase.dll", "description": "Create a COM object"},
    "d3d12createdevice": {"family": "graphics_d3d12", "module": "d3d12.dll", "description": "Create a Direct3D 12 device"},
    "createdxgifactory2": {"family": "graphics_dxgi", "module": "dxgi.dll", "description": "Create a DXGI factory"},
    "xinputgetstate": {"family": "input_xinput", "module": "xinput1_4.dll", "description": "Read XInput controller state"},
    "xaudiocreate": {"family": "audio_xaudio2", "module": "xaudio2_9.dll", "description": "Create an XAudio2 engine"},
    "winhttpopen": {"family": "network_winhttp", "module": "winhttp.dll", "description": "Initialize a WinHTTP session"},
    "wsastartup": {"family": "network_winsock", "module": "ws2_32.dll", "description": "Initialize Winsock"},
}


def assess_imported_symbols(pe_analysis: dict[str, Any]) -> dict[str, Any]:
    """Classify exact known symbol names without inferring platform equivalence."""
    modules = []
    counts: dict[str, int] = {}
    for module in pe_analysis.get("import_modules", []):
        dll = str(module.get("dll", ""))
        symbols = []
        for imported in module.get("functions", []):
            if imported.get("kind") != "name":
                symbols.append({"import": imported, "status": "ordinal_not_catalogued"})
                continue
            name = str(imported.get("name", ""))
            entry = WIN32_SYMBOLS.get(name.casefold())
            if entry and entry["module"].casefold() == dll.casefold():
                status = "known_win32_api_family"
                counts[entry["family"]] = counts.get(entry["family"], 0) + 1
                symbols.append({"import": imported, "status": status, **entry})
            else:
                symbols.append({"import": imported, "status": "not_in_curated_catalogue"})
        modules.append({"module": dll, "symbols": symbols})
    return {
        "schema_version": 1,
        "modules": modules,
        "family_counts": counts,
        "catalogue_entries": len(WIN32_SYMBOLS),
        "evidence_level": "curated_exact_symbol_and_module_name",
        "platform_equivalence_established": False,
        "limitations": [
            "The catalogue is intentionally small and incomplete.",
            "A Win32 API family label is not proof that an Xbox API has equivalent semantics.",
            "Version, flags, threading rules, lifetime, error behavior and performance must be checked separately.",
            "Unknown symbols remain unknown; no fuzzy name matching is performed.",
        ],
    }
