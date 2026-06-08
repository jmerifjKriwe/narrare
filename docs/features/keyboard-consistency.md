---
id: KEYBOARD-001
title: "Tastatur-Konsistenz"
status: planned
area: settings
mvp: false

ui_tooltip: "Einheitliche Tastaturkürzel für alle KI-Interaktionen."
ui_help_short: |
  Standardisiert die Tastaturkürzel in Narrare, damit KI-Aktionen
  überall gleich bedienbar sind: Ctrl+Enter für Absenden, Escape für
  Abbrechen, Tab für Übernehmen von GhostText — konsistent in Editor,
  Chat, KB-Dialogen und Analyse-Fenstern.
ui_help_long: |
  ## Tastatur-Konsistenz

  Narrare wächst — und mit jeder neuen Funktion können neue Tastaturkürzel
  entstehen. Dieses Feature sorgt dafür, dass alle KI-Interaktionen
  dieselben Tastaturkürzel verwenden.

  ### Einheitliche Shortcuts

  | Aktion | Shortcut | Wo |
  |--------|----------|----|
  | KI-Aktion ausführen (Prompt senden) | Ctrl/Cmd+Enter | Alle Textareas |
  | KI-Vorschlag übernehmen | Tab | GhostText, Inline-Vorschläge |
  | Vorgang abbrechen/stoppen | Escape | Alle KI-Operationen |
  | Nächste Alternative | Ctrl/Cmd+. | Rewrite, Generation |
  | Vorherige Alternative | Ctrl/Cmd+, | Rewrite, Generation |

  ### Bestehende Abweichungen

  - KB-Dialoge verwenden Ctrl+Enter ✅ (beibehalten)
  - Session Chat verwendet einfaches Enter ⚠️ (sollte Shift+Enter = Newline,
    Ctrl+Enter = Senden werden)
  - GhostText Tab-Accept existiert bereits ✅
  - Escape-Cancel für alle SSE-Streams fehlt ❌
ui_available_in: [settings, editor, session, kb]
---

# KEYBOARD-001 — Tastatur-Konsistenz

## What it does

Vereinheitlicht die Tastaturbedienung aller KI-Interaktionen in Narrare
nach einem konsistenten Schema: Ctrl+Enter zum Absenden, Escape zum
Abbrechen, Tab zum Übernehmen. Schließt Lücken, wo nur Klick-Bedienung
möglich ist, und dokumentiert alle Shortcuts in den Einstellungen.

## Why it exists

**CR-07 §7 Bewertung: ⭐⭐☆☆☆** — Das UX-Audit hat identifiziert:

1. **Ctrl/Cmd+Enter** für KB-Textareas (`KBSessionFieldList.tsx:191-199`,
   `KBInterviewView.tsx:230-234`) — konsistent und gut.

2. **Enter** für Session Chat (`SessionActions.tsx:47-52`) — Enter sendet
   die Nachricht, aber Shift+Enter für Newline existiert nicht
   konsistent. Nutzer erwarten Ctrl+Enter zum Senden in Multi-Line-Inputs.

3. **Click-only** für die meisten AI-Output-Actions — Accept, Reject, Retry
   sind nur per Mausklick erreichbar. Keine Tastaturkürzel.

4. **Tab für GhostText** existiert bereits (`TipTapEditor.tsx:520-523`
   GhostText-Extension) — muss erhalten bleiben.

5. **Escape für Cancel** fehlt für die meisten SSE-Streams — nur
   explizite Stop-Buttons vorhanden.

### Konkret betroffene Bereiche

| Bereich | Aktuelles Verhalten | Ziel |
|---------|-------------------|------|
| KB Field Suggest (Textarea) | Ctrl+Enter ✅ | Beibehalten |
| KB Interview (Textarea) | Ctrl+Enter ✅ | Beibehalten |
| Session Chat (Input) | Enter (send) ⚠️ | Shift+Enter = Newline, Ctrl+Enter = Senden |
| Generation Prompt | Click only ❌ | Ctrl+Enter = Generieren |
| Rewrite Config | Click only ❌ | Ctrl+Enter = Umschreiben |
| GhostText Accept | Tab ✅ | Beibehalten + dokumentieren |
| Cancel AI Op | Stop-Button ❌ | Escape + Stop-Button |
| Accept AI Output | Click only ❌ | Ctrl+Y (Accept) / Ctrl+N (Reject) |

