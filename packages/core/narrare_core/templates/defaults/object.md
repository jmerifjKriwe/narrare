---
template_type: object
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      object_type:
        type: str
      owner:
        type: str
      origin:
        type: str
      first_appearance:
        type: str
  properties:
    label_key: kb.groups.properties
    description_key: kb.groups.propertiesHint
    order: 2
    fields:
      material:
        type: str
      dimensions:
        type: str
      weight:
        type: str
      condition:
        type: str
      appearance:
        type: str
  origin_details:
    label_key: kb.groups.origin_details
    description_key: kb.groups.origin_detailsHint
    order: 3
    fields:
      creator:
        type: str
      created_date:
        type: str
      place_of_origin:
        type: str
      method_of_creation:
        type: str
  significance:
    label_key: kb.groups.significance
    description_key: kb.groups.significanceHint
    order: 4
    fields:
      purpose:
        type: str
      powers:
        type: list
      historical_significance:
        type: str
      current_location:
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

# Object Template

Use this template to create a detailed object profile for important
items in your story.

## Overview

Describe the object's appearance, properties, and significance.
