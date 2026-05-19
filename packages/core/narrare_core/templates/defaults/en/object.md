---
template_type: object
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      object_type:
        type: str
        description: Type of object (e.g. weapon, artifact, tool)
      owner:
        type: str
        description: Current owner or possessor
      origin:
        type: str
        description: Origin or creation history
      first_appearance:
        type: str
        description: First appearance in the story
  properties:
    label_key: kb.groups.properties
    description_key: kb.groups.propertiesHint
    order: 2
    fields:
      material:
        type: str
        description: Material or composition
      dimensions:
        type: str
        description: Physical dimensions or size
      weight:
        type: str
        description: Weight or heft
      condition:
        type: str
        description: Current condition or state of repair
      appearance:
        type: str
        description: Visual appearance and distinguishing features
  origin_details:
    label_key: kb.groups.origin_details
    description_key: kb.groups.origin_detailsHint
    order: 3
    fields:
      creator:
        type: str
        description: Who created the object
      created_date:
        type: str
        description: When the object was created
      place_of_origin:
        type: str
        description: Where the object was created
      method_of_creation:
        type: str
        description: How the object was made
  significance:
    label_key: kb.groups.significance
    description_key: kb.groups.significanceHint
    order: 4
    fields:
      purpose:
        type: str
        description: Primary purpose or function
      powers:
        type: list
        description: Special powers or abilities
      historical_significance:
        type: str
        description: Historical or cultural importance
      current_location:
        type: str
        description: Where the object is currently located
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
