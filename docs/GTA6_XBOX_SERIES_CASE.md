# GTA VI Xbox Series build — evidence and intake plan

**Research snapshot:** 2026-11-23  
**Status:** reported release; binary not independently inspected by Orion-Core.

## What is currently reported

Several outlets report that CyberLeek published a missing executable for an alleged Xbox Series X|S build labelled **1.0.2.1 (Nov 2026)** on 23 November. The earlier package was described as approximately 209 GB. These reports establish that the release is being claimed and discussed; they do not establish that the binary is authentic, complete, safe, or runnable.

Reported SHA-256 values attributed to the release announcement:

- ZIP archive: `7545a2f7fb4b399cf8850987f087ed9a4d8499ddb6d6c2d642fd60c27f569730`
- EXE: `e95020b2fa4a721db3df59fdecf75621730ac559d8835252f6c3b658d5a08993`

These are **published reference strings only**. Orion-Core has not downloaded or hashed either file. A matching SHA-256 proves byte-for-byte agreement with whoever published that reference value; it does not prove Rockstar provenance, integrity of the whole game package, or safety.

## Critical format distinction

The current Orion-Core `xex.py` parser targets **Xbox 360 XEX2**. It is not the parser for an Xbox Series X|S executable. The reported target is Xbox Series / Scarlett and the relevant executable should be approached as a modern x64 PE/GDK application, subject to confirmation from the actual file's headers. Do not route it through the XEX2 parser merely because it is an Xbox executable.

The next Orion-Core work should be a separate, bounded **Xbox Series executable intake** path built on the existing PE analyzer:

1. Record file size and SHA-256 for a user-supplied, lawfully accessible file. Do not execute it.
2. Check DOS/PE signatures, machine type, PE32+ optional header, subsystem, section table, data directories and import descriptors.
3. Preserve raw values, file offsets, RVA/VA distinctions, parser warnings and unknown structures.
4. Inventory imported DLL names and imported symbols where safely mapped; do not resolve or invoke them.
5. Record Authenticode certificate-table presence and digest-verification status only if a separately reviewed, read-only verifier is added. Do not treat a signature mismatch as proof of malware or proof of authenticity.
6. Compare executable metadata against the sidecar DLL inventory and package manifest supplied by the user. Report unresolved imports and platform-specific dependencies as hypotheses.
7. Add synthetic fixtures and regression tests. No game binary is needed for parser development.

## What a PC compatibility investigation would need

A static executable inventory is only the starting point. A credible port/recompilation assessment also needs evidence for:

- CPU instruction coverage and calling conventions;
- Xbox GDK / Scarlett runtime and system-library dependencies;
- graphics command, resource, descriptor, shader and synchronization behavior;
- shader format and translation requirements;
- memory allocation, virtual memory, GPU residency and streaming;
- audio, input, storage, threading and networking interfaces;
- asset-container metadata and runtime loading behavior.

A PE header or successful shader conversion alone does not establish that the game can boot. Any full-game status must be tied to a reproducible run and clearly named hardware/software configuration.

## Safety and scope

This document does not link to leaked binaries or provide download instructions. Do not run unknown EXE files, use third-party “GTA 6 PC launchers,” or paste commands from download pages. Fake GTA VI PC clients have been documented using malware-delivery techniques.

Orion-Core remains a read-only research tool. It will not decrypt protected game content, bypass DRM, defeat signature checks, or execute the supplied game binary. Work on public format documentation, synthetic test inputs, and files the user is authorized to inspect.

## Sources

- [GameGPU, 23 Nov 2026 — report of the claimed executable release and published hashes](https://en.gamegpu.com/news/igry/cyberleek-opublikoval-ispolnyaemyj-fajl-gta-6-versii-1-0-2-1-dlya-xbox-na-tri-chasa-ranshe-sroka)
- [Rambler, 23 Nov 2026 — repeats the two SHA-256 values and explains their limited meaning](https://news.rambler.ru/games/57469179-cyberleek-vylozhil-exe-utekshey-sborki-gta-vi-entuziasty-poprobuyut-zapustit-igru-na-pk/)
- [Notebookcheck, 22 Nov 2026 — prior status, uncertainty and compatibility obstacles](https://www.notebookcheck.net/Can-Cyberleek-s-leaked-GTA-6-Xbox-build-become-a-PC-port-Three-GitHub-projects-are-trying-without-the-executable.1456848.0.html)
- [Bitdefender, 20 Nov 2026 — fake GTA VI PC client malware analysis](https://www.bitdefender.com/en-us/blog/labs/fake-gta-vi-pc-client-malware-clickfix)
- [Microsoft PE format documentation](https://learn.microsoft.com/en-us/windows/win32/debug/pe-format)

News reports and a leaker-provided checksum are not independent authentication of the game binary.
