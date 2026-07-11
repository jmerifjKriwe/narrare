# FIND-008: Worldbuilding Phase 2 — fehlendes formales JSON-Output-Schema
Priorität: 🟡 Mittel
Status: Offen
Review: cr-01
CR-AUFG: CR-AUFG-01-03
Querverweise: cr-01 stale finding (phase2-Bewertung in prompt-content-standards.md veraltet)

## Befund

Worldbuilding-Phase-2-Prompt verwendet deskriptive Prosa statt eines formalen
JSON-Codeblocks mit Beispielobjekt. Die Felder sind beschrieben (category,
entity_ids, description, contradiction, etc.), aber es gibt kein Beispielobjekt.

> **Stale-Hinweis:** `prompt-content-standards.md` L224 bewertet phase2 als
> ⭐⭐⭐ "Weak: Missing formal output schema, Do-NOT section, CoT, confidence
> thresholds". Diese Bewertung ist **teilweise veraltet**: Do-NOT-Sektion
> (6 Items), CoT (`<scratchpad>`) und Confidence-Thresholds wurden seitdem
> hinzugefügt. Einzig das "formal output schema" (JSON-Beispiel) fehlt noch.
> Die Bewertung sollte nach Remediation auf ⭐⭐⭐⭐ aktualisiert werden
> (siehe P3-Aufgabe CR-AUFG-01-11).

## Evidenz

- `packages/core/narrare_core/prompts/_bundled/kb/en/worldbuilding/phase2/system.md`
  L74-88 — deskriptive Prosa ("Provide your analysis as structured data with:
  1. issues: list…") statt JSON-Codeblock.
- Do-NOT-Sektion (6 Items), `<scratchpad>`-CoT und Severity/Confidence-
  Thresholds sind bereits vorhanden (verbessert seit der ursprünglichen
  Bewertung).
- Kein Checker für JSON-Beispielobjekt-Vorhandensein existiert.

## Auswirkung

Variable Output-Formate, Parsing-Probleme. Das Modell hat keine klare
Struktur-Vorgabe und könnte Inkonsistenz in der Output-Form produzieren.

## Empfehlung

Ersetze die deskriptive Output-Format-Sektion durch einen JSON-Codeblock mit
Beispielobjekt (issues[] mit category, entity_ids, entity_names, description,
contradiction, suggested_resolution, severity, confidence + assessment).
Bump version auf 1.3.0.

**Owner:** Core.

## Verifikation

- [ ] phase2/system.md hat JSON-Codeblock mit Beispielobjekt
- [ ] Version gebumpt (1.2.0 → 1.3.0)
- [ ] `prompt-content-standards.md` phase2-Bewertung aktualisiert (nach Remediation)
