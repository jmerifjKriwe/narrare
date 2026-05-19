---
template_type: system
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      system_type:
        type: str
        description: Type of system (e.g. magic, technology, political)
      practitioners:
        type: list
        description: Known practitioners or users
      first_appearance:
        type: str
        description: First appearance in the story
  mechanics:
    label_key: kb.groups.mechanics
    description_key: kb.groups.mechanicsHint
    order: 2
    fields:
      rules:
        type: list
        description: Core rules or laws governing the system
      cost:
        type: str
        description: Cost or price of using the system
      limitations:
        type: list
        description: Known limitations or restrictions
      levels:
        type: list
        description: Proficiency levels or tiers
  practitioner_details:
    label_key: kb.groups.practitioner_details
    description_key: kb.groups.practitioner_detailsHint
    order: 3
    fields:
      users:
        type: list
        description: Notable users or wielders
      requirements:
        type: str
        description: Requirements to use the system
      training:
        type: str
        description: Training or initiation process
      organizations:
        type: list
        description: Related organizations or schools
  origins:
    label_key: kb.groups.origins
    description_key: kb.groups.originsHint
    order: 4
    fields:
      source:
        type: str
        description: Origin or source of the system
      discovered_by:
        type: str
        description: Who discovered or created the system
      discovered_date:
        type: str
        description: When the system was discovered
      history:
        type: str
        description: History and evolution of the system
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

# System Template

Use this template to create a detailed system profile for your story's
world-building (magic systems, technology, social structures, etc.).

## Overview

Describe the system's rules, limitations, and impact on the world.
