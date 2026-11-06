# Narrare UI-Rework — Design-Guide (Richtung C: Command & Fokus)

Stand: 2026-11-06 · Status: Norm (Slice 1), reconciled with the landed visual-identity wave · Ablage: `~/.opencode/plan` (Plan-Modus)
Build-Session verschiebt nach `docs/superpowers/specs/` + Plan nach `docs/superpowers/plans/`. Move, never copy.

## 1. Intent und Why

Die Screenshots in `assets/screenshots/01-07` zeigen kein modernes Schreib-Tool, sondern ein Admin-Dashboard mit Manuskript darin: generisches Card-Kit, native Forms, abgeschnittene Chapter-Titel, drei Docks ohne Ort für Kommendes.

Gleichzeitig legt `docs/features/INDEX.md` ~20 UI-tragende Features oben drauf (WRITE-008 Multi-Draft, WRITE-013 Workflows, PLAN-001..006 Timeline/Storyboard/Character-Arc, ANAL-001..011 Analyse-Suite, KB-008/010 Graph, CONS-002 Regeln, STATS-001/002 Stats/Costs, Prompt-History, Diffs, Slash-Actions). Flickwerk würde beim ersten Canvas-Feature wieder aufbrechen.

Dieser Guide ist die bindende Norm für den Rework: Was gebaut werden darf, was verboten ist, und wie jede Implementierung beweist, dass sie nicht driftet.

## 2. Goals / Non-Goals / Anti-Goals

Goals:
- G1: Manuskript als Held — Fokus-Fläche, lesbare Measure, EB Garamond nur für Prosa.
- G2: Erweiterbare Shell — Areas Schreiben/Planen/Wissen/Analysieren, austauschbares rechtes Dock, eigene Full-Page-Canvas für Timeline/Storyboard/Graph/Stats.
- G3: Command-first — ⌘K als Herz für Navigation + AI-Aktionen (Diff, Varianten, Prompt-History, Job-Status).
- G4: Norm + lebender Beweis — `DESIGN.md`-Norm plus `/design`-Route im selben Vite-Graph, abgesichert durch bestehende Gates (axe, typeScale) + ein Screenshot-Test.
- G5: Dark-fähig und tastatur-bedienbar ab Tag 1, keine Nachrüstung.

Non-Goals (später, nicht Teil des Reworks):
- Onboarding/Setup-Wizard-Neubau, Import/Sync/Extern-Sync, MCP/A2A-Adapter-UI, LLM-Wiki-Vollausbau.

Anti-Goals (Misserfolg auch wenn es technisch läuft):
- Neues generisches SaaS-Card-Kit, All-Caps-Eyebrows, `·`-Meta-Strings, `—`-Labels, Tinten-Schwarz als Ersatz für Schwarz.
- Native ungestylte Selects/Buttons neben Custom-Controls.
- Abgeschnittene Titel; Selektion per farbiger Vollfläche statt Gewichts-/Positions-Markierung.
- Gestapelte Formular-Docks statt Konversation/Diff/Graph-Patterns.

## 3. Constraints

