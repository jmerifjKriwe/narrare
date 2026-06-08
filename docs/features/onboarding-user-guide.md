---
id: ONBOARD-001
title: "Onboarding & AI-Einführung"
status: stable
area: setup
mvp: false

ui_tooltip: "Entdecke Narrares KI-Funktionen mit einer geführten Einführung."
ui_help_short: |
  Nach der Ersteinrichtung findest du hier Demo-Projekte, eine kurze
  Tour durch die wichtigsten KI-Features und eine sanfte Einführung in
  die Arbeit mit der KI — vom ersten Prompt bis zur ersten KI-unterstützten
  Textüberarbeitung.
ui_help_long: |
  ## Onboarding & AI-Einführung

  Neu bei Narrare? Dieses Feature hilft dir, nach dem Setup schnell
  produktiv zu werden — ohne dass du zuerst eigene Inhalte erstellen
  oder dich durch die Dokumentation kämpfen musst.

  **Demo-Projekte im Dashboard:** Die drei bereits vorhandenen
  Demogeschichten (Echoes of the Thornwall, Dead Signal, Im stillen Wald)
  werden im Dashboard als Kacheln angezeigt. Ein Klick lädt das Projekt
  und du kannst sofort loslegen.

  **Geführte KI-Ersteinrichtung:** Ein kurzer Assistent (1–2 Minuten)
  zeigt dir die wichtigsten KI-Interaktionsmuster: Wie schreibst du
  einen Prompt? Wie akzeptierst oder verwirfst du einen Vorschlag?
  Wie nutzt du GhostText-Inline-Vorschläge?

  **Kontextbezogene Tooltips:** Beim ersten Erscheinen jeder KI-Funktion
  erscheint ein kurzer Erklär-Tooltip, der dir zeigt, was diese Funktion
  tut und wie du sie nutzt.
ui_available_in: [dashboard, editor]
---

# ONBOARD-001 — Onboarding & AI-Einführung

## What it does

Bietet neuen Nutzern nach der Ersteinrichtung (SETUP-001/SETUP-002) eine
geführte Einführung in Narrares KI-Funktionen. Demo-Projekte werden im
Dashboard sichtbar und per Klick ladbar. Eine Mini-Tour (1–2 Minuten)
erklärt die wichtigsten Interaktionsmuster (Prompt, GhostText, Accept/Reject).
Bestehende GhostText-Onboarding-Elemente (TipTapEditor.tsx) werden
integriert und erweitert.

## Why it exists

**CR-07 §5 Bewertung: ⭐⭐☆☆☆** — Das UX-Audit hat identifiziert:

1. **Demo-Projekte sind nach dem Setup nicht auffindbar.** Die Demos
   existieren (SETUP-002: 3 vollständige Projekte), werden im Dashboard
   aber nicht prominent angeboten. Nutzer, die Narrare evaluieren wollen,
   müssen wissen, dass sie im Wizard „Demo laden" wählen müssen.

2. **Keine geführte Einführung in KI-Fähigkeiten.** GhostText hat ein
   einmaliges Onboarding (TipTapEditor.tsx:99-101, 233-261, 520-523),
   aber es gibt keinen strukturierten Einstieg, der dem Nutzer erklärt,
   wie man mit der KI interagiert — Prompt schreiben, Ergebnis bewerten,
   akzeptieren/verwerfen.

3. **Q-011 (Distribution Strategy) bleibt offen.** Ein guter Onboarding-Flow
   ist Voraussetzung dafür, Narrare auch nicht-technischen Nutzern zugänglich
   zu machen.

## How it works (User perspective)

1. **Dashboard nach Setup:** Nach Abschluss des Setup-Wizards sieht der
   Nutzer im Dashboard drei Demo-Kacheln (Echoes, Dead Signal, Im stillen Wald)
   mit Kurzbeschreibung, Genre-Tag und Word Count. Ein Klick lädt das Projekt.

2. **KI-Einführungs-Tour:** Beim erstmaligen Öffnen des Editors erscheint
   eine kurze Tour (3–4 Schritte), die folgende Elemente erklärt:
   - **GhostText:** „Schreibe einen Satz — Narrare macht Vorschläge im
     Hintergrund. Drücke Tab, um zu übernehmen."
   - **Prompt/Eingabe:** „Markiere Text und klicke auf das Sparkles-Symbol.
     Beschreibe, was die KI ändern soll."
   - **Akzeptieren/Verwerfen:** „Nach einer KI-Aktion erscheinen
     Übernehmen/Verwerfen-Buttons. Dein Feedback hilft der KI, besser zu werden."
   - **Session/Chat:** „Nutze den Freien Assistenten in der rechten Sidebar
     für Schreibfragen und Brainstorming."

