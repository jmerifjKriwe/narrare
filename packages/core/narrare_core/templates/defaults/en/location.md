---
template_type: location
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      location_type:
        type: str
        description: Type of location (e.g. city, forest, building)
      parent_location:
        type: str
        description: Parent or containing location
      coordinates:
        type: str
        description: Geographic coordinates or position
      climate:
        type: str
        description: Climate or weather patterns
      terrain:
        type: str
        description: Terrain or landscape features
      size:
        type: str
        description: Size or scale of the location
  features:
    label_key: kb.groups.features
    description_key: kb.groups.featuresHint
    order: 2
    fields:
      architecture:
        type: str
        description: Architectural style or building types
      natural_features:
        type: list
        description: Notable natural features
      landmarks:
        type: list
        description: Important landmarks or points of interest
      atmosphere:
        type: str
        description: Overall atmosphere or mood of the location
  inhabitants:
    label_key: kb.groups.inhabitants
    description_key: kb.groups.inhabitantsHint
    order: 3
    fields:
      population:
        type: str
        description: Population size or density
      species:
        type: list
        description: Species or races that inhabit the location
      factions:
        type: list
        description: Factions or groups present in the location
      notable_residents:
        type: list
        description: Notable residents or inhabitants
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      founded:
        type: str
        description: When the location was founded or established
      key_events:
        type: list
        description: Key historical events at this location
      current_state:
        type: str
        description: Current condition or status of the location
sections:
  description:
    label_key: kb.sections.description
    description_key: kb.sections.descriptionHint
    order: 1
  notes:
    label_key: kb.sections.notes
    description_key: kb.sections.notesHint
    order: 2
---

# Location Template

Use this template to create a detailed location profile for your story's world.

## Overview

Provide a vivid description of the location, including its atmosphere,
unique features, and significance in the narrative.
