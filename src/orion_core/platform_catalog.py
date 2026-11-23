"""Curated platform facts from public Microsoft GDK documentation.

These records describe platform contracts, not any specific game's implementation.
Review source URLs and checked_on dates when refreshing this catalogue.
"""
from __future__ import annotations

from orion_core.evidence import EvidenceRecord
from orion_core.capability import CapabilityInventory

CHECKED_ON = "2026-11-23"

_RECORDS = (
    EvidenceRecord(
        claim_id="GDK-API-001",
        subsystem="os_api",
        claim="The GDK defines a common Win32 gaming API subset intended for Windows PC and Xbox targets.",
        platform="both",
        classification="common",
        status="confirmed_fact",
        confidence="high",
        checked_on=CHECKED_ON,
        source_url="https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604",
        source_title="What is the Microsoft Game Development Kit?",
        notes="Common API availability does not imply identical OS behavior, package layout, or permissions.",
    ),
    EvidenceRecord(
        claim_id="GDK-GFX-001",
        subsystem="graphics",
        claim="Xbox GDK titles use D3D12.x; D3D11.x is not supported on Xbox by the GDK.",
        platform="xbox",
        classification="xbox_only",
        status="confirmed_fact",
        confidence="high",
        checked_on=CHECKED_ON,
        source_url="https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604",
        source_title="What is the Microsoft Game Development Kit?",
        notes="This records the Xbox API contract; it does not establish which API any particular game uses.",
    ),
    EvidenceRecord(
        claim_id="GDK-GFX-002",
        subsystem="graphics",
        claim="The GDK documentation describes separate stock D3D12 PC and D3D12.x Xbox build configurations.",
        platform="both",
        classification="extension",
        status="confirmed_fact",
        confidence="high",
        checked_on=CHECKED_ON,
        source_url="https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/get-started/overviews/developing-new-titles-on-gamecore?view=gdk-2604",
        source_title="Developing a new title with the GDK in Visual Studio",
        notes="Microsoft recommends platform-specific build configurations and conditional code or separate platform DLLs where required.",
    ),
    EvidenceRecord(
        claim_id="GDK-RUNTIME-001",
        subsystem="runtime",
        claim="Gaming Runtime is separately serviceable on Windows PC and ships as part of Game OS on Xbox.",
        platform="both",
        classification="common",
        status="confirmed_fact",
        confidence="high",
        checked_on=CHECKED_ON,
        source_url="https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604",
        source_title="What is the Microsoft Game Development Kit?",
        notes="A PC port must validate runtime installation and availability rather than assume the Xbox deployment model.",
    ),
    EvidenceRecord(
        claim_id="GDK-MEM-001",
        subsystem="memory_resources",
        claim="Xbox Game OS provides explicit CPU, GPU, memory-resource and I/O guarantees for supported title configurations.",
        platform="xbox",
        classification="xbox_only",
        status="confirmed_fact",
        confidence="high",
        checked_on=CHECKED_ON,
        source_url="https://learn.microsoft.com/en-us/xbox/gdk/docs/gdk-dev/intro/introduction?view=gdk-2604",
        source_title="What is the Microsoft Game Development Kit?",
        notes="These guarantees must not be assumed on heterogeneous Windows PC hardware.",
    ),
    EvidenceRecord(
        claim_id="GDK-PROJECT-001",
        subsystem="build_system",
        claim="A GDK title can target PC, Xbox, or both from a common codebase with platform-specific build configurations.",
        platform="both",
        classification="common",
        status="confirmed_fact",
        confidence="high",
        checked_on=CHECKED_ON,
        source_url="https://learn.microsoft.com/en-us/gaming/gdk/docs/gdk-dev/get-started/overviews/developing-new-titles-on-gamecore?view=gdk-2604",
        source_title="Developing a new title with the GDK in Visual Studio",
        notes="Shared source code is not equivalent to binary compatibility or zero porting work.",
    ),
)


def load_platform_inventory() -> CapabilityInventory:
    """Return a fresh immutable inventory of curated public platform facts."""
    return CapabilityInventory(_RECORDS)
