# FIND-007: Worldbuilding Phase 1 Prompt-Defizite (JSON-Schema + writing_language)
Priorität: 🟡 Mittel
Status: Offen
Review: cr-01
CR-AUFG: CR-AUFG-01-01, CR-AUFG-01-02
Querverweise: cr-04 §5.4 (i18n-Lücke), cr-00 §6 (bekanntes Problem)

## Befund

Der Worldbuilding-Phase-1-Prompt hat zwei inhaltliche Defizite:

1. **Kein formales JSON-Output-Schema:** Verwendet deskriptive Prosa
   ("Provide your analysis as structured data with: 1. gaps: list…") statt
   eines formalen JSON-Codeblocks mit Beispielobjekt. Das Modell könnte
   Freitext, Bullets oder gemischte Formate liefern. Verletzung von
   `prompt-standards.md` §1 Section 4 ("JSON schemas MUST include an example
   object").

2. **Kein `{{writing_language}}` und keine Constraints-Sektion:** Das Modell
   weiß nicht, in welcher Sprache es Antworten verfassen soll. Dies ist ein
   echtes Inhaltsdefizit für ein Feature, das strukturierte Analysen in der
   Projektsprache liefern soll.

Der Prompt wurde in `prompt-content-standards.md` L224 als ⭐⭐⭐ "Weak" bewertet
— diese Bewertung ist für phase2 teilweise veraltet (siehe FIND-008), aber für
phase1 weiterhin zutreffend.

## Evidenz

- `packages/core/narrare_core/prompts/_bundled/kb/en/worldbuilding/phase1/system.md`
  L51-58 — deskriptive Prosa statt JSON-Codeblock.
- Kein `{{writing_language}}` im gesamten Template, keine Constraints-Sektion.
- `prompt_vars.py` — KB-REQUIRED enthält nur `user_preferences`,
  `avoidance_patterns`. `writing_language` ist nicht gelistet für KB.
- Kein Checker für JSON-Beispielobjekt-Vorhandensein existiert
  (`check_required_sections` prüft nur Heading-Existenz).

## Auswirkung

- Ohne JSON-Schema: variable Output-Formate, Parsing-Probleme, inkonsistente
  Analyse-Ergebnisse.
- Ohne `writing_language`: Output in falscher Sprache (defaultet auf EN bei
  fehlender Sprachanweisung), insbesondere bei DE/FR-Projekten.

## Empfehlung

1. Ersetze die deskriptive Output-Format-Sektion durch einen JSON-Codeblock mit
   vollständigem Beispielobjekt (inkl. `suggested_action` pro Gap und
   `story_relevance`-Range). Bump version auf 1.2.0.
2. Füge eine Constraints-Sektion hinzu mit
   `Write all descriptions, reasoning, and assessment in {{writing_language}}.`

**Owner:** Core.

## Verifikation

- [ ] phase1/system.md hat JSON-Codeblock mit Beispielobjekt
- [ ] phase1/system.md hat Constraints-Sektion mit `{{writing_language}}`
- [ ] Version gebumpt (1.1.0 → 1.2.0)
- [ ] `check_prompt_structure.py` weiterhin grün
