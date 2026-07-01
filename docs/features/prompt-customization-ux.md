---
id: PROMPT-003
title: "Prompt Customization UX"
status: stable
area: prompts
mvp: false

ui_tooltip: "Passe KI-Prompts an deinen Schreibstil an — mit Variablen-Erklärung, sicherer Vorschau und optionalem Live-Test."
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

  **Änderungen prüfen:** Bevor du einen Prompt speicherst, kannst du
  eine sichere Vorschau ohne KI-Anfrage öffnen. Sie zeigt den fertigen
  Prompt mit eingefügten Variablen, Provenance und Validierungsdiagnostik.

  **Optionaler Live-Test:** Wenn deine KI-Einstellungen vollständig sind,
  kannst du zusätzlich einen echten Testlauf starten. Dieser verbraucht
  Tokens und sendet die angezeigten Projektdaten an den konfigurierten
  Provider.

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
Erklärungen, Provenance, Security-Klassen und Beispielwerten, bietet
eine providerfreie Preview vor dem Speichern, optional einen gated Live-
Test und ermöglicht Reset-to-Default pro Intent.

## Why it exists

**CR-07 §6 Bewertung: ⭐⭐☆☆☆** — Das UX-Audit hat identifiziert:

1. **Keine Variablen-Erklärung:** Platzhalter wie `{{kb_context}}`,
   `{{chapter_text}}` werden in der Settings-UI nicht erklärt. Nutzer
   wissen nicht, welche Daten dort eingefügt werden.

2. **Kein sicher getrennter Preview/Test-Modus:** Änderungen am Prompt werden
   blind gespeichert. Es gibt keine providerfreie Möglichkeit zu sehen, wie der
   finale Prompt (mit aufgelösten Variablen) aussieht; ein optionaler Live-Test
   muss davon klar getrennt, provider-/secret-gated und als tokenverbrauchend
   markiert sein.

3. **Kein Reset-to-Default:** Einmal geänderte Custom Instructions
   können nicht auf die Standardwerte zurückgesetzt werden — außer
   durch manuelles Löschen.

4. **Entdeckung im Audit:** Die Settings AI-Komponenten
   (`packages/web/components/studio/settings/IntentOverrides.tsx`) wurden vom Audit-Prompt als existent,
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
    - **Vorschau-Button:** „Prompt-Vorschau anzeigen" → öffnet ein
      Panel mit dem vollständig aufgelösten Prompt (Variable → echte
      Projektdaten), Provenance und Validierungsdiagnostik; kein LLM-Aufruf
      und keine Provider-Secrets erforderlich
    - **Optionaler Live-Test:** „Prompt live testen" → nur aktiv, wenn Provider-
      Konfiguration vorhanden ist und der Nutzer Token-/Privacy-Hinweis bestätigt
   - **Reset-Button:** „Auf Standard zurücksetzen" → setzt den Prompt
     auf den ursprünglichen, systemdefinierten Wert zurück (mit
     Bestätigungsdialog)

3. **Providerfreie Preview:**
   - Klick auf „Vorschau" → Core/API löst Variablen mit aktuellem Projektkontext
     auf und liefert Diagnostik (fehlende Variablen, Security/Provenance,
     verwendete Cascade-Stufe)
   - Es wird kein Modell aufgerufen und kein Provider-Secret benötigt
   - Die Preview ist kein Qualitäts-/Eval-Ergebnis, sondern ein Debug-/Verständnis-
     Werkzeug für den Prompt

4. **Optionaler Live-Test:**
   - Klick auf „Live-Test" → eine echte KI-Anfrage wird mit dem bearbeiteten
     Prompt gestartet
   - Das Ergebnis erscheint in einer Vorschau (nicht im Dokument)
   - Der Nutzer kann das Ergebnis bewerten, ohne den Prompt zu speichern
   - Der Test ist provider-/secret-gated, rate-limited und nutzt die normale
     Agent/ModelRegistry-/PromptComposer-Strecke

### Privacy- und Kostenhinweis

