# FIND-011: {{style_profile}} fehlt in 4 von 8 EN Writing-Prompts
Priorität: 🟡 Mittel
Status: Offen
Review: cr-01
CR-AUFG: CR-AUFG-01-06
Querverweise: cr-04 §4.2.3 (Voice-Checker vs Writing-Continue Divergenz)

## Befund

`{{style_profile}}` — die wichtigste Variable für "wie schreibt der Autor"
(profilierte Satzläge, Rhythmus, Diktion) — fehlt in 4 von 8 EN
Writing-Prompts: `scene_by_scene`, `interactive_session`, `story_suggest`,
`chat`. Diese Prompts generieren oder diskutieren Prosa, haben aber keinen
Zugriff auf den profilierten Schreibstil des Autors.

(`inline_suggest` ist bewusst minimal — dort vertretbar.)

Dies verursacht eine **Voice-Checker vs Writing-Continue Divergenz**:
Voice-Checker misst Voice-Consistency gegen Profile, aber Continue generiert
ohne Style-Profile → Checker meldet Inkonsistenz, die Continue "nicht wissen
konnte".

## Evidenz

- `{{style_profile}}` Nutzung in EN Writing-Prompts: extend_chapter ✓,
  rewrite_selection ✓, new_chapter ✓, co_author ✓ (4 von 8).
- Fehlt in: `scene_by_scene`, `interactive_session`, `story_suggest`, `chat`
  (4 von 8).
- `{{culture_guidelines}}`, `{{genre}}`, `{{story_structure}}`,
  `{{writing_language}}` sind konsistent (alle 8). `{{character_voice_profiles}}`
  in 7 von 8.
- `prompt_vars.py` L85-89 — `SHOULD_VARS_BY_CATEGORY["writing"]` enthält
  `character_voice_profiles` und `kb_suggested`, aber **nicht** `style_profile`.

## Auswirkung

4 Writing-Prompts generieren Prosa ohne Kenntnis des profilierbaren Autorenstils.
Bei abweichendem Output meldet der Voice-Checker fälschlich Inkonsistenz, weil
Continue den Stil nicht kannte. Der Nutzer erhält inkonsistente Stil-Qualität
zwischen verschiedenen Writing-Modi.

## Empfehlung

Füge `### Style Profile\n\nThe author's established writing style:\n\n{{style_profile}}\n`
zu den 4 Templates hinzu. Bump versions.

Zusätzlich (P3, CR-AUFG-01-10): Füge `"style_profile"` zu
`SHOULD_VARS_BY_CATEGORY["writing"]` hinzu, damit künftiges Fehlen als WARN
gemeldet wird.

**Owner:** Core.

## Verifikation

- [ ] `scene_by_scene`, `interactive_session`, `story_suggest`, `chat` haben `{{style_profile}}`
- [ ] Versions gebumpt
- [ ] Voice-Checker vs Continue Divergenz reduziert
- [ ] `style_profile` in SHOULD_VARS für writing (P3-Begleitaufgabe)
