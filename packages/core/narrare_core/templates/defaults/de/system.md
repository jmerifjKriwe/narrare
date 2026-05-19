---
template_type: system
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      system_type:
        type: str
        description: Art des Systems (z.B. Magie, Technologie, Politik)
      practitioners:
        type: list
        description: Bekannte Anwender oder Nutzer
      first_appearance:
        type: str
        description: Erster Auftritt in der Geschichte
  mechanics:
    label_key: kb.groups.mechanics
    description_key: kb.groups.mechanicsHint
    order: 2
    fields:
      rules:
        type: list
        description: Kernregeln oder Gesetze des Systems
      cost:
        type: str
        description: Kosten oder Preis der Nutzung
      limitations:
        type: list
        description: Bekannte Einschränkungen oder Beschränkungen
      levels:
        type: list
        description: Kompetenzstufen oder Grade
  practitioner_details:
    label_key: kb.groups.practitioner_details
    description_key: kb.groups.practitioner_detailsHint
    order: 3
    fields:
      users:
        type: list
        description: Bemerkenswerte Anwender oder Nutzer
      requirements:
        type: str
        description: Voraussetzungen zur Nutzung des Systems
      training:
        type: str
        description: Ausbildungs- oder Einweihungsprozess
      organizations:
        type: list
        description: Zugehörige Organisationen oder Schulen
  origins:
    label_key: kb.groups.origins
    description_key: kb.groups.originsHint
    order: 4
    fields:
      source:
        type: str
        description: Ursprung oder Quelle des Systems
      discovered_by:
        type: str
        description: Wer das System entdeckt oder erschaffen hat
      discovered_date:
        type: str
        description: Wann das System entdeckt wurde
      history:
        type: str
        description: Geschichte und Entwicklung des Systems
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

# Systemvorlage

Verwende diese Vorlage, um ein detailliertes Systemprofil für das Worldbuilding deiner Geschichte zu erstellen.

## Überblick

Beschreibe die Regeln, Einschränkungen und Auswirkungen des Systems auf die Welt.
