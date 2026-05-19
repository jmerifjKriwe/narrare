---
template_type: character
template_version: "2.0.0"
template_language: fr
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    fields:
      age:
        type: int
        description: Âge du personnage
      role:
        type: str
        description: Rôle dans l'histoire (ex: protagoniste, antagoniste)
      gender:
        type: str
        description: Genre du personnage
      pronouns:
        type: str
        description: Pronoms préférés
      nationality:
        type: str
        description: Nationalité ou origine culturelle
      pov_character:
        type: bool
        description: Est-ce un personnage narrateur ?
      affiliation:
        type: str
        description: Affiliation à un groupe ou une organisation
      element:
        type: str
        description: Élément ou thème associé
      aliases:
        type: list
        description: Alias ou surnoms connus
  development:
    label_key: kb.groups.development
    description_key: kb.groups.developmentHint
    fields:
      arc:
        type: str
        description: Arc narratif ou évolution du personnage
      first_appearance:
        type: str
        description: Première apparition dans l'histoire
sections:
  background:
    label_key: kb.sections.background
    description_key: kb.sections.backgroundHint
    order: 1
  personality:
    label_key: kb.sections.personality
    description_key: kb.sections.personalityHint
    order: 2
---

# Modèle de Personnage

Utilisez ce modèle pour créer un profil détaillé de personnage pour votre histoire.

## Aperçu

Décrivez le personnage, sa personnalité, ses motivations et son rôle dans le récit.

## Contexte

Décrivez l'histoire du personnage, son éducation et les expériences formatrices.
