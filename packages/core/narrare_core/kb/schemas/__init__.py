"""KB metadata schemas — Pydantic models for entity-type-specific metadata.

Public exports:
    KBEntry — Discriminated union (Series-Canon | Novel-Overlay), Schema 2A+STI
    KBEntryBase — Common fields for all KB entries (scope-aware STI base)
    SeriesKBEntry — Series-Canon KB entry (novel_id IS NULL)
    NovelKBEntry — Novel-Overlay KB entry (novel_id IS NOT NULL)
    KBEntryMetadata — Base model (fallback for unknown entity types)
    CharacterMetadata — Character entity metadata (inc. grouped fields)
    LocationMetadata — Location entity metadata (inc. grouped fields)
    FactionMetadata — Faction entity metadata (inc. grouped fields)
    ObjectMetadata — Object entity metadata (inc. grouped fields)
    SystemMetadata — System entity metadata (inc. grouped fields)
    TimelineMetadata — Timeline entity metadata (inc. grouped fields)
    ConceptMetadata — Concept entity metadata (inc. grouped fields)
    SettingMetadata — Setting entity metadata (inc. grouped fields)
    AppearanceFields — Character physical appearance
    PersonalityFields — Character personality traits
    BackgroundFields — Character background
    SpeechPatterns — Character speech patterns
    VoiceAnalysis — Machine-derived character voice profile (ANAL-008/ADR-055)
    VoiceMetrics — Deterministic numeric voice metrics (ADR-021/ADR-055)
    RelationshipFields — Character relationships
    DevelopmentFields — Character development arc
    LocationFeatures — Geographic/architectural features
    LocationInhabitants — Location population details
    LocationHistory — Location historical context
    FactionStructure — Faction organisational structure
    FactionIdeology — Faction beliefs and goals
    FactionHistory — Faction historical background
    ObjectProperties — Object physical properties
    ObjectOrigin — Object origin details
    ObjectSignificance — Object story significance
    SystemMechanics — System rules and mechanics
    SystemPractitioners — System practitioners
    SystemOrigins — System origin details
    TimelinePeriod — Timeline time period info
    TimelineEvents — Timeline key events
    ConceptDefinition — Concept definition group
    ConceptHistory — Concept history group
    SettingBasics — Setting basic characteristics
    SettingWorldRules — Setting world rules group
    SettingSociety — Setting society group
    SettingGeography — Setting geography group
    SCHEMA_REGISTRY — Mapping of entity type strings to schema classes
    get_schema — Lookup helper returning the correct schema class
"""

from .base import KBEntryMetadata
from .character import (
    AppearanceFields,
    BackgroundFields,
    CharacterMetadata,
    DevelopmentFields,
    PersonalityFields,
    RelationshipFields,
    SpeechPatterns,
    VoiceAnalysis,
    VoiceMetrics,
)
from .concept import ConceptDefinition, ConceptHistory, ConceptMetadata
from .entry import KBEntry, KBEntryBase, NovelKBEntry, SeriesKBEntry
from .faction import FactionHistory, FactionIdeology, FactionMetadata, FactionStructure
from .location import (
    LocationFeatures,
    LocationHistory,
    LocationInhabitants,
    LocationMetadata,
)
from .object import ObjectMetadata, ObjectOrigin, ObjectProperties, ObjectSignificance
from .registry import SCHEMA_REGISTRY, get_schema
from .setting import (
    SettingBasics,
    SettingGeography,
    SettingMetadata,
    SettingSociety,
    SettingWorldRules,
)
from .system import SystemMechanics, SystemMetadata, SystemOrigins, SystemPractitioners
from .timeline import TimelineEvents, TimelineMetadata, TimelinePeriod

__all__ = [
    "SCHEMA_REGISTRY",
    "AppearanceFields",
    "BackgroundFields",
    "CharacterMetadata",
    "ConceptDefinition",
    "ConceptHistory",
    "ConceptMetadata",
    "DevelopmentFields",
    "FactionHistory",
    "FactionIdeology",
    "FactionMetadata",
    "FactionStructure",
    "KBEntry",
    "KBEntryBase",
    "KBEntryMetadata",
    "LocationFeatures",
    "LocationHistory",
    "LocationInhabitants",
    "LocationMetadata",
    "NovelKBEntry",
    "ObjectMetadata",
    "ObjectOrigin",
    "ObjectProperties",
    "ObjectSignificance",
    "PersonalityFields",
    "RelationshipFields",
    "SeriesKBEntry",
    "SettingBasics",
    "SettingGeography",
    "SettingMetadata",
    "SettingSociety",
    "SettingWorldRules",
    "SpeechPatterns",
    "SystemMechanics",
    "SystemMetadata",
    "SystemOrigins",
    "SystemPractitioners",
    "TimelineEvents",
    "TimelineMetadata",
    "TimelinePeriod",
    "VoiceAnalysis",
    "VoiceMetrics",
    "get_schema",
]
