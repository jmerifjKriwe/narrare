---
template_type: timeline
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  period:
    label_key: kb.groups.period
    description_key: kb.groups.periodHint
    order: 1
    fields:
      era:
        type: str
      era_name:
        type: str
      start_date:
        type: str
      end_date:
        type: str
      duration:
        type: str
      first_appearance:
        type: str
  events:
    label_key: kb.groups.events
    description_key: kb.groups.eventsHint
    order: 2
    fields:
      major_events:
        type: list
      key_figures:
        type: list
      conflicts:
        type: list
      discoveries:
        type: list
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
