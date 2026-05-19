---
template_type: character
template_version: "2.1.0"
template_language: fr
schema_version: "2.0.0"
field_groups:
  basic_info:
    label_key: kb.groups.basicInfo
    description_key: kb.groups.basicInfoHint
    order: 1
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
      occupation:
        type: str
        description: Profession ou occupation
      aliases:
        type: list
        description: Alias ou surnoms connus
  appearance:
    label_key: kb.groups.appearance
    description_key: kb.groups.appearanceHint
    order: 2
    fields:
      height:
        type: str
        description: Taille physique
      build:
        type: str
        description: Morphologie ou corpulence
      hair_color:
        type: str
        description: Couleur et style de cheveux
      eye_color:
        type: str
        description: Couleur des yeux
      skin_tone:
        type: str
        description: Teint ou couleur de peau
      distinctive_marks:
        type: str
        description: Cicatrices, tatouages, grains de beauté ou autres signes distinctifs
      clothing_style:
        type: str
        description: Style vestimentaire habituel
  personality:
    label_key: kb.groups.personality
    description_key: kb.groups.personalityHint
    order: 3
    fields:
      traits:
        type: list
        description: Traits de personnalité principaux
      strengths:
        type: list
        description: Forces du personnage
      weaknesses:
        type: list
        description: Faiblesses ou défauts
      fears:
        type: list
        description: Ce que le personnage craint
      desires:
        type: list
        description: Objectifs, désirs ou aspirations
      motivations:
        type: str
        description: Ce qui motive ce personnage
      quirks:
        type: list
        description: Habitudes ou manies inhabituelles
  background:
    label_key: kb.groups.background
    description_key: kb.groups.backgroundHint
    order: 4
    fields:
      family:
        type: str
        description: Contexte familial
      upbringing:
        type: str
        description: Comment le personnage a été élevé
      education:
        type: str
        description: Éducation ou formation
      key_events:
        type: list
        description: Événements marquants du passé
      formative_experiences:
        type: str
        description: Expériences qui ont façonné le personnage
  relationships:
    label_key: kb.groups.relationships
    description_key: kb.groups.relationshipsHint
    order: 5
    fields:
      allies:
        type: list
        description: Alliés et amis connus
      rivals:
        type: list
        description: Rivaux et antagonistes
      family_members:
        type: list
        description: Membres importants de la famille
      mentors:
        type: list
        description: Mentors ou enseignants
  development:
    label_key: kb.groups.development
    description_key: kb.groups.developmentHint
    order: 6
    fields:
      arc:
        type: str
        description: Arc narratif ou évolution du personnage
      starting_point:
        type: str
        description: Point de départ émotionnel/psychologique
      key_turning_points:
        type: list
        description: Tournants majeurs dans l'arc du personnage
      current_state:
        type: str
        description: État émotionnel/psychologique actuel
      planned_arc:
        type: str
        description: Trajectoire de développement prévue
      first_appearance:
        type: str
        description: Première apparition dans l'histoire
  speech:
    label_key: kb.groups.speech
    description_key: kb.groups.speechHint
    order: 7
    fields:
      typical_phrases:
        type: list
        description: Expressions ou tournures caractéristiques
      dialect:
        type: str
        description: Dialecte, accent ou modes d'expression
      vocabulary_quirks:
        type: str
        description: Vocabulaire inhabituel ou habitudes de parole
      body_language:
        type: str
        description: Gestes ou langage corporel caractéristique
sections:
  background:
    label_key: kb.sections.background
    description_key: kb.sections.backgroundHint
    order: 1
  personality:
    label_key: kb.sections.personality
    description_key: kb.sections.personalityHint
    order: 2
  notes:
    label_key: kb.sections.notes
    description_key: kb.sections.notesHint
    order: 3
---

# Modèle de Personnage

Utilisez ce modèle pour créer un profil détaillé de personnage pour votre histoire.

## Aperçu

Décrivez le personnage, sa personnalité, ses motivations et son rôle dans le récit.

## Contexte

Décrivez l'histoire du personnage, son éducation et les expériences formatrices.
