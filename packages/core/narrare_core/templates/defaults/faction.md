---
template_type: faction
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      founded:
        type: str
      members:
        type: list
      ideology:
        type: str
      first_appearance:
        type: str
  structure:
    label_key: kb.groups.structure
    description_key: kb.groups.structureHint
    order: 2
    fields:
      leadership:
        type: str
      hierarchy:
        type: str
      membership_count:
        type: str
      headquarters:
        type: str
  belief_system:
    label_key: kb.groups.belief_system
    description_key: kb.groups.belief_systemHint
    order: 3
    fields:
      beliefs:
        type: list
      goals:
        type: list
      methods:
        type: str
      taboos:
        type: list
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      origin_story:
        type: str
      key_events:
        type: list
      current_status:
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

# Faction Template

Use this template to create a detailed faction profile for your story's world.

## Overview

Describe the faction's goals, structure, and role in the narrative.
