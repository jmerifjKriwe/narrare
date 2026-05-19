---
template_type: timeline
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  period:
    label_key: kb.groups.period
    description_key: kb.groups.periodHint
    order: 1
    fields:
      era:
        type: str
        description: Era or period name
      era_name:
        type: str
        description: Common name for this era
      start_date:
        type: str
        description: Start of the timeline period
      end_date:
        type: str
        description: End of the timeline period
      duration:
        type: str
        description: Total duration of the period
      first_appearance:
        type: str
        description: First appearance in the story
  events:
    label_key: kb.groups.events
    description_key: kb.groups.eventsHint
    order: 2
    fields:
      major_events:
        type: list
        description: Major events during this period
      key_figures:
        type: list
        description: Key figures or individuals
      conflicts:
        type: list
        description: Conflicts or wars during this period
      discoveries:
        type: list
        description: Important discoveries or inventions
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

# Timeline Template

Use this template to create a detailed timeline entry for your story's
chronology.

## Overview

Describe the key events, transitions, and significance of this
time period in your story's world.
