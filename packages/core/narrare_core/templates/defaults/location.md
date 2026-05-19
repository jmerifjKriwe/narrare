---
template_type: location
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      location_type:
        type: str
      parent_location:
        type: str
      coordinates:
        type: str
      climate:
        type: str
      terrain:
        type: str
      size:
        type: str
  features:
    label_key: kb.groups.features
    description_key: kb.groups.featuresHint
    order: 2
    fields:
      architecture:
        type: str
      natural_features:
        type: list
      landmarks:
        type: list
      atmosphere:
        type: str
  inhabitants:
    label_key: kb.groups.inhabitants
    description_key: kb.groups.inhabitantsHint
    order: 3
    fields:
      population:
        type: str
      species:
        type: list
      factions:
        type: list
      notable_residents:
        type: list
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      founded:
        type: str
      key_events:
        type: list
      current_state:
        type: str
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
