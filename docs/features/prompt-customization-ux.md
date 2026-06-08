---
id: PROMPT-003
title: "Prompt Customization UX"
status: planned
area: prompts
mvp: false

ui_tooltip: "Passe KI-Prompts an deinen Schreibstil an — mit Variablen-Erklärung und Vorschau."
ui_help_short: |
  In den AI-Einstellungen kannst du Prompts für jede KI-Funktion anpassen.
  Dieses Feature macht diese Anpassung verständlich: Variablen wie
  `{{kb_context}}` werden erklärt, Änderungen können in einer Vorschau
  getestet werden, und mit einem Klick setzt du alles auf die
  Standardwerte zurück.
ui_help_long: |
  ## Prompt Customization UX

  Narrare verwendet für jede KI-Funktion einen Basis-Prompt, der den
  Kontext deines Projekts (Figuren, Orte, Kapiteltext) einbindet.
  Erfahrene Nutzer können diese Prompts anpassen, um das Verhalten
  der KI gezielt zu steuern.

  **Prompt-Variablen verstehen:** Platzhalter wie `{{kb_context}}`,
  `{{chapter_text}}`, `{{character_name}}` werden in der UI mit
  Beschreibung und Beispielwert angezeigt. Du siehst, welche Daten
  an der Stelle eingefügt werden.

  **Änderungen testen:** Bevor du einen Prompt speicherst, kannst du
  ihn mit aktuellen Projektdaten in einer Vorschau ausprobieren. Die
  Vorschau zeigt, wie der fertige Prompt (mit eingefügten Variablen)
  aussehen würde.

  **Zurücksetzen:** Jeder Prompt hat einen „Auf Standard zurücksetzen"-
  Button. Damit kehrst du jederzeit zum Ausgangsprompt zurück — ohne
  Sorge, etwas kaputt zu machen.

  **Post-MVP:** Dieses Feature ist für Phase 6+ geplant und baut auf
  der bestehenden Prompt-Override-Infrastruktur (PROMPT-001, PROMPT-002) auf.
ui_available_in: [settings]
---

# PROMPT-003 — Prompt Customization UX

## What it does

Macht die bestehende Prompt-Anpassung (PROMPT-001/PROMPT-002) für
Endnutzer verständlich und sicher. Zeigt Prompt-Variablen mit
Erklärungen und Beispielwerten, bietet einen Preview/Test-Modus
vor dem Speichern und ermöglicht Reset-to-Default pro Intent.

## Why it exists

**CR-07 §6 Bewertung: ⭐⭐☆☆☆** — Das UX-Audit hat identifiziert:

1. **Keine Variablen-Erklärung:** Platzhalter wie `{{kb_context}}`,
   `{{chapter_text}}` werden in der Settings-UI nicht erklärt. Nutzer
   wissen nicht, welche Daten dort eingefügt werden.

2. **Kein Preview/Test-Modus:** Änderungen am Prompt werden blind
   gespeichert. Es gibt keine Möglichkeit zu sehen, wie der finale
   Prompt (mit aufgelösten Variablen) vor der ersten KI-Anfrage aussieht.

3. **Kein Reset-to-Default:** Einmal geänderte Custom Instructions
   können nicht auf die Standardwerte zurückgesetzt werden — außer
   durch manuelles Löschen.

4. **Entdeckung im Audit:** Die Settings AI-Komponenten
   (`IntentOverrides.tsx`) wurden vom Audit-Prompt als existent,
   aber nicht vollständig auditiert markiert. Dieses Feature spec
   schließt diese Lücke.

Bestehende Infrastruktur: PROMPT-001 (File-based Prompt Overrides) und
PROMPT-002 (User DB Prompt Templates) stellen bereits die technische
Grundlage — dieses Feature macht sie nutzerfreundlich.

## How it works (User perspective)

### In den AI-Einstellungen (Settings › KI)

1. **Intent-Liste:** Der Nutzer sieht eine Liste aller KI-Intents
   (Schreiben, Umschreiben, Analyse, usw.) mit dem aktuell verwendeten
   System-Prompt.

