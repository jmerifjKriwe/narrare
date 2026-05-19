---
template_type: character
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    fields:
      age:
        type: int
        description: Character age
      role:
        type: str
        description: Role in the story (e.g. protagonist, antagonist, supporting)
      gender:
        type: str
        description: Character gender
      pronouns:
        type: str
        description: Preferred pronouns
      nationality:
        type: str
        description: Nationality or cultural origin
      pov_character:
        type: bool
        description: Is this a point-of-view character?
      affiliation:
        type: str
        description: Group or organization affiliation
      element:
        type: str
        description: Associated element or theme
      aliases:
        type: list
        description: Known aliases or nicknames
  development:
    label_key: kb.groups.development
    description_key: kb.groups.developmentHint
    fields:
      arc:
        type: str
        description: Character arc or development path
      first_appearance:
        type: str
        description: First appearance in the story
sections:
  background:
    label_key: kb.sections.background
    description_key: kb.sections.backgroundHint
    order: 1
  personality:
    label_key: kb.sections.personality
    description_key: kb.sections.personalityHint
    order: 2
---

# Character Template

Use this template to create a detailed character profile for your story.

## Overview

Provide a rich description of the character, including their personality,
motivations, and role in the narrative.

## Background

Describe the character's history, upbringing, and formative experiences
that shaped who they are.
