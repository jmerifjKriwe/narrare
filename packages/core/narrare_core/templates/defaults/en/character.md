---
template_type: character
template_version: "2.1.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
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
      occupation:
        type: str
        description: Profession or occupation
      aliases:
        type: list
        description: Known aliases or nicknames
  appearance:
    label_key: kb.groups.appearance
    description_key: kb.groups.appearanceHint
    order: 2
    fields:
      height:
        type: str
        description: Physical height
      build:
        type: str
        description: Body type or build
      hair_color:
        type: str
        description: Hair color and style
      eye_color:
        type: str
        description: Eye color
      skin_tone:
        type: str
        description: Skin tone or complexion
      distinctive_marks:
        type: str
        description: Scars, tattoos, birthmarks, or other distinctive features
      clothing_style:
        type: str
        description: Typical clothing or attire
  personality:
    label_key: kb.groups.personality
    description_key: kb.groups.personalityHint
    order: 3
    fields:
      traits:
        type: list
        description: Core personality traits (e.g. brave, cunning, gentle)
      strengths:
        type: list
        description: Character strengths
      weaknesses:
        type: list
        description: Character weaknesses or flaws
      fears:
        type: list
        description: What the character fears
      desires:
        type: list
        description: Goals, desires, or aspirations
      motivations:
        type: str
        description: What drives this character
      quirks:
        type: list
        description: Unusual habits or quirks
  background:
    label_key: kb.groups.background
    description_key: kb.groups.backgroundHint
    order: 4
    fields:
      family:
        type: str
        description: Family background
      upbringing:
        type: str
        description: How the character was raised
      education:
        type: str
        description: Education or training
      key_events:
        type: list
        description: Key formative events in the character's past
      formative_experiences:
        type: str
        description: Experiences that shaped who they are
  relationships:
    label_key: kb.groups.relationships
    description_key: kb.groups.relationshipsHint
    order: 5
    fields:
      allies:
        type: list
        description: Known allies and friends
      rivals:
        type: list
        description: Rivals and antagonists
      family_members:
        type: list
        description: Important family members
      mentors:
        type: list
        description: Mentors or teachers
  development:
    label_key: kb.groups.development
    description_key: kb.groups.developmentHint
    order: 6
    fields:
      arc:
        type: str
        description: Character arc or development path
      starting_point:
        type: str
        description: Where the character starts emotionally/psychologically
      key_turning_points:
        type: list
        description: Major turning points in the character's arc
      current_state:
        type: str
        description: Current emotional/psychological state
      planned_arc:
        type: str
        description: Planned character development trajectory
      first_appearance:
        type: str
        description: First appearance in the story
  speech:
    label_key: kb.groups.speech
    description_key: kb.groups.speechHint
    order: 7
    fields:
      typical_phrases:
        type: list
        description: Characteristic phrases or expressions
      dialect:
        type: str
        description: Dialect, accent, or speech patterns
      vocabulary_quirks:
        type: str
        description: Unusual vocabulary or speech habits
      body_language:
        type: str
        description: Characteristic gestures or body language
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
