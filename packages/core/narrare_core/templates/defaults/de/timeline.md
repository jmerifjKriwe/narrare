---
template_type: timeline
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  period:
    label_key: kb.groups.period
    description_key: kb.groups.periodHint
    order: 1
    fields:
      era:
        type: str
        description: Name der Epoche oder Periode
      era_name:
        type: str
        description: Gebräuchlicher Name dieser Epoche
      start_date:
        type: str
        description: Beginn des Zeitraums
      end_date:
        type: str
        description: Ende des Zeitraums
      duration:
        type: str
        description: Gesamtdauer der Periode
      first_appearance:
        type: str
        description: Erster Auftritt in der Geschichte
  events:
    label_key: kb.groups.events
    description_key: kb.groups.eventsHint
    order: 2
    fields:
      major_events:
        type: list
        description: Wichtige Ereignisse in diesem Zeitraum
      key_figures:
        type: list
        description: Schlüsselfiguren oder Personen
      conflicts:
        type: list
        description: Konflikte oder Kriege in diesem Zeitraum
      discoveries:
        type: list
        description: Wichtige Entdeckungen oder Erfindungen
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

# Zeitleisten-Vorlage

Verwende diese Vorlage, um einen detaillierten Zeitleisten-Eintrag für die Chronologie deiner Geschichte zu erstellen.

## Überblick

Beschreibe die wichtigsten Ereignisse, Übergänge und die Bedeutung dieses Zeitraums für die Welt deiner Geschichte.