## How it works (User perspective)

1. **Ctrl+Enter überall:** Egal ob KB-Dialog, Session-Chat,
   Generation-Prompt oder Rewrite-Config — Ctrl+Enter führt die
   KI-Aktion aus.

2. **Shift+Enter = Neue Zeile:** In allen Textareas erzeugt Shift+Enter
   einen Zeilenumbruch, Enter ohne Shift führt die Aktion aus (nur in
   Single-Line-Inputs; in Multi-Line-Inputs gilt Ctrl+Enter für Aktion).

3. **Escape bricht ab:** Während einer KI-Operation (Streaming, SSE)
   bricht Escape die Operation ab — genauso wie der Stop-Button.
   Nach Abschluss schließt Escape das Ergebnis-Panel oder Modal.

4. **Keyboard-Shortcut-Liste:** In Settings › Shortcuts werden alle
   Tastaturkürzel aufgelistet, inklusive der KI-spezifischen.

### GhostText (bestehend, beibehalten)
- **Tab** akzeptiert den aktuellen Ghost-Text-Vorschlag
- **Escape** verwirft den Vorschlag (besteht teilweise)
- Keine Änderung am bestehenden Verhalten

## How it works (Technical)

**Scope:** Reine Frontend-Änderungen. Keine neuen Backend-Endpoints.

### Änderungsübersicht

| Datei | Änderung |
|-------|----------|
| `SessionActions.tsx:47-52` | Enter → Shift+Enter=Newline, Ctrl+Enter=Send |
| `GenerationPanel.tsx` | Ctrl+Enter-Handler für Prompt-Textarea |
| `TipTapEditor.tsx` | Escape-Handler für Cancel bei aktiver SSE-Operation |
| `KBInterviewView.tsx` | Escape-Cancel (bestehenden Stop-Button ergänzen) |
| `KBSessionFieldList.tsx` | Escape-Cancel (bestehenden Stop-Button ergänzen) |
| `useSessionSocket.ts` | Escape → send cancel message |
| `SettingsView.tsx` | Shortcuts-Liste um KS-Aktionen erweitern |
| `studio.json` | Neue i18n-Keys für Shortcut-Beschreibungen |

### Keyboard-Handler-Pattern

```typescript
// Standard-Handler für Ctrl+Enter in Textareas
const handleKeyDown = (e: React.KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
    e.preventDefault();
    onSubmit(); // Führt die KI-Aktion aus
  }
  if (e.key === "Escape" && isStreaming) {
    e.preventDefault();
    onCancel(); // Bricht die Operation ab
  }
};
```

### i18n (neue Keys)

| Key | DE | EN | FR |
|-----|----|----|----|
| `shortcuts.ai.ctrlEnter` | KI-Aktion ausführen | Run AI Action | Exécuter l'action IA |
| `shortcuts.ai.escape` | Vorgang abbrechen | Cancel Operation | Annuler l'opération |
| `shortcuts.ai.tabAccept` | GhostText übernehmen | Accept Ghost Text | Accepter le texte fantôme |
| `shortcuts.ai.nextAlt` | Nächste Alternative | Next Alternative | Alternative suivante |
| `shortcuts.ai.prevAlt` | Vorherige Alternative | Previous Alternative | Alternative précédente |
| `shortcuts.ai.acceptOutput` | KI-Output übernehmen | Accept AI Output | Accepter la sortie IA |
| `shortcuts.ai.rejectOutput` | KI-Output verwerfen | Reject AI Output | Rejeter la sortie IA |

## UX Requirements

### AI Interaction Type
- [ ] Generation — produces new content
- [ ] Suggestion — inline ghost text
- [ ] Analysis — structured feedback/report
- [ ] Extraction — structured data from text
- [ ] Transformation — rewrites existing content
- [ ] Conversation — multi-turn AI session
- [x] Navigation/Control — Tastatur-Kürzel (keine eigene KI)

