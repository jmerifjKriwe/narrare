---
template_type: timeline
template_version: "2.0.0"
template_language: fr
schema_version: "2.0.0"
field_groups:
  period:
    label_key: kb.groups.period
    description_key: kb.groups.periodHint
    order: 1
    fields:
      era:
        type: str
        description: Nom de l'époque ou de la période
      era_name:
        type: str
        description: Nom usuel de cette époque
      start_date:
        type: str
        description: Début de la période
      end_date:
        type: str
        description: Fin de la période
      duration:
        type: str
        description: Durée totale de la période
      first_appearance:
        type: str
        description: Première apparition dans l'histoire
  events:
    label_key: kb.groups.events
    description_key: kb.groups.eventsHint
    order: 2
    fields:
      major_events:
        type: list
        description: Événements majeurs de cette période
      key_figures:
        type: list
        description: Figures clés ou personnages importants
      conflicts:
        type: list
        description: Conflits ou guerres de cette période
      discoveries:
        type: list
        description: Découvertes ou inventions importantes
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

# Modèle de Chronologie

Utilisez ce modèle pour créer une entrée détaillée de chronologie pour l'histoire de votre récit.

## Aperçu

Décrivez les événements clés, les transitions et l'importance de cette période dans le monde de votre histoire.
