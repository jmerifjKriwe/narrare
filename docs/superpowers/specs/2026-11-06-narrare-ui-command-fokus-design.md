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

### 5.7 Platz-Atlas (bindend)

Jede künftige Feature-Familie hat genau ein Zuhause. Diese Sektion ist die
Karte, gegen die alle späteren Tasks bauen: Kein neues Dock, keine neue
Canvas-Route, keine neue Command-Gruppe ohne Zeile hier — und keine Familie
mit zwei Heimen.

Verifizierte Kompositions-Fakten (Stand Slice 2, keine Annahmen):
- `capability.yaml`-Nav-Flags: `chat`/`knowledge` sind `nav: true`, `writing`
  (`nav: false` — das Shelf *ist* Home), `prompts`/`settings`/`setup` sind
  `nav: false` (Settings-Cluster bzw. Shell-State, keine Destination).
- Generierte Register (`web/lib/generated/`, Header als Regel): `nav` =
  Home-Navigation; `docks` = eine Zeile pro Capability mit `dockRoutes`, ein
  Tab pro Zeile, gematchte Child-Route ist der Dock-State
  (`NovelPage.tsx:234-242`, Tabs `:570-577`); `commands` = pinned
  `COMMAND_ORDER` (writing, settings, prompts, knowledge) — neue Commands nur
  als Zeilen in existierenden Modulen; `settingsPages` = ein Cluster pro
  `settingsRoutes`.
- `IconRail.tsx`: Home-Konstante (exact, `:118-124`) + `nav`-Zeilen
  (`:125-134`) + Settings-Anker (`:136-144`); 48 px fein / 168 px grob.
- Workbench-Arithmetik (`NovelPage.tsx:588`): Rail 224 + Spalte 592 + Dock
  352 = Container 1200 (F25, eine linke Kante mit Shelf und Top-Bar); Dock
  `w-88` (`:814`), Editor-Karte 576 (`:714`).

Slots: **Nav-Area** (neuer Rail-Eintrag) / **Dock-Tab** (Workspace-Dock,
Child-Route) / **Canvas-Route** (Full-Page-Route) / **Command-only**
(Paletten-Zeile, keine Fläche) / **Settings-Cluster** (Hub-Cluster).

#### 5.7.1 Slot-Tabelle

Bereich **Planen** (neuer Rail-Eintrag, Landing: Timeline — s. Entscheidung
P1). Alle sechs PLAN-Familien teilen ihn, weil sie ein Workflow sind:
Planen vor dem Text, zeit-referenziert.

| Familie (IDs) | Slot | Entscheidung bei Gabel |
|---|---|---|
| Timeline (PLAN-004) | Nav-Area „Planen" (Landing-Canvas) | P1: Timeline statt Storyboard als Landing — die Zeitachse ist das Rückgrat, an dem Szene/Gap/Struktur/Arc hängen; Rest sind Sibling-Canvas unter demselben Eintrag. |
| Storyboard (PLAN-005) | Canvas-Route unter Planen | Dock verworfen — Kartenraster braucht volle Breite, kein 352-Kontext zum Text nötig. |
| Story-Struktur (PLAN-003) | Canvas-Route unter Planen | Wie Storyboard: Akt-/Kapitel-Visualisierung ist räumlich, kein Neben-dem-Text-Lesen. |
| Szenen-Planung (PLAN-001) | Dock-Tab „Planen" (Switcher) | P2: Dock statt Canvas — Szenen-Outline wird *gegen* das Manuskript geschrieben, Editor muss sichtbar bleiben. |
| Gap-Analyse (PLAN-002) | Dock-Tab „Planen" (Switcher) | Canvas verworfen — Befundliste neben dem Text, keine räumliche Fläche. |
| Character-Arc (PLAN-006) | Dock-Tab „Planen" (Switcher) | P3: Dock statt Analysieren-Canvas — Arc wird pro Figur lesend verfolgt, Manuskript daneben; Quervergleich läuft über Command in denselben Tab. |

