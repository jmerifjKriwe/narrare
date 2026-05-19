---
template_type: system
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      system_type:
        type: str
      practitioners:
        type: list
      first_appearance:
        type: str
  mechanics:
    label_key: kb.groups.mechanics
    description_key: kb.groups.mechanicsHint
    order: 2
    fields:
      rules:
        type: list
      cost:
        type: str
      limitations:
        type: list
      levels:
        type: list
  practitioner_details:
    label_key: kb.groups.practitioner_details
    description_key: kb.groups.practitioner_detailsHint
    order: 3
    fields:
      users:
        type: list
      requirements:
        type: str
      training:
        type: str
      organizations:
        type: list
  origins:
    label_key: kb.groups.origins
    description_key: kb.groups.originsHint
    order: 4
    fields:
      source:
        type: str
      discovered_by:
        type: str
      discovered_date:
        type: str
      history:
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

# System Template

Use this template to create a detailed system profile for your story's
world-building (magic systems, technology, social structures, etc.).

## Overview

Describe the system's rules, limitations, and impact on the world.