3. **Kontext-Tooltips:** Jede KI-Funktion zeigt beim ersten Aufruf einen
   kurzen Tooltip (max. 80 Zeichen), der verschwindet, sobald der Nutzer
   die Funktion einmal genutzt hat.

4. **Wiedervorlage:** Die Tour kann jederzeit über Settings → Hilfe
   oder den „?"-Button in der Sidebar erneut gestartet werden.

## How it works (Technical)

### Bestehende Infrastruktur (keine Änderung nötig)

| Komponente | Pfad | Zweck |
|------------|------|-------|
| `FeatureTour` | `components/ui/feature-tour.tsx` (192 Zeilen) | Custom Tour-Komponente mit Spotlight, Keyboard-Navigation, `localStorage`-Persistenz, i18n |
| `TourStep` Interface | Exportiert aus `feature-tour.tsx` | `{ target?, titleKey, descriptionKey }` — CSS-Selector oder zentriert |
| `FEATURE_TOUR_STEPS` | `lib/config/feature-tour-steps.ts` | 6 Steps konfiguriert (Editor, Nav, AI-Toolbar, GhostText, Worldbuilding, Settings) |
| `requestFeatureTour()` | Helper in `feature-tour.tsx` | Setzt `localStorage`-Flag, das FeatureTour startet |
| Tour-Trigger | `useQuickStart.ts:48` | Ruft `requestFeatureTour()` nach Quick-Start auf |
| `GhostTextOnboarding` | `components/editor/GhostTextOnboarding.tsx` (112 Zeilen) | Einmaliges GhostText-Tooltip mit `localStorage`-Tracking |
| `DashboardView` | `components/studio/DashboardView.tsx` (~127 Zeilen) | Rendert NovelCardGrid, wird um Demo-Sektion erweitert |
| `DemoProjectInfo` (FE) | `types/wizard.ts:39` | TypeScript-Interface für Demo-Metadaten |
| `DemoProjectInfo` (BE) | `setup/base_schemas.py:114` | Pydantic-Model für Demo-Metadaten |
| `DemoLoader.all_demo_info()` | `setup/demo_loader.py:132` | Liefert `list[DemoProjectInfo]` für alle 3 Demos |
| `setupApi` | `lib/api/setup.ts` | Frontend API Client (hat noch kein `listDemos()`) |
| `<FeatureTour>` | `app/(studio)/layout.tsx` | Rendert Tour im Studio-Layout |

### Neu zu implementieren

**1. `GET /setup/demos` Endpoint (Backend)**
- Router: `apps/api/narrare/setup/router.py` — neuer GET-Endpoint
- Nutzt bestehenden `DemoLoader.all_demo_info()` direkt (kein neuer Service)
- Response: `DemoListResponse` = `list[DemoProjectInfo]`
- Keine Auth erforderlich (Demos sind öffentliche Metadaten)
- **⚠️ RULE-17 Issue:** BE-Schema hat `language: str`, FE-Interface hat `writing_language: string`. Feld-Must vor Implementierung klären (Entweder BE-Feld umbenennen oder FE-Mapping im API-Client).

**2. `setupApi.listDemos()` (Frontend API Client)**
- Datei: `lib/api/setup.ts` — neue Methode
- Ruft `GET /setup/demos` auf, mappt Response auf `DemoProjectInfo[]`
- Berücksichtigt FIELD-Mismatch `language` ↔ `writing_language`

**3. `DemoProjectCards` Komponente (Frontend)**
- Neue Datei: `components/studio/DemoProjectCards.tsx`
- Kacheln für Demo-Projekte (Cover-Platzhalter, Titel, Genre-Tag, Word Count, Kurzbeschreibung)
- Klick löst bestehenden Demo-Load-Flow aus (SETUP-002)
- Wird als Sektion in `DashboardView` integriert
- Extrahiert aus DashboardView (RULE-04: DashboardView ~127 Zeilen → Demo-Sektion in eigener Datei)

**4. `useSeenTooltips` Hook (Frontend)**
- Neue Datei: `lib/hooks/useSeenTooltips.ts`
- Pattern analog zu `GhostTextOnboarding`: `localStorage`-basiert
- Interface: `{ seenTooltips: Set<string>; markSeen(id: string): void; isSeen(id: string): boolean }`
- Pro KI-Funktion ein Tooltip (GhostText, Prompt, Accept/Reject, Session/Chat)
- Koexistiert mit GhostTextOnboarding ohne Konflikt (unterschiedliche localStorage Keys)