2. **Prompt-Detail-Ansicht:** Beim Klick auf einen Intent öffnet sich
   eine Detailansicht mit:
   - **Prompt-Editor:** Textarea mit dem aktuellen Prompt (monospace,
     zeilennummeriert)
   - **Variablen-Panel:** Eine Seitenleiste/Tabelle, die alle im Prompt
     verwendeten `{{variablen}}` auflistet mit:
     - Name der Variable (z. B. `kb_context`)
     - Beschreibung („Das aktuell relevante Wissen aus deiner Welt")
     - Beispielwert (z. B. „Anna Müller — eine Lehrerin, die …")
     - Datenquelle („Knowledge Base, Kapitel {chapter.title}")
   - **Vorschau-Button:** „Getesteten Prompt anzeigen" → öffnet ein
     Panel mit dem vollständig aufgelösten Prompt (Variable → echte
     Projektdaten)
   - **Reset-Button:** „Auf Standard zurücksetzen" → setzt den Prompt
     auf den ursprünglichen, systemdefinierten Wert zurück (mit
     Bestätigungsdialog)

3. **Test-Lauf (Preview-Modus):**
   - Klick auf „Testen" → eine echte KI-Anfrage wird mit dem
     bearbeiteten Prompt gestartet
   - Das Ergebnis erscheint in einer Vorschau (nicht im Dokument)
   - Der Nutzer kann das Ergebnis bewerten ohne es zu speichern
   - Nach dem Test kann der Prompt gespeichert oder verworfen werden

### Privacy-Hinweis

Der Preview-Modus sendet eine echte KI-Anfrage — das verbraucht Tokens.
Ein Hinweis weist den Nutzer darauf hin, bevor der Test gestartet wird.

## How it works (Technical)

**Entry point:** Settings AI tab → `IntentOverrides.tsx` (erweitert)
**Backend:** Bestehende Routen + neuer `POST /api/v1/settings/prompts/{intent}/preview`
**Service:** `PromptPreviewService` in `apps/api/narrare/prompts/`
**Contract:** `PromptCustomizationProtocol` in `prompts/contracts_prompt_ux.py`
**Prompt:** Verwendet bestehende Prompts aus `core/prompts/_bundled/`

### Neue API-Endpunkte

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/v1/settings/prompts/{intent}/preview` | POST | Liefert den vollständig aufgelösten Prompt (Variable → Projektdaten) ohne KI-Aufruf |
| `/api/v1/settings/prompts/{intent}/test` | POST | Führt eine KI-Anfrage mit dem bearbeiteten Prompt aus (Preview-Modus, Ergebnis wird nicht persistiert) |
| `/api/v1/settings/prompts/{intent}/reset` | POST | Setzt den Prompt-Override auf den systemdefinierten Standard zurück |

### Frontend-Änderungen

| Komponente | Neu/Erweitert | Beschreibung |
|------------|---------------|-------------|
| `IntentOverrides.tsx` | Erweitert | Detail-Ansicht mit Variable-Info + Reset + Preview |
| `PromptPreviewDialog.tsx` | Neu | Modal/Sheet mit vollständig aufgelöstem Prompt |
| `PromptTestDialog.tsx` | Neu | Modal mit KI-Testlauf (Streaming-Preview) |
| `VariableExplanationTable.tsx` | Neu | Tabelle mit Variablen-Name, Beschreibung, Beispielwert |

### Prompt-Variable Metadata

Die Variablen-Metadaten (Name, Beschreibung, Datenquelle) müssen in den
Prompt-Dateien oder einem separaten Manifest gepflegt werden:

```yaml
# core/prompts/_bundled/writing/en/extend/variables.yaml
- name: "kb_context"
  description: "Relevant knowledge base context for the current chapter"
  source: "KBService.get_relevant_context()"
  example: "Anna Müller — a teacher from the city..."
```

### i18n

Neue Schlüssel in `studio.json` unter `settings.ai.promptCustomization.*`:

| Key | DE | EN | FR |
|-----|----|----|----|
| `promptCustomization.title` | Prompt-Anpassung | Prompt Customization | Personnalisation des prompts |
| `promptCustomization.variables` | Verfügbare Variablen | Available Variables | Variables disponibles |
| `promptCustomization.preview` | Getesteten Prompt anzeigen | Show Resolved Prompt | Afficher le prompt résolu |
| `promptCustomization.test` | Prompt testen | Test Prompt | Tester le prompt |
| `promptCustomization.reset` | Auf Standard zurücksetzen | Reset to Default | Réinitialiser |
| `promptCustomization.resetConfirm` | Wirklick zurücksetzen? | Reset to default? | Réinitialiser ? |
| `promptCustomization.resetDone` | Prompt zurückgesetzt | Prompt reset | Prompt réinitialisé |
| `promptCustomization.testWarning` | Dies verbraucht KI-Tokens. Fortfahren? | This uses AI tokens. Continue? | Cela utilise des tokens IA. Continuer ? |
| `promptCustomization.variableName` | Variable | Variable | Variable |
| `promptCustomization.variableDescription` | Beschreibung | Description | Description |
| `promptCustomization.variableExample` | Beispiel | Example | Exemple |
| `promptCustomization.variableSource` | Datenquelle | Data Source | Source de données |

## UX Requirements

### AI Interaction Type
- [ ] Generation — produces new content
- [ ] Suggestion — inline ghost text
- [ ] Analysis — structured feedback/report
- [ ] Extraction — structured data from text
- [ ] Transformation — rewrites existing content
- [ ] Conversation — multi-turn AI session
- [x] Configuration — Prompt-Test-Modus verwendet KI

### Streaming
| Question | Answer |
|----------|--------|
| Backend SSE endpoint exists? | Preview: nein (nur Prompt-Auflösung). Test: ja (KI-Anfrage) |
| Frontend uses SSE? | Test: ja — Streaming-Vorschau des KI-Ergebnisses |
| REST endpoint also needed? | Preview: ja (POST). Test: nein (SSE reicht) |

### User Controls
| Control | Required? | i18n key |
|---------|-----------|----------|
| Cancel/Abort | Test-Modus: ja | `studio.aiActions.stop` |
| Accept | nein (Preview wird nicht persistiert) | — |
| Reject | nein | — |
| Retry | Test-Modus: ja | `studio.aiActions.retry` |
| Rating | nein | — |

### Loading States
| Phase | Indicator | Within |
|-------|-----------|--------|
| Prompt-Vorschau (Preview) | Skeleton-Textarea | 500ms |
| KI-Testlauf | Streaming-Text (progressiv) | kontinuierlich |
| Reset | Button-Spinner | 300ms |

### Error Handling
| Scenario | User message (de) | User action |
|----------|-------------------|-------------|
| Preview-Fehler (Variable nicht auflösbar) | "Konnte Variable {name} nicht auflösen. Projektkontext könnte fehlen." | Fehler melden |
| KI-Test schlägt fehl | "Der Test-Prompt konnte nicht ausgeführt werden. Prüfe deine KI-Einstellungen." | Retry oder zurück |
| Reset fehlschlägt | "Konnte Prompt nicht zurücksetzen. Bitte versuche es erneut." | Retry |

### Onboarding
| Question | Answer |
|----------|--------|
| Discoverable from | Settings → KI → Intent-Liste |
| Tooltip needed? | Ja: „Passe an, wie die KI reagiert" |
| Tour step needed? | Optional — Teil der KI-Einführungs-Tour (ONBOARD-001) |

### Accessibility
| Requirement | Implemented? |
|-------------|-------------|
| aria-live for test output | 📋 Zu prüfen |
| aria-label on reset/preview buttons | 📋 Zu prüfen |
| Focus moves to test output | 📋 Zu prüfen |
| Escape cancels test | 📋 Zu prüfen |

## Constraints & Edge Cases

- **Preview-Modus verwendet ECHTE Projektdaten.** Der Nutzer muss
  eingeweiht sein, dass sensible Projektdaten im Preview sichtbar werden.
- **Test-Modus verbraucht Tokens.** Warnhinweis vor dem ersten Test.
- **Kein unbegrenztes Testen:** Optionales Rate-Limiting für den
  Test-Endpoint (max. 5 Tests pro Minute).
- **Reset ist immer möglich:** Der Original-Prompt ist im Code definiert
  (`core/prompts/_bundled/`) und kann nicht überschrieben werden. Reset
  löscht nur den User-Override.
- **Komplexe Prompts:** Prompts mit Conditional Logic (@if/endif) werden
  im Preview nur annotiert, nicht interpretiert — der Nutzer sieht die
  Rohstruktur.
- **Kein Editieren von system-owned Prompts:** Der Nutzer überschreibt
  nur Custom Instructions (PROMPT-001), nicht den systemdefinierten Kernprompt.

## Related Features

- [PROMPT-001](../prompts/PROMPT-001-file-overrides.md) — File-based Prompt Overrides (Basis)
- [PROMPT-002](../prompts/PROMPT-002-db-templates.md) — User DB Prompt Templates (Basis)
- [ONBOARD-001](../onboarding-user-guide.md) — Variablen-Erklärung kann Tour-Step sein
- [SET-004](../settings/SET-004-provider-config.md) — AI Provider Configuration (Settings-Kontext)
- [INFRA-002](../infra/INFRA-002-prompt-system.md) — Unified Prompt System (Prompt-Architektur)

## Status & History

- `2026-06-08` — Added to registry (CR-07 UX Audit §6 Remediation)

## Definition of Done

- [ ] Prompt-Variablen-Panel zeigt alle `{{variablen}}` mit Beschreibung + Beispielwert
- [ ] Preview-Modus (Prompt-Auflösung ohne KI) implementiert
- [ ] Test-Modus (KI-Anfrage + Streaming-Vorschau) implementiert
- [ ] Reset-to-Default pro Intent mit Bestätigungsdialog implementiert
- [ ] Warnhinweis vor KI-Test (Token-Verbrauch)
- [ ] i18n: Alle neuen UI-Texte in studio.json (de/en/fr)
- [ ] Prompt-Variable-Metadaten (Beschreibung, Datenquelle) in Manifest-Datei gepflegt
- [ ] Rate-Limiting für Test-Endpoint (max. 5/min)
- [ ] Tests: Preview- + Test-Endpoint (Integration), Frontend-Komponenten (Vitest)
- [ ] Bestehende PROMPT-001/PROMPT-002 funktionieren unverändert
- [ ] Dokumentation: Feature-Spec auf stable gesetzt

---

> **Post-MVP:** Dieses Feature ist nicht vor Phase 6 abgeschlossen.
> Die bestehende Prompt-Anpassung (PROMPT-001/PROMPT-002) bleibt
> weiterhin funktional — ohne die UX-Verbesserungen dieses Features.
