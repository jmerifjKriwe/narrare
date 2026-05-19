"""Setting entity metadata schema.

A setting captures project-level world rules, genre, atmosphere,
and the broader context in which the story unfolds.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .base import KBEntryMetadata


class SettingBasics(BaseModel):
    """Core setting characteristics."""

    model_config = ConfigDict(extra="allow")

    genre: str | None = None
    time_period: str | None = None
    tone: str | None = None
    atmosphere: str | None = None


class SettingWorldRules(BaseModel):
    """Fundamental rules governing the world."""

    model_config = ConfigDict(extra="allow")

    magic_level: str | None = None
    tech_level: str | None = None
    supernatural_elements: list[str] | None = None
    limitations: list[str] | None = None


class SettingSociety(BaseModel):
    """Societal structures and dynamics."""

    model_config = ConfigDict(extra="allow")

    political_structure: str | None = None
    cultural_values: list[str] | None = None
    social_classes: list[str] | None = None
    major_conflicts: list[str] | None = None


class SettingGeography(BaseModel):
    """Geographic context of the setting."""

    model_config = ConfigDict(extra="allow")

    central_location: str | None = None
    landmarks: list[str] | None = None
    dangerous_areas: list[str] | None = None


class SettingMetadata(KBEntryMetadata):
    """Metadata for setting KB entries with grouped fields.

    All fields are optional — the template is a recommendation, not
    enforcement.  ``extra="allow"`` is inherited from KBEntryMetadata.
    """

    # Flat fields for backward compat
    setting_type: str | None = None
    # Nested groups
    basics: SettingBasics | None = None
    world_rules: SettingWorldRules | None = None
    society: SettingSociety | None = None
    geography: SettingGeography | None = None
