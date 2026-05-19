---
template_type: location
template_version: "2.0.0"
template_language: fr
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      location_type:
        type: str
        description: "Type de lieu (ex: ville, forêt, bâtiment)"
      parent_location:
        type: str
        description: Lieu parent ou contenant
      coordinates:
        type: str
        description: Coordonnées géographiques ou position
      climate:
        type: str
        description: Climat ou conditions météorologiques
      terrain:
        type: str
        description: Terrain ou caractéristiques du paysage
      size:
        type: str
        description: Taille ou échelle du lieu
  features:
    label_key: kb.groups.features
    description_key: kb.groups.featuresHint
    order: 2
    fields:
      architecture:
        type: str
        description: Style architectural ou types de bâtiments
      natural_features:
        type: list
        description: Caractéristiques naturelles remarquables
      landmarks:
        type: list
        description: Points de repère ou lieux d'intérêt importants
      atmosphere:
        type: str
        description: Atmosphère générale ou ambiance du lieu
  inhabitants:
    label_key: kb.groups.inhabitants
    description_key: kb.groups.inhabitantsHint
    order: 3
    fields:
      population:
        type: str
        description: Taille ou densité de la population
      species:
        type: list
        description: Espèces ou races habitant le lieu
      factions:
        type: list
        description: Factions ou groupes présents dans le lieu
      notable_residents:
        type: list
        description: Résidents ou habitants notables
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      founded:
        type: str
        description: Date de fondation ou d'établissement du lieu
      key_events:
        type: list
        description: Événements historiques clés en ce lieu
      current_state:
        type: str
        description: État ou statut actuel du lieu
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

# Modèle de Lieu

Utilisez ce modèle pour créer un profil détaillé de lieu pour le monde de votre histoire.

## Aperçu

Décrivez le lieu, son atmosphère, ses caractéristiques uniques et son importance narrative.
