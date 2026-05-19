---
template_type: character
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      age:
        type: int
      role:
        type: str
      gender:
        type: str
      pronouns:
        type: str
      nationality:
        type: str
      pov_character:
        type: bool
      affiliation:
        type: str
      element:
        type: str
      occupation:
        type: str
      aliases:
        type: list
  appearance:
    label_key: kb.groups.appearance
    description_key: kb.groups.appearanceHint
    order: 2
    fields:
      height:
        type: str
      build:
        type: str
      hair_color:
        type: str
      eye_color:
        type: str
      skin_tone:
        type: str
      distinctive_marks:
        type: str
      clothing_style:
        type: str
  personality:
    label_key: kb.groups.personality
    description_key: kb.groups.personalityHint
    order: 3
    fields:
      traits:
        type: list
      strengths:
        type: list
      weaknesses:
        type: list
      fears:
        type: list
      desires:
        type: list
      motivations:
        type: str
      quirks:
        type: list
  background:
    label_key: kb.groups.background
    description_key: kb.groups.backgroundHint
    order: 4
    fields:
      family:
        type: str
      upbringing:
        type: str
      education:
        type: str
      key_events:
        type: list
      formative_experiences:
        type: str
  relationships:
    label_key: kb.groups.relationships
    description_key: kb.groups.relationshipsHint
    order: 5
    fields:
      allies:
        type: list
      rivals:
        type: list
      family_members:
        type: list
      mentors:
        type: list
  development:
    label_key: kb.groups.development
    description_key: kb.groups.developmentHint
    order: 6
    fields:
      arc:
        type: str
      starting_point:
        type: str
      key_turning_points:
        type: list
      current_state:
        type: str
      planned_arc:
        type: str
      first_appearance:
        type: str
  speech:
    label_key: kb.groups.speech
    description_key: kb.groups.speechHint
    order: 7
    fields:
      typical_phrases:
        type: list
      dialect:
        type: str
      vocabulary_quirks:
        type: str
      body_language:
        type: str
sections:
  background:
    label_key: kb.sections.background
    description_key: kb.sections.backgroundHint
    order: 1
  personality:
    label_key: kb.sections.personality
    description_key: kb.sections.personalityHint
    order: 2
  notes:
    label_key: kb.sections.notes
    description_key: kb.sections.notesHint
    order: 3
---

# Character Template

Use this template to create a detailed character profile for your story.

## Overview

Provide a rich description of the character, including their personality,
motivations, and role in the narrative.

## Background

Describe the character's history, upbringing, and formative experiences
that shaped who they are.
