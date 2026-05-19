---
template_type: concept
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  definition:
    label_key: kb.groups.conceptDefinition
    description_key: kb.groups.conceptDefinitionHint
    fields:
      category:
        type: str
      summary:
        type: str
      key_principles:
        type: list
      rules:
        type: list
      implications:
        type: str
  history:
    label_key: kb.groups.conceptHistory
    description_key: kb.groups.conceptHistoryHint
    fields:
      origin:
        type: str
      discovery:
        type: str
      key_figures:
        type: list
      evolution:
        type: str
sections:
  description:
    label_key: kb.sections.description
    description_key: kb.sections.descriptionHint
    order: 1
  implications:
    label_key: kb.sections.implications
    description_key: kb.sections.implicationsHint
    order: 2
---
# Concept Template

Use this template to define abstract worldbuilding elements like technologies,
magic systems, philosophical ideas, or social structures.

## Description

Provide a thorough description of the concept, including how it works,
who interacts with it, and its role in the world.

## Implications

Describe the broader implications of this concept — how does it affect
society, technology, culture, or the story's conflict?
