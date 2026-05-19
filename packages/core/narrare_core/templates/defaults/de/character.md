---
template_type: character
template_version: "2.1.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
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
      occupation:
        type: str
        description: Beruf oder Tätigkeit
      aliases:
        type: list
        description: Bekannte Aliasnamen oder Spitznamen
  appearance:
    label_key: kb.groups.appearance
    description_key: kb.groups.appearanceHint
    order: 2
    fields:
      height:
        type: str
        description: Körpergröße
      build:
        type: str
        description: Statur oder Körperbau
      hair_color:
        type: str
        description: Haarfarbe und Frisur
      eye_color:
        type: str
        description: Augenfarbe
      skin_tone:
        type: str
        description: Hautfarbe oder Teint
      distinctive_marks:
        type: str
        description: Narben, Tätowierungen, Muttermale oder andere Merkmale
      clothing_style:
        type: str
        description: Typische Kleidung oder Stil
  personality:
    label_key: kb.groups.personality
    description_key: kb.groups.personalityHint
    order: 3
    fields:
      traits:
        type: list
        description: Kernmerkmale der Persönlichkeit
      strengths:
        type: list
        description: Stärken der Figur
      weaknesses:
        type: list
        description: Schwächen oder Fehler
      fears:
        type: list
        description: Was die Figur fürchtet
      desires:
        type: list
        description: Ziele, Wünsche oder Bestrebungen
      motivations:
        type: str
        description: Was diese Figur antreibt
      quirks:
        type: list
        description: Ungewöhnliche Gewohnheiten oder Eigenarten
  background:
    label_key: kb.groups.background
    description_key: kb.groups.backgroundHint
    order: 4
    fields:
      family:
        type: str
        description: Familienhintergrund
      upbringing:
        type: str
        description: Wie die Figur aufgewachsen ist
      education:
        type: str
        description: Ausbildung oder Training
      key_events:
        type: list
        description: Schlüsselerlebnisse in der Vergangenheit
      formative_experiences:
        type: str
        description: Erfahrungen die die Figur geprägt haben
  relationships:
    label_key: kb.groups.relationships
    description_key: kb.groups.relationshipsHint
    order: 5
    fields:
      allies:
        type: list
        description: Bekannte Verbündete und Freunde
      rivals:
        type: list
        description: Rivalen und Antagonisten
      family_members:
        type: list
        description: Wichtige Familienmitglieder
      mentors:
        type: list
        description: Mentoren oder Lehrer
  development:
    label_key: kb.groups.development
    description_key: kb.groups.developmentHint
    order: 6
    fields:
      arc:
        type: str
        description: Charakterentwicklung oder Handlungsbogen
      starting_point:
        type: str
        description: Wo die Figur emotional/psychologisch beginnt
      key_turning_points:
        type: list
        description: Wichtige Wendepunkte im Charakterbogen
      current_state:
        type: str
        description: Aktueller emotionaler/psychologischer Zustand
      planned_arc:
        type: str
        description: Geplante Charakterentwicklung
      first_appearance:
        type: str
        description: Erster Auftritt in der Geschichte
  speech:
    label_key: kb.groups.speech
    description_key: kb.groups.speechHint
    order: 7
    fields:
      typical_phrases:
        type: list
        description: Charakteristische Formulierungen oder Ausdrücke
      dialect:
        type: str
        description: Dialekt, Akzent oder Sprechmuster
      vocabulary_quirks:
        type: str
        description: Ungewöhnlicher Wortschatz oder Sprechgewohnheiten
      body_language:
        type: str
        description: Charakteristische Gesten oder Körpersprache
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

# Charakter-Vorlage

Verwende diese Vorlage, um ein detailliertes Charakterprofil für deine Geschichte zu erstellen.

## Überblick

Beschreibe die Figur mit ihrer Persönlichkeit, Motivation und Rolle in der Erzählung.

## Hintergrund

Beschreibe die Geschichte, Erziehung und prägenden Erfahrungen der Figur.
