---
template_type: system
template_version: "2.0.0"
template_language: fr
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      system_type:
        type: str
        description: "Type de système (ex: magie, technologie, politique)"
      practitioners:
        type: list
        description: Praticiens ou utilisateurs connus
      first_appearance:
        type: str
        description: Première apparition dans l'histoire
  mechanics:
    label_key: kb.groups.mechanics
    description_key: kb.groups.mechanicsHint
    order: 2
    fields:
      rules:
        type: list
        description: Règles ou lois fondamentales du système
      cost:
        type: str
        description: Coût ou prix de l'utilisation du système
      limitations:
        type: list
        description: Limites ou restrictions connues
      levels:
        type: list
        description: Niveaux de compétence ou degrés
  practitioner_details:
    label_key: kb.groups.practitioner_details
    description_key: kb.groups.practitioner_detailsHint
    order: 3
    fields:
      users:
        type: list
        description: Utilisateurs ou praticiens notables
      requirements:
        type: str
        description: Conditions requises pour utiliser le système
      training:
        type: str
        description: Formation ou processus d'initiation
      organizations:
        type: list
        description: Organisations ou écoles associées
  origins:
    label_key: kb.groups.origins
    description_key: kb.groups.originsHint
    order: 4
    fields:
      source:
        type: str
        description: Origine ou source du système
      discovered_by:
        type: str
        description: Qui a découvert ou créé le système
      discovered_date:
        type: str
        description: Quand le système a été découvert
      history:
        type: str
        description: Histoire et évolution du système
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

# Modèle de Système

Utilisez ce modèle pour créer un profil détaillé de système pour le worldbuilding de votre histoire.

## Aperçu

Décrivez les règles, les limites et l'impact du système sur le monde.
