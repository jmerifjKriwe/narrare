---
template_type: concept
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  definition:
    label_key: kb.groups.conceptDefinition
    description_key: kb.groups.conceptDefinitionHint
    fields:
      category:
        type: str
        description: Category of the concept (e.g. technology, society, magic, philosophy)
      summary:
        type: str
        description: Brief one-sentence summary of the concept
      key_principles:
        type: list
        description: Core principles or tenets that define this concept
      rules:
        type: list
        description: Specific rules or laws governing this concept
      implications:
        type: str
        description: Broader implications of this concept on the world
  history:
    label_key: kb.groups.conceptHistory
    description_key: kb.groups.conceptHistoryHint
    fields:
      origin:
        type: str
        description: How or where the concept originated
      discovery:
        type: str
        description: How the concept was discovered or came to be known
      key_figures:
        type: list
        description: Important figures associated with this concept
      evolution:
        type: str
        description: How the concept has evolved over time
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
