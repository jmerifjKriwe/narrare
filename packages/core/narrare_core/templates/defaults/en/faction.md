---
template_type: faction
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      founded:
        type: str
        description: When the faction was founded
      members:
        type: list
        description: Notable members of the faction
      ideology:
        type: str
        description: Core ideology or beliefs
      first_appearance:
        type: str
        description: First appearance in the story
  structure:
    label_key: kb.groups.structure
    description_key: kb.groups.structureHint
    order: 2
    fields:
      leadership:
        type: str
        description: Leadership structure or key leaders
      hierarchy:
        type: str
        description: Internal hierarchy or rank system
      membership_count:
        type: str
        description: Approximate number of members
      headquarters:
        type: str
        description: Main base or headquarters location
  belief_system:
    label_key: kb.groups.belief_system
    description_key: kb.groups.belief_systemHint
    order: 3
    fields:
      beliefs:
        type: list
        description: Core beliefs or tenets
      goals:
        type: list
        description: Primary goals or objectives
      methods:
        type: str
        description: Methods or tactics used
      taboos:
        type: list
        description: Forbidden actions or taboos
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      origin_story:
        type: str
        description: Origin story or founding myth
      key_events:
        type: list
        description: Key events in the faction's history
      current_status:
        type: str
        description: Current status or activity level
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