**5. FEATURE_TOUR_STEPS aktualisieren (falls erforderlich)**
- Datei: `lib/config/feature-tour-steps.ts`
- Prüfung: Decken die aktuellen 6 Steps den ONBOARD-001-Inhalt ab?
- Falls nicht: Steps aktualisieren und entsprechende i18n-Keys im studio-Namespace ergänzen

**6. Tour-Replay Trigger (Frontend)**
- `requestFeatureTour()` existiert — braucht nur einen UI-Trigger
- Ort: Settings → Hilfe oder "?"-Button in der Sidebar
- Implementierung: Button/Button-Link der `requestFeatureTour()` aufruft

## UX Requirements

### AI Interaction Type
- [ ] Generation — produces new content
- [ ] Suggestion — inline ghost text
- [ ] Analysis — structured feedback/report
- [ ] Extraction — structured data from text
- [ ] Transformation — rewrites existing content
- [ ] Conversation — multi-turn AI session
- [x] Guidance/Education — erklärt KI-Interaktion (keine eigene KI)

### Streaming
Nicht anwendbar — das Feature selbst nutzt keine KI.

### User Controls
Nicht anwendbar — Tour-UI verwendet Next/Back/Done/Skip (bestehende FeatureTour-Controls), keine AI Actions.

### Loading States
Nicht anwendbar — keine KI-Ladezustände.

### Onboarding

| Question | Answer |
|----------|--------|
| Discoverable from | Dashboard, Settings→Hilfe |
| Tooltip needed? | Ja — einmalig pro KI-Funktion |
| Tour step needed? | Ja — 3–4 Schritte nach erstem Editor-Besuch |
| First-run guidance? | Ja — nach Abschluss des Setup-Wizards |

### Error Handling

| Scenario | User message (de) | User action |
|----------|-------------------|-------------|
| Demo laden fehlschlägt | "Demo-Projekt konnte nicht geladen werden. Bitte versuche es erneut." | Retry-Button |
| Tour-Backend nicht verfügbar | Tour läuft rein client-seitig — kein Fehlerfall | — |

## Constraints & Edge Cases

- **FeatureTour existiert bereits:** Keine neue Tour-Library erforderlich. Die bestehende Custom `FeatureTour`-Komponente (192 Zeilen, 12 Tests) wird unverändert genutzt. Shepherd.js oder andere Libraries werden NICHT eingeführt.
- **GhostTextOnboarding koexistiert:** Das bestehende `GhostTextOnboarding` (`components/editor/GhostTextOnboarding.tsx`, 112 Zeilen) bleibt bestehen und koexistiert mit dem neuen `useSeenTooltips`-System. Beide nutzen `localStorage` mit unterschiedlichen Keys — kein Konflikt.
- **Demo-Discovery nur nach erstem Setup:** Nutzer, die bereits ein eigenes Projekt haben, müssen die Demos nicht sehen. Steuerung via Query-Parameter oder UI-Logik (Post-MVP-Entscheidung).
- **Tour nicht aufdringlich:** Die Tour kann jederzeit mit Escape oder „Skip" abgebrochen werden. Das bestehende „Nicht mehr anzeigen"-Verhalten via `localStorage` (`TOUR_STORAGE_KEY`) bleibt erhalten.
- **Keine erneute Tour bei Projektwechsel:** `onboardingTourCompleted` ist benutzerweit gespeichert, nicht projektbezogen.
- **FIELD-Mismatch BE ↔ FE:** `DemoProjectInfo.language` (BE) vs. `DemoProjectInfo.writing_language` (FE). Muss vor Implementierung von `GET /setup/demos` geklärt werden (RULE-17).
- **Kein Ersatz für vollständige Dokumentation:** Die Tour ersetzt nicht `docs/_shared/GLOSSARY.md` oder die Feature-Docs. Sie ist ein Schnelleinstieg.
- **Focus-Trap:** Bestehende FeatureTour hat keinen Focus-Trap. Als Nice-to-have im DoD aufgenommen (Barrierefreiheit).

## Related Features