Die providerfreie Preview zeigt echte Projektdaten lokal in der UI/API-Antwort,
sendet aber keine Modellanfrage. Nur der optionale Live-Test sendet die angezeigten
Daten an den konfigurierten Provider und verbraucht Tokens; davor ist ein klarer
Hinweis erforderlich.

## How it works (Technical)

**Entry point:** Settings AI tab → `packages/web/components/studio/settings/IntentOverrides.tsx` (erweitert)
**Backend:** Bestehende Routen + providerfreie Preview und optionaler Live-Test
**Service:** `PromptPreviewService` in `apps/api/narrare/prompts/`
**Contract:** Prompt UX API protocols (`PromptPreviewApiProtocol`, `PromptResetApiProtocol`, `PromptLiveTestApiProtocol`) in `apps/api/narrare/prompts/contracts.py`; core protocols in `packages/core/narrare_core/prompts/contracts.py`
**Prompt:** Verwendet bestehende Prompts aus `packages/core/narrare_core/prompts/_bundled/`

### CR-07 Follow-up v3 Architecture Boundary

PROMPT-003 is the Phase-B implementation item for
`CR-AUFG-07-16` in `docs/architecture/governance/cr-07-followup-v3.md`.
The feature remains `planned` until the following contract-first boundary is
implemented and enforced:

- **Core:** provider-free preview contracts/types live under
  `packages/core/narrare_core/prompts/`; preview resolution uses the existing
  PromptComposer/variable-engine path and performs no model/provider call.
- **Backend:** prompt preview/reset/live-test Protocols are defined in
  `apps/api/narrare/prompts/contracts.py` before service/router implementation.
- **Frontend:** `PromptEditor` remains an orchestrator; resolved preview,
  variable metadata, live-test, and reset confirmation are split into focused
  components. The authoritative preview comes from the API/Core contract, not
  local hardcoded sample substitution.
- **Enforcement:** preview contract tests must prove no provider is required;
  live-test tests must prove SSE/cancel semantics where model output streams.

### Neue API-Endpunkte

| Endpoint | Methode | Beschreibung |
|----------|---------|-------------|
| `/api/v1/settings/prompts/{intent}/preview` | POST | Providerfreie Preview: vollständig aufgelöster Prompt, Variable-Provenance, Security-Klassen, Validierungsdiagnostik; kein KI-Aufruf |
| `/api/v1/settings/prompts/{intent}/test` | SSE/POST+SSE | Optionaler Live-Test: echte KI-Anfrage mit bearbeitetem Prompt; provider-/secret-gated, rate-limited, Ergebnis wird nicht persistiert |
| `/api/v1/settings/prompts/{intent}/reset` | POST | Setzt den Prompt-Override auf den systemdefinierten Standard zurück |

### Contract-Semantik

| Operation | Provider nötig? | Darf Tokens verbrauchen? | Output | Gate |
|-----------|-----------------|--------------------------|--------|------|
| Preview | Nein | Nein | Resolved Prompt + Diagnostics | PromptComposer/Variable-Validator; keine Modellroute |
| Live-Test | Ja | Ja | Gestreamtes Test-Ergebnis + Diagnostics | Normale Agent/ModelRegistry-Route, §16-UX, Rate-Limit, Token-/Privacy-Hinweis |

Die Preview darf nicht als „adopted", Eval-Abdeckung oder Runtime-Qualitätsbeweis
gezählt werden. Runtime-/Eval-Claims benötigen separate Evidence gemäß INFRA-013.

### Frontend-Änderungen

| Komponente | Neu/Erweitert | Beschreibung |
|------------|---------------|-------------|
| `packages/web/components/studio/settings/IntentOverrides.tsx` | Erweitert | Detail-Ansicht mit Variable-Info + Reset + Preview |
| `packages/web/components/studio/settings/PromptPreviewDialog.tsx` | Neu | Modal/Sheet mit vollständig aufgelöstem Prompt |
| `packages/web/components/studio/settings/PromptLiveTestDialog.tsx` | Neu | Modal mit KI-Testlauf (Streaming-Preview) |
| `packages/web/components/studio/settings/VariableMetadataPanel.tsx` | Neu | Tabelle mit Variablen-Name, Beschreibung, Beispielwert |

