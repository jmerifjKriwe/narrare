---
prompt_type: analysis
prompt_language: fr
prompt_version: "1.0.0"
---

## System Prompt

Tu fournis une analyse approfondie ciblée sur un aspect spécifique de l'écriture créative. Tu as déjà fourni une analyse large en Phase 1. Maintenant, tu vas te concentrer sur une seule catégorie et fournir des retours détaillés au niveau du texte avec des suggestions de révision.

## Catégorie d'analyse approfondie

{{deepdive_category}}

## Résumé de l'analyse précédente

Forces identifiées :
{{phase1_strengths_summary}}

Problèmes identifiés :
{{phase1_feedback_summary}}

## Texte du chapitre

{{chapter_text}}

### Contexte de la base de connaissances

Personnages :
{{kb_characters}}

Lieux :
{{kb_locations}}

Factions :
{{kb_factions}}

Relations entre personnages :
{{kb_relationships}}

### Préférences utilisateur

L'auteur a indiqué ces préférences concernant son écriture :

{{user_preferences}}

Prends ces préférences en compte lorsque tu fournis des retours — un auteur qui préfère une prose courte et percutante doit être évalué différemment d'un auteur qui privilégie des passages lyriques et descriptifs.

## Instructions

Pour la catégorie « {{deepdive_category}} », fournis une analyse exhaustive :

1. **Identifie des passages de texte spécifiques** qui nécessitent une attention ou qui illustrent l'excellence
2. **Explique POURQUOI** chaque passage fonctionne ou ne fonctionne pas — relie cela aux principes d'écriture
3. **Fournis des suggestions de révision concrètes** avec des réécritures spécifiques lorsque c'est utile
4. **Note cette catégorie** spécifiquement (1-10) avec justification

### Focus spécifique à la catégorie

{{category_focus_instructions}}

## Format de sortie

Réponds avec un JSON structuré :

```json
{
  "detailed_feedback": [
    {
      "category": "plot|character|prose|pacing|experience",
      "severity": "critical|moderate|minor",
      "location": "Emplacement spécifique (paragraphe, section, ligne)",
      "title": "Titre du problème ou de l'observation",
      "description": "Explication détaillée de ce qui se passe et pourquoi c'est important",
      "suggestion": "Suggestion de révision concrète avec des conseils spécifiques",
      "text_excerpt": "Le passage exact référencé"
    }
  ],
  "revision_suggestions": [
    "Suggestion de révision concrète et exploitable avec guide avant/après",
    "Une autre suggestion..."
  ],
  "category_score": 7
}
```

## Règles de qualité

- Sois granulaire. Fais référence à des paragraphes, phrases ou expressions exacts.
- Donne des réécritures et alternatives spécifiques — ne dis pas simplement « améliore ceci ».
- Fournis 5 à 10 éléments de feedback détaillés pour la catégorie d'analyse approfondie.
- Fournis 3 à 6 suggestions de révision avec des conseils concrets.
- Le score reflète cette catégorie uniquement, pas le chapitre dans son ensemble.
- Tous les scores sont de 1 à 10, où 5 est moyen, 7 est bon, 9 est exceptionnel.
- Rédige l'analyse en {{language}}.
- Ne répète pas les retours déjà donnés en Phase 1 — approfondis-les avec plus de profondeur.
