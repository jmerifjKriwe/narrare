---
template_type: object
template_version: "2.0.0"
template_language: fr
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      object_type:
        type: str
        description: "Type d'objet (ex: arme, artefact, outil)"
      owner:
        type: str
        description: Propriétaire actuel
      origin:
        type: str
        description: Origine ou histoire de création
      first_appearance:
        type: str
        description: Première apparition dans l'histoire
  properties:
    label_key: kb.groups.properties
    description_key: kb.groups.propertiesHint
    order: 2
    fields:
      material:
        type: str
        description: Matériau ou composition
      dimensions:
        type: str
        description: Dimensions physiques ou taille
      weight:
        type: str
        description: Poids ou lourdeur
      condition:
        type: str
        description: État actuel ou état de conservation
      appearance:
        type: str
        description: Apparence visuelle et traits distinctifs
  origin_details:
    label_key: kb.groups.origin_details
    description_key: kb.groups.origin_detailsHint
    order: 3
    fields:
      creator:
        type: str
        description: Créateur de l'objet
      created_date:
        type: str
        description: Date de création de l'objet
      place_of_origin:
        type: str
        description: Lieu de création de l'objet
      method_of_creation:
        type: str
        description: Méthode de fabrication de l'objet
  significance:
    label_key: kb.groups.significance
    description_key: kb.groups.significanceHint
    order: 4
    fields:
      purpose:
        type: str
        description: Fonction ou but principal
      powers:
        type: list
        description: Pouvoirs ou capacités spéciaux
      historical_significance:
        type: str
        description: Importance historique ou culturelle
      current_location:
        type: str
        description: Où se trouve actuellement l'objet
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

# Modèle d'Objet

Utilisez ce modèle pour créer un profil détaillé d'objet pour les éléments importants de votre histoire.

## Aperçu

Décrivez l'apparence, les propriétés et l'importance de l'objet.