### Streaming
Nicht anwendbar — Keyboard-Handler sind unabhängig vom Streaming.

### User Controls
Nicht anwendbar — Keyboard-Shortcuts ergänzen bestehende UI-Controls.

### Error Handling
Keine spezifischen Fehlerfälle — Keyboard-Handler haben keinen Backend-Status.

### Onboarding
| Question | Answer |
|----------|--------|
| Discoverable from | Settings › Shortcuts |
| Tooltip needed? | Optional: "Ctrl+Enter zum Senden" im Textarea-Placeholder |
| Tour step needed? | Optional — Teil der KI-Einführungs-Tour (ONBOARD-001) |

## Constraints & Edge Cases

- **Mac-Kompatibilität:** Alle Shortcuts müssen sowohl mit Ctrl (Windows/Linux)
  als auch Cmd (Mac) funktionieren.
- **Shift+Enter in Single-Line-Inputs:** Wenn ein Inputfeld nur eine Zeile
  erwartet, sendet Enter direkt — Shift+Enter ist dann ohne Effekt.
- **Escape-Konflikte:** Escape schließt auch Modals/Dropdowns. Wenn eine
  KI-Operation aktiv ist, hat Cancel vor Close-Dialog Priorität.
- **GhostText Escape:** Wenn GhostText aktiv ist und der Nutzer Escape drückt,
  muss geprüft werden, ob Escape den GhostText verwirft oder die
  übergeordnete KI-Operation abbricht. Priorität: GhostText-Verwerfung.
- **Keine Änderung an bestehenden Ctrl+Enter-Stellen:** KB-Dialoge bleiben
  unverändert. Nur Stellen, die aktuell kein Ctrl+Enter verwenden, werden
  angepasst.
- **Bestehende Stop-Buttons bleiben erhalten:** Keyboard-Shortcuts ergänzen,
  ersetzen nicht die visuellen Controls (§16.2 Cancel Rule).

## Related Features

- [ONBOARD-001](../onboarding-user-guide.md) — Tour kann Shortcuts erwähnen
- [SET-001](../settings/SET-001-user-settings.md) — Shortcuts-Liste in Settings
- [WRITE-007](../writing/WRITE-007-inline-suggestions.md) — GhostText Tab-Verhalten
- [CHAT-001](../chat/CHAT-001-free-form-chat.md) — Session Chat Enter-Verhalten

## Status & History

- `2026-06-08` — Added to registry (CR-07 UX Audit §7 Remediation)

## Definition of Done

- [ ] Ctrl+Enter führt KI-Aktionen in ALLEN Textareas aus (Generation, Rewrite, Session, KB)
- [ ] Shift+Enter erzeugt Newline in allen Multi-Line-Inputs
- [ ] Escape bricht aktive KI-Operationen ab (alle SSE-Streams)
- [ ] Escape schließt Ergebnis-Panel nach abgeschlossener Operation
- [ ] GhostText: Tab-Accept und Escape-Dismiss bleiben erhalten und sind dokumentiert
- [ ] Keyboard-Handler für Mac (Cmd) + Windows/Linux (Ctrl) getestet
- [ ] Settings › Shortcuts zeigt alle KI-Shortcuts mit Beschreibung
- [ ] Keine Regression: Bestehende Ctrl+Enter-Stellen (KB) funktionieren unverändert
- [ ] i18n: Alle Shortcut-Beschreibungen in studio.json (de/en/fr)
- [ ] Escape-Konflikt gelöst: Cancel > Close-Dialog bei aktiver KI-Operation
- [ ] Tests: Keyboard-Handler (Vitest, ggf. Playwright für Escape-Cancel)
- [ ] Dokumentation: Feature-Spec auf stable gesetzt

---

> **Post-MVP / Low Priority:** Dieses Feature ist aufgrund der
> visuellen Workarounds (Stop-Buttons, Click-Controls) niedriger
> priorisiert als die §16-Compliance und die Fehlerbehandlung.
> Es wird erst nach Abschluss der P0/P1-CR-07-Aufgaben angegangen.
