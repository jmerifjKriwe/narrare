---
template_type: faction
template_version: "2.0.0"
template_language: fr
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
    fields:
      founded:
        type: str
        description: Date de fondation de la faction
      members:
        type: list
        description: Membres notables de la faction
      ideology:
        type: str
        description: Idéologie ou croyances fondamentales
      first_appearance:
        type: str
        description: Première apparition dans l'histoire
  structure:
    label_key: kb.groups.structure
    description_key: kb.groups.structureHint
    order: 2
    fields:
      leadership:
        type: str
        description: Structure de leadership ou dirigeants clés
      hierarchy:
        type: str
        description: Hiérarchie interne ou système de rangs
      membership_count:
        type: str
        description: Nombre approximatif de membres
      headquarters:
        type: str
        description: Quartier général ou base principale
  belief_system:
    label_key: kb.groups.belief_system
    description_key: kb.groups.belief_systemHint
    order: 3
    fields:
      beliefs:
        type: list
        description: Croyances fondamentales ou principes
      goals:
        type: list
        description: Objectifs ou buts principaux
      methods:
        type: str
        description: Méthodes ou tactiques utilisées
      taboos:
        type: list
        description: Actions interdites ou tabous
  history:
    label_key: kb.groups.history
    description_key: kb.groups.historyHint
    order: 4
    fields:
      origin_story:
        type: str
        description: Histoire d'origine ou mythe fondateur
      key_events:
        type: list
        description: Événements clés de l'histoire de la faction
      current_status:
        type: str
        description: Statut actuel ou niveau d'activité
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

# Modèle de Faction

Utilisez ce modèle pour créer un profil détaillé de faction pour le monde de votre histoire.

## Aperçu

Décrivez les objectifs, la structure et le rôle de la faction dans le récit.
