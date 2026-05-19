---
template_type: character
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    fields:
      age:
        type: int
        description: Alter der Figur
      role:
        type: str
        description: Rolle in der Geschichte (z.B. Protagonist, Antagonist)
      gender:
        type: str
        description: Geschlecht der Figur
      pronouns:
        type: str
        description: Bevorzugte Pronomen
      nationality:
        type: str
        description: Nationalität oder kulturelle Herkunft
      pov_character:
        type: bool
        description: Ist dies eine Erzählerfigur?
      affiliation:
        type: str
        description: Gruppen- oder Organisationszugehörigkeit
      element:
        type: str
        description: Zugeordnetes Element oder Thema
      aliases:
        type: list
        description: Bekannte Aliasnamen oder Spitznamen
  development:
    label_key: kb.groups.development
    description_key: kb.groups.developmentHint
    fields:
      arc:
        type: str
        description: Charakterentwicklung oder Handlungsbogen
      first_appearance:
        type: str
        description: Erster Auftritt in der Geschichte
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

# Charakter-Vorlage

Verwende diese Vorlage, um ein detailliertes Charakterprofil für deine Geschichte zu erstellen.

## Überblick

Beschreibe die Figur mit ihrer Persönlichkeit, Motivation und Rolle in der Erzählung.

## Hintergrund

Beschreibe die Geschichte, Erziehung und prägenden Erfahrungen der Figur.
