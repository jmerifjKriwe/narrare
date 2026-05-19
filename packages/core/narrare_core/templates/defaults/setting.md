---
template_type: setting
template_version: "3.0.0"
schema_version: "2.0.0"
field_groups:
  basics:
    label_key: kb.groups.settingBasics
    description_key: kb.groups.settingBasicsHint
    fields:
      genre:
        type: str
      time_period:
        type: str
      tone:
        type: str
      atmosphere:
        type: str
  world_rules:
    label_key: kb.groups.settingWorldRules
    description_key: kb.groups.settingWorldRulesHint
    fields:
      magic_level:
        type: str
      tech_level:
        type: str
      supernatural_elements:
        type: list
      limitations:
        type: list
  society:
    label_key: kb.groups.settingSociety
    description_key: kb.groups.settingSocietyHint
    fields:
      political_structure:
        type: str
      cultural_values:
        type: list
      social_classes:
        type: list
      major_conflicts:
        type: list
  geography:
    label_key: kb.groups.settingGeography
    description_key: kb.groups.settingGeographyHint
    fields:
      central_location:
        type: str
      landmarks:
        type: list
      dangerous_areas:
        type: list
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