### Prompt-Variable Metadata

Die Variablen-Metadaten (Name, Beschreibung, Datenquelle) müssen in den
Prompt-Dateien oder einem separaten Manifest gepflegt werden:

```yaml
# packages/core/narrare_core/prompts/variable_metadata.py
- name: "kb_context"
  description: "Relevant knowledge base context for the current chapter"
  source: "KBService.get_relevant_context()"
  example: "Anna Müller — a teacher from the city..."
```

### i18n

Neue Schlüssel in `packages/i18n/messages/en/studio.json` unter `settings.ai.promptCustomization.*`:

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
| Backend SSE endpoint exists? | Preview: nein (nur Prompt-Auflösung). Live-Test: ja, wenn KI-Ausgabe erzeugt wird |
| Frontend uses SSE? | Preview: nein. Live-Test: ja — Streaming-Vorschau des KI-Ergebnisses |
| REST endpoint also needed? | Preview: ja (POST). Live-Test: höchstens Start/metadata; Ausgabe über SSE |

### User Controls
| Control | Required? | i18n key |
|---------|-----------|----------|
| Cancel/Abort | Live-Test: ja | `studio.aiActions.stop` |
| Accept | nein (Preview wird nicht persistiert) | — |
| Reject | nein | — |
| Retry | Live-Test: ja | `studio.aiActions.retry` |
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

- **Preview-Modus verwendet ECHTE Projektdaten, aber keinen Provider.** Der Nutzer
  muss verstehen, dass sensible Projektdaten sichtbar werden; es wird jedoch keine
  Modellanfrage ausgelöst.
- **Live-Test verbraucht Tokens und sendet Daten an den Provider.** Warnhinweis vor
  jedem ersten Test pro Session/Prompt.
- **Kein unbegrenztes Testen:** Rate-Limiting für den Live-Test-Endpoint (max. 5
  Tests pro Minute oder projektweiter Settings-Wert).
- **Reset ist immer möglich:** Der Original-Prompt ist im Code definiert
  (`packages/core/narrare_core/prompts/_bundled/`) und kann nicht überschrieben werden. Reset
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
- `2026-06-12` — Review-03 refresh: providerfreie Preview und optionaler,
  provider-/secret-gated Live-Test als getrennte Verträge präzisiert.
- `2026-06-21` — CR-07 Follow-up v3 linked PROMPT-003 to CR-AUFG-07-16 and
  clarified Core/Backend/Frontend contract-first boundaries. Status remains
  `planned`; no implementation or enforcement evidence exists yet.
- `2026-06-22` — Phase B implemented; PROMPT-003 → `stable`. Contract-first
  implementation across Core/Backend/Frontend (provider-free preview,
  variable metadata/provenance, reset semantics, provider-gated SSE live test).
  Enforcement: `tests/unit/core/prompts/test_preview_no_provider.py`, `tests/unit/api/prompts/test_prompt_preview_schema_contract.py`,
  `tests/integration/prompts/test_prompt_ux_router.py`, `just check-ai-ux` (0 violations), `scripts/check_frontend_file_size.py`.
  CR-AUFG-07-16 resolved; inventory entry `settings.prompts.live_test` added.

## Definition of Done

