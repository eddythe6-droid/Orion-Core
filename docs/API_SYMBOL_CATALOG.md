# Curated Win32 API symbol catalogue

The Game Inspector includes a small, deliberately conservative catalogue of exact Win32 import names. It tags known symbols with broad API families such as file I/O, virtual memory, synchronization, timing, COM, D3D12, DXGI, input, audio and networking.

## Interpretation

A catalogue match means only that an imported name and its DLL match a curated Windows API entry. It does not prove that the Xbox-side call has the same contract, flags, threading behavior, object lifetime, error semantics, performance, or availability on a particular Windows build.

The catalogue does not guess Xbox replacements. Xbox/GDK-specific module names remain platform hints until a separately sourced and validated API contract exists. Unknown names and ordinal-only imports remain unknown. Matching is exact and case-insensitive; no fuzzy matching is used.

The catalogue is intentionally incomplete and versioned in code. It is a triage aid, not a compatibility layer or implementation.
