---
template_type: faction
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      founded:
        type: str
        description: Gründungsdatum der Fraktion
      members:
        type: list
        description: Bekannte Mitglieder der Fraktion
      ideology:
        type: str
        description: Kernideologie oder Überzeugungen
      first_appearance:
        type: str
        description: Erster Auftritt in der Geschichte
  structure:
    label_key: kb.groups.structure
    description_key: kb.groups.structureHint
    order: 2
    fields:
      leadership:
        type: str
        description: Führungsstruktur oder wichtige Anführer
      hierarchy:
        type: str
        description: Interne Hierarchie oder Rangordnung
      membership_count:
        type: str
        description: Ungefähre Mitgliederzahl
      headquarters:
        type: str
        description: Hauptquartier oder Hauptsitz
  belief_system:
    label_key: kb.groups.belief_system
    description_key: kb.groups.belief_systemHint
    order: 3
    fields:
      beliefs:
        type: list
        description: Grundüberzeugungen oder Leitsätze
      goals:
        type: list
        description: Primäre Ziele oder Zielsetzungen
      methods:
        type: str
        description: Methoden oder Taktiken
      taboos:
        type: list
        description: Verbotene Handlungen oder Tabus
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      origin_story:
        type: str
        description: Ursprungsgeschichte oder Gründungsmythos
      key_events:
        type: list
        description: Schlüsselereignisse in der Fraktionsgeschichte
      current_status:
        type: str
        description: Aktueller Status oder Aktivitätsgrad
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

# Fraktionsvorlage

Verwende diese Vorlage, um ein detailliertes Fraktionsprofil für die Welt deiner Geschichte zu erstellen.

## Überblick

Beschreibe die Ziele, Struktur und Rolle der Fraktion in der Erzählung.
