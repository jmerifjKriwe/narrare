---
template_type: object
template_version: "2.0.0"
template_language: de
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      object_type:
        type: str
        description: Art des Objekts (z.B. Waffe, Artefakt, Werkzeug)
      owner:
        type: str
        description: Aktueller Besitzer
      origin:
        type: str
        description: Ursprung oder Entstehungsgeschichte
      first_appearance:
        type: str
        description: Erster Auftritt in der Geschichte
  properties:
    label_key: kb.groups.properties
    description_key: kb.groups.propertiesHint
    order: 2
    fields:
      material:
        type: str
        description: Material oder Zusammensetzung
      dimensions:
        type: str
        description: Physische Abmessungen oder Größe
      weight:
        type: str
        description: Gewicht oder Schwere
      condition:
        type: str
        description: Aktueller Zustand oder Erhaltungszustand
      appearance:
        type: str
        description: Visuelles Erscheinungsbild und Unterscheidungsmerkmale
  origin_details:
    label_key: kb.groups.origin_details
    description_key: kb.groups.origin_detailsHint
    order: 3
    fields:
      creator:
        type: str
        description: Wer das Objekt erschaffen hat
      created_date:
        type: str
        description: Wann das Objekt erschaffen wurde
      place_of_origin:
        type: str
        description: Wo das Objekt erschaffen wurde
      method_of_creation:
        type: str
        description: Wie das Objekt hergestellt wurde
  significance:
    label_key: kb.groups.significance
    description_key: kb.groups.significanceHint
    order: 4
    fields:
      purpose:
        type: str
        description: Hauptzweck oder Funktion
      powers:
        type: list
        description: Besondere Kräfte oder Fähigkeiten
      historical_significance:
        type: str
        description: Historische oder kulturelle Bedeutung
      current_location:
        type: str
        description: Wo sich das Objkt derzeit befindet
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

# Objektvorlage

Verwende diese Vorlage, um ein detailliertes Objektprofil für wichtige Gegenstände in deiner Geschichte zu erstellen.

## Überblick

Beschreibe das Aussehen, die Eigenschaften und die Bedeutung des Objekts.