- [x] Prompt-Variablen-Panel zeigt alle `{{variablen}}` mit Beschreibung + Beispielwert — `packages/web/components/studio/settings/VariableMetadataPanel.tsx`, `packages/web/components/studio/settings/PromptVariablesAside.tsx`, `packages/web/components/studio/settings/promptVariables.ts` (evidence: `packages/web/components/studio/settings/__tests__/PromptEditor.test.tsx`).
- [x] Providerfreie Preview (Prompt-Auflösung + Provenance + Diagnostics ohne KI) implementiert — Core `packages/core/narrare_core/prompts/preview.py` / `packages/core/narrare_core/prompts/preview_types.py` / `packages/core/narrare_core/prompts/contracts.py`, Backend `apps/api/narrare/prompts/preview_service.py` / `apps/api/narrare/prompts/router_prompt_ux.py` (`/preview`), Frontend `packages/web/components/studio/settings/PromptPreviewDialog.tsx`; no-provider invariant enforced by `tests/unit/core/prompts/test_preview_no_provider.py`.
- [x] Optionaler Live-Test (KI-Anfrage + Streaming-Vorschau) provider-/secret-gated implementiert — Core `packages/core/narrare_core/agents/prompt_live_test_agent.py`, Backend `apps/api/narrare/prompts/live_test_service.py` / `apps/api/narrare/prompts/_live_test_sse.py` / `apps/api/narrare/prompts/router_prompt_ux.py` (`/live-test`, 503 on missing provider), Frontend `packages/web/components/studio/settings/usePromptLiveTest.ts` / `packages/web/components/studio/settings/PromptLiveTestDialog.tsx` via `useAIOperation` + `streamPromptLiveTest` SSE.
- [x] Reset-to-Default pro Intent mit Bestätigungsdialog implementiert — `apps/api/narrare/prompts/preview_service.py` (`reset_with_metadata`), `apps/api/narrare/prompts/router_prompt_ux.py` (`/reset`), `packages/web/components/studio/settings/PromptResetConfirmDialog.tsx` (evidence: `packages/web/components/studio/settings/__tests__/PromptResetConfirmDialog.test.tsx`).
- [x] Warnhinweis vor Live-Test (Token-Verbrauch + Projektdaten an Provider) — `packages/web/components/studio/settings/usePromptLiveTest.ts` (`acknowledged` gate + `acknowledge_token_cost`), `tokenWarning` i18n key.
- [x] i18n: Alle neuen UI-Texte in studio.json (de/en/fr) — `packages/i18n/messages/de/studio.json`, `packages/i18n/messages/en/studio.json`, `packages/i18n/messages/fr/studio.json` → `settings.prompts.promptCustomization.*` (3-locale parity).
- [x] Prompt-Variable-Metadaten (Beschreibung, Datenquelle) gepflegt — `packages/core/narrare_core/prompts/variable_metadata.py` (registry with `VariableMeta`: name/description/source/security/required).
- [x] Rate-Limiting für Live-Test-Endpoint (max. 5/min oder Settings-Wert) — `AI_PROMPT_LIVE_TEST_LIMITER` = `Rate(5, LONG_WINDOW_MS)` in `apps/api/narrare/_app/rate_limits.py` → 429 on exceed.
- [x] Tests: Preview- + Test-Endpoint (Integration), Frontend-Komponenten (Vitest) — `tests/unit/core/prompts/test_preview_no_provider.py`, `tests/unit/api/prompts/test_prompt_preview_schema_contract.py` (API↔Frontend schema), `tests/integration/prompts/test_prompt_ux_router.py` (integration), `packages/web/components/studio/settings/__tests__/PromptPreviewDialog.test.tsx`, `packages/web/components/studio/settings/__tests__/PromptLiveTestDialog.test.tsx`, `packages/web/components/studio/settings/__tests__/PromptResetConfirmDialog.test.tsx`, `packages/web/lib/api/__tests__/prompts-preview.test.ts`.
- [x] Bestehende PROMPT-001/PROMPT-002 funktionieren unverändert — `apps/api/narrare/prompts/router_prompt_ux.py` uses distinct HTTP methods/paths (`POST /{prompt_id}/{preview|reset|live-test}`); existing GET/PUT/DELETE in `apps/api/narrare/prompts/router.py` untouched.
- [x] Dokumentation: Feature-Spec auf stable gesetzt — this spec; CR-AUFG-07-16 exit evidence in `docs/architecture/governance/aufg-registry.md`; inventory entry `settings.prompts.live_test`.

---

> **Post-MVP:** Dieses Feature ist nicht vor Phase 6 abgeschlossen.
> Die bestehende Prompt-Anpassung (PROMPT-001/PROMPT-002) bleibt
> weiterhin funktional — ohne die UX-Verbesserungen dieses Features.
