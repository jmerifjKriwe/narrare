---
template_type: setting
template_version: "2.0.0"
template_language: en
schema_version: "2.0.0"
field_groups:
  basics:
    label_key: kb.groups.settingBasics
    description_key: kb.groups.settingBasicsHint
    fields:
      genre:
        type: str
        description: Primary genre of the story (e.g. fantasy, sci-fi, historical)
      time_period:
        type: str
        description: Time period or era of the story
      tone:
        type: str
        description: Overall tone (e.g. dark, hopeful, satirical)
      atmosphere:
        type: str
        description: Dominant atmosphere or mood of the world
  world_rules:
    label_key: kb.groups.settingWorldRules
    description_key: kb.groups.settingWorldRulesHint
    fields:
      magic_level:
        type: str
        description: Level and prevalence of magic in the world
      tech_level:
        type: str
        description: Level of technological advancement
      supernatural_elements:
        type: list
        description: Supernatural or fantastical elements present
      limitations:
        type: list
        description: Key limitations or constraints of this world
  society:
    label_key: kb.groups.settingSociety
    description_key: kb.groups.settingSocietyHint
    fields:
      political_structure:
        type: str
        description: System of governance (e.g. monarchy, democracy, theocracy)
      cultural_values:
        type: list
        description: Core cultural values and beliefs
      social_classes:
        type: list
        description: Social class structure and hierarchy
      major_conflicts:
        type: list
        description: Major societal conflicts or tensions
  geography:
    label_key: kb.groups.settingGeography
    description_key: kb.groups.settingGeographyHint
    fields:
      central_location:
        type: str
        description: Primary or central location of the story
      landmarks:
        type: list
        description: Important landmarks or places of interest
      dangerous_areas:
        type: list
        description: Hazardous or forbidden areas
sections:
  world_description:
    label_key: kb.sections.worldDescription
    description_key: kb.sections.worldDescriptionHint
    order: 1
  notes:
    label_key: kb.sections.notes
    description_key: kb.sections.notesHint
    order: 2
---
# Setting Template

Use this template to define the overarching world rules, genre conventions,
and atmospheric backdrop for your story.

## World Description

Describe the world in detail — its geography, the daily life of its inhabitants,
the balance of power, and what makes it unique.

## Notes

Additional worldbuilding notes, inspirations, or ideas that don't fit elsewhere.
