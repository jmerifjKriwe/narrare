---
id: ONBOARD-001
title: "Onboarding & AI-Einführung"
status: planned
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

**Demo-Discovery im Dashboard:**
- **Frontend:** Dashboard-Komponente prüft `GET /api/v1/setup/demos` auf
  verfügbare Demo-Projekte (oder liest aus Session-Storage, ob Demos
  verfügbar sind — Post-MVP-Entscheidung)
- **Backend:** Optional ein `GET /setup/demos`-Endpoint, der Metadaten zu
  den drei Demo-Projekten zurückgibt (Titel, Genre, Sprache, Word Count,
  Kurzbeschreibung)
- **Laden:** POST /api/v1/setup/load-demo/{demo_id} → erzeugt ein neues
  Novel aus den Demo-Daten (analog zu SETUP-002)

**KI-Einführungs-Tour:**
- **Frontend:** Client-seitige Tour-Komponente (z. B. basierend auf
  Shepherd.js oder einer einfachen Custom-Komponente)
- **State:** `localStorage` oder `zustand` speichert `onboardingTourCompleted`
  und `onboardingTourDismissed`
- **Tooltip-System:** Zustand-Store für einmalige Tooltips
  (`seenTooltips: Set<string>`), gespeichert in `localStorage`

**Kein neuer Backend-Service erforderlich** — die Tour und Tooltips sind
reine Frontend-Logik. Das Demo-Loading nutzt den bestehenden
`DemoLoader` aus SETUP-002.

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
Nicht anwendbar — Tour-UI verwendet Schließen/Überspringen, keine AI Actions.

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

- **Demo-Discovery nur nach erstem Setup:** Nutzer, die bereits ein
  eigenes Projekt haben, müssen die Demos nicht sehen.
- **Tour nicht aufdringlich:** Die Tour kann jederzeit mit Escape
  oder „Überspringen" abgebrochen werden. Ein „Nicht mehr anzeigen"-Häkchen
  verhindert Wiederholung.
- **Keine erneute Tour bei Projektwechsel:** `onboardingTourCompleted` ist
  benutzerweit gespeichert, nicht projektbezogen.
- **Bestehende GhostText-Onboarding-Elemente integrieren:** Die aktuellen
  `TipTapEditor.tsx:99-101`, `233-261`, `520-523` GhostText-Einmal-Tooltips
  bleiben erhalten oder werden in das neue Tooltip-System migriert.
- **Kein Ersatz für vollständige Dokumentation:** Die Tour ersetzt nicht
  `docs/_shared/GLOSSARY.md` oder die Feature-Docs. Sie ist ein Schnelleinstieg.

## Related Features

- [SETUP-001](../setup/SETUP-001-setup-wizard.md) — Setup Wizard (Voraussetzung)
- [SETUP-002](../setup/SETUP-002-demo-content.md) — Demo Projects (bestehende 3 Demos)
- [SETUP-004](../setup/SETUP-004-provider-config.md) — AI Provider Configuration
- [WRITE-007](../writing/WRITE-007-inline-suggestions.md) — GhostText-Onboarding-Integration
- [CHAT-001](../chat/CHAT-001-free-form-chat.md) — Freier Assistent (Tour-Step)

## Status & History

- `2026-06-08` — Added to registry (CR-07 UX Audit §5 Remediation)

---

## RULE-XX Compliance Matrix

| Regel | Relevanz | Status |
|-------|----------|--------|
| RULE-01b: Agents via ModelRegistry | Nicht anwendbar — kein LLM-Aufruf | ✅ k.A. |
| RULE-02: Prompts nur in core/prompts/ | Nicht anwendbar — keine Prompts | ✅ k.A. |
| RULE-03: Contract vor Implementation | Nicht anwendbar — reine Frontend-Logik | ✅ k.A. |
| RULE-04: Modularisieren statt komprimieren | Tour-Komponente und Tooltip-System getrennt halten | 📋 Zu prüfen |
| RULE-06: Eine Verantwortlichkeit pro Datei | Tooltip-Store, Tour-Komponente, Dashboard-Card getrennt | 📋 Zu prüfen |
| RULE-20: Keine halben Implementierungen | "Demo im Dashboard sichtbar" bedeutet: Kachel + Klick-Laden + Fehlerbehandlung | ✅ DoD |
| RULE-22: i18n für alle UI-Texte | Tour-Texte und Tooltips in studio.json (de/en/fr) | 📋 DoD |

## Definition of Done

- [ ] Demo-Projekte sind im Dashboard als Kacheln sichtbar (Cover/Beschreibung/WC)
- [ ] Klick auf Demo-Kachel lädt ein neues Novel aus Demo-Daten (analog SETUP-002)
- [ ] KI-Einführungs-Tour (3–4 Schritte) erscheint beim ersten Editor-Besuch
- [ ] Tour kann mit Escape / „Überspringen" abgebrochen werden
- [ ] Tour kann über Settings › Hilfe erneut gestartet werden
- [ ] Einmalige Tooltips pro KI-Funktion (max. 80 Zeichen) implementiert
- [ ] Tooltip-Status in localStorage persistiert
- [ ] Bestehende GhostText-Tooltips (TipTapEditor.tsx) integriert oder migriert
- [ ] i18n: Alle Tour-Texte und Tooltips in studio.json (de/en/fr)
- [ ] RULE-04-Prüfung: Tour-Komponente, Tooltip-System, Dashboard-Card getrennt
- [ ] Tests: Tour-Flow (Vitest), Dashboard-Demo-Darstellung, Tooltip-Persistenz
- [ ] Keine regressions: Bestehende Demos (SETUP-002) funktionieren unverändert
- [ ] Dokumentation: Diese Feature-Spec auf stable gesetzt