- Tokens gehören der Shell: `web/globals.css:18-87` (`light-dark()`, oklch, `color-scheme`, `--radius 4px / --radius-lg 8px`). Capabilities unter `app/capabilities/*/web` tragen Utilities, nie eigene Palette (Kommentar `globals.css:3-8`).
- Alias `@shell` zeigt auf `web/` (`web/vite.config.ts:42-45`, `web/tsconfig.json` paths identisch). Capability importiert Shell, nie umgekehrt.
- Type-Scale mit Leading auf Token (`globals.css:154-166`), Prosa `.ProseMirror` EB Garamond 400/600, `max-width 34rem`, Rhythmen in `em` (`globals.css:197-368`). 600 ist das härteste echte Gewicht — kein synthetisches 700.
- Ports/Proxies/Cache-Verhalten (`vite.config.ts:16-61`) bleiben unangetastet; E2E-No-Store (#634) und strenge Ports sind Konfiguration.
- Gates: `just check`, `just test-file`, `just verify`, axe-Gate (AA 4.5:1, vgl. Kommentar zu `--muted` in `globals.css:31-34`), `typeScale.test`, E2E-Screenshots nach `assets/screenshots/`.
- Governance-Budget (Spec §8): kein Pflicht-Gate für separates Tool, das Pflege kostet. Darum kein Storybook als Pflicht.

## 4. Approaches (gewählt: C)

A — Aufräumen im Bestand: Spacing/Radien/Forms vereinheitlichen, Truncation fixen. Tage, aber kein Platz für Timeline/Graph/Analyse. Verworfen weil `docs/features` genau diese Canvas-Fälle aufzwingt.

B — Shell neu, Inhalte portieren: Areas, Dock, Canvas, ein AI-Pattern-Set. Wochen, alle `web/` + Capability-Webs betroffen. Tragfähig, aber ohne Leitbild beliebig.

C — Command & Fokus (gewählt): wie B, plus ⌘K-first, dunkel-fähig, Diff/Varianten eingebaut. Teuerste Richtung (Tastaturführung, A11y, Dark-Kontraste), aber einzige mit Ort für jede Feature-Zeile. Vom Nutzer am 2026-11-06 per Mockup-Vergabe gewählt.

## 5. Festgelegtes Design (bindend)

### 5.1 Tokens

Basis bleibt `web/globals.css`. Ergänzt wird nur, was fehlt — keine zweite Palette:
- `--overlay`, `--scrim`, `--shadow-overlay` (bereits vorhanden) für Command-Palette/Dialogs wiederverwenden.
- Gestrichen: `--diff-add`, `--diff-del`, `--diff-hunk` — die gelandete Diff-Darstellung (`border-success` für Added, `border-danger` für Removed, `PromptsPage.tsx:400,407`, Visual-Identity §A4) trägt die Bedeutung bereits; neue Tokens würden nur ein zweites Vokabular für denselben Zustand schaffen.
- `--focus`-Ring Pflicht auf jedem interaktiven Element, `:focus-visible` immer sichtbar, `forced-colors`-Fallback wie beim ProseMirror-Caret.
- Verboten: drittes Radius-Maß, Pills außerhalb Filter/Avatar, Hue als Control-Füllung, Area-Farbe außerhalb Nav-Icons (vgl. `globals.css:66-71`).

### 5.2 Typografie

- UI: eine Sans (Bestand), Prosa: EB Garamond 400 lesend / 600 Headings. Keine dritte Familie.
- Skala ausschließlich aus `@theme inline`-Tokens (`text-meta` bis `text-hero`). Kein ad-hoc `leading`, keine All-Caps-Labels, keine `·`-Meta-Zeilen.
- Zeilenlänge Prosa ≤ 80ch, Measure 34rem bleibt. Der Chapter-Row-Name ist vollständig (`NovelPage.tsx:658` als `aria-label` aus Titel + Wortzahl); die visuelle Einzeile (`truncate`, `NovelPage.tsx:678`) ist Density, kein Datenverlust. Umbruch nur dort, wo die Rail-Geometrie ihn trägt — als Follow-up, nicht hier.
- Sprachwahl: gelandet — `LanguageSwitcher.tsx` nutzt bereits den getokenten `Select` aus `web/ui/field`; kein natives Select, kein Neubau.

### 5.3 Layout / Shell

- Top-Bar: nur Titel-Kontext + ⌘K + Theme + Language. Kein Formular-Wildwuchs.
- Rail: 48px fein / 168px grob (`--rail-width`), Icons + Label, Areas mit Identity-Hue nur dort.
- Workspace: Manuskript zentriert, `Continue writing` gehört in eine Editor-Toolbar, nicht als frei schwebender Button. Fokus-Modus blendet Docks aus.
- Rechtes Dock: genau ein aktiver Kontext (Chat ODER Konsistenz ODER Voice ODER Analyse), austauschbar, nicht gestapelt — gelandet per generierter `docks.ts` (single-active-context) und `NovelPage.tsx:234-242` (die gematchte Child-Route ist der Dock-State, kein lokales Flag). Header mit Titel + Schließen, Liste mit `--rule`-Trennern statt `--border`-Karten.
- Canvas: Timeline/Storyboard/Graph/Stats als eigene Routes, nicht als Dock. Shelf-Cards verlinken dorthin.

### 5.4 Command-Palette

- Ein Auslöser (⌘K + Button), eine Liste, eine Tastaturführung (↑↓/Enter/Esc, Focus-Trap, Live-Region) — gelandet in `web/routes/__root.tsx` (Palette-Verdrahtung) + `web/components/Palette.tsx`; die Norm hält nur fest, was jede neue Aktion erben muss.
- Aktionen: Navigation + AI-Aktionen (Rewrite, Extend, Voice-Check, Diff anzeigen, Variante regenerieren, Prompt-History). Gleiche Zeilen-Geometrie für alle.
- Slash-Commands im Editor rufen dieselben Aktionen — kein zweites Menü-Design.

### 5.5 AI-Patterns (einmal definieren, überall verwenden)

- Diff-Ansicht (Standard aus `ai-ux/CR-AUFG-07-18`): Hunk-Header, Add/Del-Zeilen, Accept/Discard pro Hunk.
- Multi-Draft-Vergleich: nebeneinander, max. 3, gleiche Toolbar-Sprache wie Diff.
- Job-Status: ein `JobStatus`-Baustein (`web/ui/JobStatus.tsx`), kein Custom-Spinner pro Feature.
- Prompt-History: letzte Läufe einsehbar, erneut ausführbar.
- Leere/Fehler-Zustände: sagen was fehlt und was zu tun ist, keine Entschuldigungen.

### 5.6 Dark / A11y

- Jedes Token-Paar misst AA (4.5:1) auf Ground UND Card — wie `--muted`/`--warning` bereits kommentiert. Neue Paare liefern Messwerte im PR.
- Tastatur-Pfad für alles, sichtbarer Ring, `prefers-reduced-motion` respektiert, Kontrast im Dark-Mode neu gemessen (Pfirsich-Primary aus Shot 07 ist zu hell für Vollflächen).

## 6. Norm + Beweis (1+3, schlank, Pflicht)

1. `DESIGN.md` (dieser Guide, nach Move unter `docs/superpowers/specs/`): bindende Norm mit Do/Don't.
2. `/design`-Route, settings-owned: `app/capabilities/settings/web/` trägt sie nach dem `routes.tsx`-Muster, root-parented (`getParentRoute: () => rootRoute`, Pfad `/design`) — außerhalb der Settings-Hub-Cluster und ohne Benutzer-Doku. Sie rendert Tokens + alle `web/ui/`-Zustände im selben Vite-Graph (kein Storybook, kein Extra-Dep, Alias `@shell` gilt automatisch). Grund: `web/router.tsx` mountet nur Capability-Routen via `web/lib/generated/routes.ts` — eine Shell-eigene Route unter `web/routes/` würde nie gemountet.
3. Gates: bestehende `axe` + `typeScale.test` weiter grün, plus genau ein Playwright/E2E-Screenshot-Test auf `/design` (light+dark). Screenshots nach `assets/screenshots/` aktualisieren, sobald Chrome sich ändert. Keine volle visuelle Suite, keine neuen Thresholds.

Verboten: Storybook als Pflicht-Gate; separates Tool mit eigenem Config- und Story-Pflegeaufwand. Erst bei Team-Wachstum neu bewerten.

## 7. Was dem Builder überlassen bleibt

- Exakte Sans-Wahl innerhalb Bestand, Feinwerte für Spacing-Skala, finale ⌘K-Liste pro Area.
- Router-Namen für neue Canvas-Routes, E2E-Port-Belegung folgt `stack.py`.
- Entfällt als Entscheidung: `/design` ist settings-owned und root-parented (s. §6.2) — nicht Teil der Hub-Cluster, nicht in der Benutzer-Doku.

## 8. Abnahme

- `[ ]` Kein Shot 01-07-Muster mehr (Truncation ohne barrierefreies Äquivalent — die akzeptierte Regel steht in §5.2 — Native-Controls, Stapel-Docks, All-Caps).
- `[ ]` Jede neue Feature-Zeile aus §1 hat einen Ort (Dock ODER Canvas ODER Command) — namentlich im Plan.
- `[ ]` `just check`, betroffene Suites, E2E-Screenshots gelesen; Kontrast-Messwerte im PR.
- `[ ]` Guide + Route + ein Screenshot-Test grün, sonst kein Merge.