Bereich **Analysieren** (neuer Rail-Eintrag — Rail-/Routen-Name; Dock-Tab-Label: „Analyse"; Landing: Analysieren-Hub — s. P4).
Alle elf ANAL-Familien teilen ihn, weil sie ein Auslöse-Muster sind:
Command → Bericht, Messung nach dem Text.

| Familie (IDs) | Slot | Entscheidung bei Gabel |
|---|---|---|
| Beta-Reader (ANAL-001) | Nav-Area „Analysieren" (Hub-Landing) | P4: Beta-Reader statt Metrik als Landing — einziger Bericht für Autoren statt Kennzahlen, das menschliche Gesicht des Hubs; Metrik-Berichte hängen darunter. |
| Sentiment (ANAL-002) | Dock-Tab „Analyse" (geteilter Tab, Switcher) | Eigener Tab verworfen — ein Bericht unter vielen, Switcher im Tab (Kapazitätsregel 5.7.2). |
| Readability (ANAL-003) | Dock-Tab „Analyse" (Switcher) | Wie Sentiment: Scores statt Prosa — ein Bericht unter vielen, kein eigener Tab. |
| POV-Analyse (ANAL-004) | Dock-Tab „Analyse" (Switcher) | Wie Sentiment: ein Befundraster (Perspektivbrüche) unter vielen, kein eigener Tab. |
| Koreferenz (ANAL-005) | Dock-Tab „Analyse" (Switcher) | Wie Sentiment: ein Verweis-Check unter vielen, kein eigener Tab. |
| Sensitivity-Review (ANAL-006) | Dock-Tab „Analyse" (Switcher) | Wie Sentiment: ein Prüfbericht (Flaggenliste) unter vielen, kein eigener Tab. |
| Autoren-Stimme (ANAL-007) | Dock-Tab „Analyse" (Switcher) | Wie Sentiment: ein Profil-Vergleich unter vielen, kein eigener Tab. |
| Figuren-Stimme (ANAL-008) | Dock-Tab „Analyse" (Switcher) | Wie Sentiment: ein Profil-Vergleich unter vielen, kein eigener Tab; Figuren-Abgleich gegen Voice-Checker-Dock (Schreiben) ist lesend, nicht doppelt beheimatet. |
| Voice-Drift (ANAL-009) | Dock-Tab „Analyse" (Switcher) | Wie Sentiment: eine Delta-Ansicht unter vielen, kein eigener Tab. |
| Plot-Analyse (ANAL-011) | Dock-Tab „Analyse" (Switcher) | P5: Dock statt Planen-Canvas — Befundliste neben dem Text; Struktur-Canvas (räumlich) bleibt komplementär, kein Doppel-Heim. |
| Literarische Suite (ANAL-010) | Canvas-Route unter Analysieren | P6: Canvas statt geteiltem Dock-Tab — mehrdimensionaler Bericht sprengt 352 px; einziger ANAL-Canvas neben dem Hub. |

Bereich **Schreiben** (Home-Shelf, kein neuer Rail-Eintrag). Hier wohnen
alle Werkzeuge, die *gegen* das Manuskript arbeiten.

| Familie (IDs) | Slot | Entscheidung bei Gabel |
|---|---|---|
| Multi-Draft (WRITE-008) | Dock-Tab „Schreiben" (Switcher) | P7: Dock statt Canvas — gewählt wird gegen den laufenden Text (§5.5: Vergleichs-Sprache wie Diff); „nebeneinander" heißt Editor-Spalte + Dock, max. 3 Varianten im Tab-Stapel. |
| Co-Author (WRITE-006) | Dock-Tab „Schreiben" (Switcher) | Command-only verworfen — laufende Sitzung braucht Fläche. |
| Unblock-Werkzeuge (WRITE-009) | Dock-Tab „Schreiben" (Switcher) | P8: Dock statt Command-only — Übungs-/Impuls-Sitzung braucht Lesefläche neben dem Editor, kein One-Shot. |
| Voice-Checker (WRITE-010) | Dock-Tab „Schreiben" (Switcher) | Analysieren verworfen — Schreib-Feedback, bleibt beim Text (Gegenstück zu ANAL-007..009 dort). |
| Kontext-Inspektor (WRITE-014) | Dock-Tab „Schreiben" (Switcher) | Command-only verworfen — inspizierbare Fläche nötig, kein transienter Treffer. |
| Plot-Check (ASSIST-001) | Dock-Tab „Schreiben" (Switcher) | Command-only verworfen — Befunde brauchen Manuskript daneben. |
| Dialog-Coach (ASSIST-004) | Dock-Tab „Schreiben" (Switcher) | Command-only verworfen — mehrtourig, braucht Sitzung. |
| Recherche (GEN-002) | Dock-Tab „Schreiben" (Switcher) | P9: Dock statt Canvas — Quellen werden neben der Prosa gelesen; Liste passt in 352, kein Graph-Fall. |
| Workflows (WRITE-013) | Command-only | Dock verworfen — Mehrschritt-Läufe sind Command-Sequenzen, Status via `JobStatus` (§5.5), keine persistente Fläche. |
| Inline-Vorschläge (WRITE-007) | Command-only | Fläche ist der Editor selbst (Ghost-Text), kein zweites Heim. |
| Rewrite (WRITE-004) | Command-only | Transienter Eingriff + Diff-Pattern (§5.5), kein Dock. |
| Slash-Commands | Command-only | Per Definition Editor-Aliase auf Paletten-Aktionen (§5.4), kein Menü-Design, keine Fläche. |
| Prompt-History | Command-only | Paletten-Zeile mit Re-Run (§5.4/§5.5); Liste lebt in der Palette, keine Fläche. |
| Titel-Vorschläge (ASSIST-002) | Command-only | One-Shot-Liste + Übernehmen, transient. |
| Namensgenerator (GEN-001) | Command-only | Wie Titel: One-Shot-Liste, Übernehmen fügt ein. |
| Serien (SERIES-001..004) | Canvas-Route unter Schreiben | P10: Canvas statt neuer Nav-Area — bandübergreifende Verwaltung ist Shelf-nah (Home-Nachbar), zu selten für eigenen Rail-Eintrag; Einstieg via Shelf-Card. |
| Schreib-Statistik (STATS-001) | Canvas-Route „Auswertung" unter Schreiben | Dock verworfen — Zeitreihen/Charts brauchen Breite (§5.3 nennt Stats als Canvas). |
| Kosten-Tracking (STATS-002) | Canvas-Route „Auswertung" unter Schreiben (Reiter) | P11: Reiter der Stats-Canvas statt Settings — Kosten werden neben der Leistung gelesen; Keys/Quotas bleiben in Settings, kein Doppel-Heim. |

Bereich **Wissen** (existierender Rail-Eintrag, kein neuer). Identität:
persistente Story-Fakten.

| Familie (IDs) | Slot | Entscheidung bei Gabel |
|---|---|---|
| Knowledge-Graph (KB-008) | Canvas-Route unter Wissen | Dock verworfen — Graph braucht volle Seite (§5.3 nennt Graph als Canvas). |
| Editor-Graph (KB-010) | Dock-Tab „Wissen" (Switcher) | P12: Dock statt zweiter Graph-Canvas — lokale Nachbarschafts-Linse neben der Selektion; KB-008 besitzt den Vollgraphen, Cross-Link „Im Graphen öffnen" verbindet. |
| Worldbuilding (KB-006) | Dock-Tab „Wissen" (Switcher) | Canvas verworfen — geführte Erstellung ist konversationell, nicht räumlich. |
| KB-Merge (KB-009) | Dock-Tab „Wissen" (Switcher) | P13: Dock statt Settings — inhaltliche Paar-Entscheidung neben den Einträgen, keine Konfiguration. |

Bereich **Settings** (existierender Anker, Cluster pro `settingsRoutes`).

| Familie (IDs) | Slot | Entscheidung bei Gabel |
|---|---|---|
| Konsistenz-Regeln (CONS-002) | Settings-Cluster | P14: Settings statt Dock — Regel-CRUD mit Toggles ist Konfiguration; der CONS-001-Checker behält sein existierendes Konsistenz-Dock (Präzedenz, kein neues Heim). |
| Shortcuts (SET-004) | Settings-Cluster | Tastatur-Konfiguration neben den übrigen Clustern, keine eigene Fläche. |
| Prompt-UX (PROMPT-001..003 + Custom-UX) | Settings-Cluster | Bereits beheimatet (`prompts`-Capability: `nav: false`, `settingsPages`-Zeile) — Atlas bestätigt, kein Neubau. |
| Extern-Sync (IO-003) | Settings-Cluster | P15: Settings statt Command-only — Credentials/Zeitpläne sind Konfiguration mit Heim; „Jetzt synchronisieren" ist ein Button auf dieser Cluster-Seite, kein zweiter Slot. |
| Manuskript-Export (IO-001) | Command-only | Canvas verworfen — One-Shot-Job + `JobStatus` + Download, keine persistente Fläche. |
| Import/Corpus-Pass (IO-002, inkl. SETUP-003) | Command-only | Wie Export: Job mit Fortschritt, Einstieg via Shelf-Command, keine Fläche. |

Bereits beheimatet (Präzedenz, keine neuen Zeilen nötig): CONS-001-Checker
(Konsistenz-Dock, §5.3), Free-Form-Chat (CHAT-001, Chat-Dock/Tab),
Proaktive KB-Vorschläge (KB-005) und KB-Verbessern/Extraktion (KB-002..004,
KB-007) als Command-Zeilen bzw. Wissen-Dock-Inhalt, Lern-/Adaptions-Flächen
(LEARN-001/002) als künftige Analysieren-Hub-Reiter nur per Atlas-Amendment.

#### 5.7.2 Kapazitätsregeln (bindend)

- **Rail: max. 7 Destinationen** (Home + 5 Areas + Settings-Anker). Stand:
  Home, Chat, Wissen, Settings = 4; Planen + Analysieren = 6; ein Platz
  Reserve. **Gruppierungsregel:** Areas, nie Features — eine Familie bekommt
  keinen Rail-Eintrag für Größe, Größe löst der Hub-Canvas + geteilter
  Dock-Tab. Volle 7 heißt: konsolidieren (Switcher, Hub-Reiter), nie
  stapeln, nie zweite Rail.
- **Dock: max. 6 Tabs.** Gemessen an der 352-px-Spalte: 36-px-Icon-Buttons
  mit 8-px-Gaps — 6 Tabs = 256 px, Rest ist Gruppen-Label und Luft. Fixe
  Tabs: Chat, Planen (Szene/Gap/Arc-Switcher), Wissen (Graph-Linse/
  Worldbuilding/Merge-Switcher), „Analyse" (Tab-Label; alle ANAL-Berichte außer Suite),
  Schreiben (alle Schreib-Sitzungen). **Overflow:** Der 7. eigenständige
  Dock erzwingt kein Wrapping (zweite Tab-Reihe verboten) und keine 7.
  Spalte, sondern Konsolidierung in einen Switcher — oder ein „Mehr"-Menü
  als letzte Zuflucht, nie als Standard. Neuer Tab nur per Atlas-Amendment.
- **Canvas-Geometrie:** Jede Canvas-Route wiederverwendet die geteilte
  Kante — `mx-auto max-w-[1200px] px-4` (Top-Bar, Shelf, Workbench, F25) —
  und definiert ihr Innenraster selbst (Graph/Timeline besitzen eigene
  Spalten; die 224/592/352-Arithmetik gehört der Workbench, gebunden an
  Prosa-Measure + Dock). **Einstiegspunkte:** Shelf-Cards (Serien,
  Auswertung, Planen-/Analysieren-Hub), Workspace-Toolbar/Dock-Cross-Links
  („Im Graphen öffnen", Analyse-Dock (Tab „Analyse") → Suite-Canvas) und genau eine
  navigierende Command-Zeile pro Canvas (§5.4).
- **Neue Nav-Area: fast nie.** Default ist Dock/Canvas/Command unter
  existierender Area. Eine neue Area verlangt alle drei: ≥3 Canvas-Routen +
  ≥2 Dock-Tabs einer Workflow-Identität UND freie Rail-Bilanz (<7) — und ein
  Atlas-Amendment hier in §5.7. Ohne Amendment kein `nav: true`, kein
  Generator-Umbau (die pinned `COMMAND_ORDER` bleibt unangetastet).

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
