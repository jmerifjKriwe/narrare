---
template_type: location
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      location_type:
        type: str
        description: Art des Ortes (z.B. Stadt, Wald, Gebäude)
      parent_location:
        type: str
        description: Übergeordneter oder umschließender Ort
      coordinates:
        type: str
        description: Geografische Koordinaten oder Position
      climate:
        type: str
        description: Klima oder Wetterverhältnisse
      terrain:
        type: str
        description: Gelände oder Landschaftsmerkmale
      size:
        type: str
        description: Größe oder Maßstab des Ortes
  features:
    label_key: kb.groups.features
    description_key: kb.groups.featuresHint
    order: 2
    fields:
      architecture:
        type: str
        description: Architekturstil oder Gebäudearten
      natural_features:
        type: list
        description: Bemerkenswerte natürliche Merkmale
      landmarks:
        type: list
        description: Wichtige Wahrzeichen oder Sehenswürdigkeiten
      atmosphere:
        type: str
        description: Gesamtatmosphäre oder Stimmung des Ortes
  inhabitants:
    label_key: kb.groups.inhabitants
    description_key: kb.groups.inhabitantsHint
    order: 3
    fields:
      population:
        type: str
        description: Bevölkerungsgröße oder -dichte
      species:
        type: list
        description: Spezies oder Rassen, die den Ort bewohnen
      factions:
        type: list
        description: Fraktionen oder Gruppen am Ort
      notable_residents:
        type: list
        description: Bemerkenswerte Einwohner oder Bewohner
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      founded:
        type: str
        description: Wann der Ort gegründet oder errichtet wurde
      key_events:
        type: list
        description: Wichtige historische Ereignisse an diesem Ort
      current_state:
        type: str
        description: Aktueller Zustand oder Status des Ortes
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

# Ortsvorlage

Verwende diese Vorlage, um ein detailliertes Ortsprofil für die Welt deiner Geschichte zu erstellen.

## Überblick

Beschreibe den Ort mit seiner Atmosphäre, besonderen Merkmalen und Bedeutung für die Erzählung.