- [SETUP-001](../setup/SETUP-001-setup-wizard.md) — Setup Wizard (Voraussetzung)
- [SETUP-002](../setup/SETUP-002-demo-content.md) — Demo Projects (bestehende 3 Demos)
- [SETUP-004](../setup/SETUP-004-provider-config.md) — AI Provider Configuration
- [WRITE-007](../writing/WRITE-007-inline-suggestions.md) — GhostText-Onboarding-Integration
- [CHAT-001](../chat/CHAT-001-free-form-chat.md) — Freier Assistent (Tour-Step)

## Status & History

- `2026-06-08` — Added to registry (CR-07 UX Audit §5 Remediation)
- `2026-06-08` — Spec refined: Architecture Pre-Implementation Gate (NEEDS-SPEC-REFINEMENT). ~60% Infrastruktur existiert bereits (FeatureTour, DemoLoader, DemoProjectInfo). Shepherd.js verworfen zugunsten bestehender Custom-Lösung. GET /setup/demos als feste Entscheidung dokumentiert. RULE-17 FIELD-Mismatch (language ↔ writing_language) identifiziert.
- `2026-06-08` — Implemented: GET /setup/demos endpoint, DemoProjectCards component, useSeenTooltips hook, Tour-Replay in Settings, i18n (de/en/fr). 18 new tests (8 frontend + 8 hook + 2 contract).

---

## RULE-XX Compliance Matrix

| Regel | Relevanz | Status |
|-------|----------|--------|
| RULE-01b: Agents via ModelRegistry | Nicht anwendbar — kein LLM-Aufruf | ✅ k.A. |
| RULE-02: Prompts nur in core/prompts/ | Nicht anwendbar — keine Prompts | ✅ k.A. |
| RULE-03: Contract vor Implementation | Backend: `DemoListResponse` Schema in `setup/schemas.py`. Frontend: `TooltipState` Interface in `useSeenTooltips.ts` | 📋 Zu erstellen |
| RULE-04: Modularisieren statt komprimieren | DashboardView ~127 Zeilen → Demo-Sektion extrahieren in `DemoProjectCards.tsx`. FeatureTour unverändert (192 Zeilen, getestet) | 📋 Zu prüfen |
| RULE-06: Eine Verantwortlichkeit pro Datei | `DemoProjectCards`, `useSeenTooltips`, Tour-Replay Trigger jeweils eigenständig | ✅ Design |
| RULE-11: No Silent Failures | Demo-Load-Fehler werden angezeigt. Tour-Fallback: clientseitig, kein Fehlerfall | ✅ Design |
| RULE-12: Service Layer als öffentliche API | Demo-Metadaten SSOT im Backend (`DemoLoader`). Kein Frontend-Hardcode von Demo-Daten | 📋 Zu prüfen |
| RULE-17: API Contract Consistency | **⚠️ FIELD-Mismatch:** BE `DemoProjectInfo.language` vs. FE `DemoProjectInfo.writing_language`. Vor Implementierung klären | 🔴 Offen |
| RULE-20: Keine halben Implementierungen | „Demo im Dashboard sichtbar" = Kachel + Klick-Laden + Fehlerbehandlung | ✅ DoD |
| RULE-22: i18n für alle UI-Texte | Tour-Texte und Tooltips in `studio`-Namespace (kein neuer Namespace) | 📋 DoD |

## Definition of Done

- [ ] GET /setup/demos Endpoint mit `DemoListResponse` Contract (RULE-03)
- [ ] `setupApi.listDemos()` im Frontend API Client
- [ ] RULE-17 FIELD-Match geklärt: `language` (BE) ↔ `writing_language` (FE) — Contract Test
- [ ] `DemoProjectCards` Komponente im Dashboard (extrahiert aus DashboardView, RULE-04)
- [ ] `useSeenTooltips` Hook (analog GhostTextOnboarding-Pattern)
- [ ] `FEATURE_TOUR_STEPS` für ONBOARD-001 Inhalt aktualisiert (oder bestätigt: aktuelle 6 Steps decken es ab)
- [ ] Tour-Replay Trigger in Settings/Hilfe
- [ ] A11y: aria-live bei Step-Wechsel (Nice-to-have: Focus-Trap in FeatureTour)
- [ ] i18n: studio-Namespace erweitert für Demo-Kacheln und neue Tooltips (kein neuer Namespace)
- [ ] Tests: DemoProjectCards (Vitest), useSeenTooltips (Vitest), GET /setup/demos (Backend pytest)
- [ ] Keine Regressionen: Bestehende FeatureTour, GhostTextOnboarding, DemoLoader funktionieren unverändert
- [ ] Spec auf stable gesetzt
