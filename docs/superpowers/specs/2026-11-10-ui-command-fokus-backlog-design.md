# UI-Command-Fokus: Backlog-Design (Atlas-Rest)

Stand: 2026-11-10 · Status: Entwurf für die nächste Planung · Ablage: `docs/superpowers/specs/`

Der Platz-Atlas (`2026-11-06-narrare-ui-command-fokus-design.md`, §5.7) gibt
jeder Feature-Familie genau ein Zuhause. Diese Seite hält fest, was nach dem
Frontend-Rest-Slice noch offen ist: pro Familie, was heute existiert, welcher
Backend-Vertrag fehlt, welche UI-Form bereits entschieden ist, wo der Einstieg
liegt und welche eine Entscheidung die nächste Planung zuerst treffen muss.

Quellen, gegen die jede „Heute vorhanden"-Aussage geprüft ist (keine Annahme):
`app/capabilities/planning/router.py`, `app/capabilities/knowledge/router.py`,
`app/capabilities/writing/router.py`, `app/capabilities/settings/router.py`,
`app/capabilities/chat/router.py`, `app/capabilities/prompts/router.py`,
`web/lib/generated/routes.ts`, `web/lib/generated/docks.ts`,
`app/capabilities/planning/web/routes.tsx`. Endpfade unten nennen nur Routen,
die per `grep` in diesen Dateien verifiziert sind; alles andere steht als
Prosa-Vertrag („es braucht …"), nicht als erfundener Pfad.

## Was bereits gebaut ist (nicht offen, hier nur zur Abgrenzung)

- **Slice Timeline + Storyboard-Substrat (früher):** Timeline-Canvas
  (`/planning`, aus PR #768), Storyboard-Lese-API
  (`GET storyboard`, `PUT …/stage`, `POST …/remap` in
  `planning/router.py`) und Storyboard-Canvas (`/planning/storyboard`).
- **Dieser Slice:** Struktur-Canvas (`/planning/structure`, Proportionen-Balken,
  rein lesend auf der Storyboard-Lese-API) und Nachbarschafts-Linse
  (`NeighborhoodLens.tsx`, auf `GET /entities/{id}/relations` in
  `knowledge/router.py`).
- **Noch früher gebaut (Backend vorhanden, UI vorhanden):** KB-Merge
  (`POST /entities/{entity_id}/merge`, `MergeEntityDialog.tsx`) — unten als
  erledigt vermerkt, keine offene Zeile. Knowledge-Graph-CRUD (Relationen- und
  Entity-Endpunkte in `knowledge/router.py`, `GraphPage.tsx`). Szenen-Speicherung
  (`GET`/`PUT scenes`, `SceneDock.tsx`). Timeline-Event-CRUD
  (`timeline-events`-Endpunkte). Extraktion (`POST /extraction/{novel_id}`),
  Konsistenz-Job + Befunde (`POST /consistency/{novel_id}`,
  `GET …/findings`), Vorschläge (`…/suggestions`, accept/discard). Chat
  (`POST /chat/ask`, Chat-Dock). Prompts-CRUD + Diff (`prompts/router.py`).
  Manuskript-Export (`POST …/export`) und -Import (`POST …/import`) in
  `writing/router.py`. Konsistenz-Dock (`ChecksPanel.tsx`).

## Bereich Planen (Nav-Area „Planen", Landing: Timeline)

| Familie (IDs) | Atlas-Slot (P-Nr.) | Heute vorhanden | Was fehlt (Backend-Vertrag in Prosa) | UI-Form (entschieden) | Einstiegspunkt | Erste Entscheidung der nächsten Planung |
|---|---|---|---|---|---|---|
| Timeline (PLAN-004) | Nav-Area-Landing-Canvas (P1) | Event-CRUD und Timeline-Canvas existieren. | AI-Extraktion (Zeit-Ausdrücke aus Kapiteln lesen, als Events vorschlagen), Charakter-Alter (Geburtsdaten an KB-Entities + Altersrechnung), temporale Konsistenzprüfung. Spec: `docs/features/planning/PLAN-004-timeline.md` und `PLAN-004-architecture.md` (sehen genau dieses Fundament vor). | Canvas bleibt, Befunde landen als Liste daneben; kein zweiter Slot. | Timeline-Canvas (`/planning`). | Extraktions-Vertrag zuerst: Vorschlags-Tabelle (analog KB-Suggestions mit accept/discard) oder direkte Event-Anlage? |
| Storyboard (PLAN-005) | Canvas-Route unter Planen | Lese-API, Stufen-Zuweisung (`PUT …/stage`), Remap mit Vorschau (`POST …/remap`), Canvas existieren. | **Kein Backend nötig — frei planbar:** Drag-&-Drop schreibt auf das existierende `PUT …/stage`; AI-Remap läuft über das existierende `POST …/remap`. Offen ist nur Frontend (DnD-Interaktion, Remap-Bestätigungsdialog). | Kartenraster volle Breite, kein Dock. | Timeline-Landing (einzige Tür zur Sibling-Canvas). | DnD-Semantik: sofort speichern oder Sammel-Bestätigung pro Spalte? |
| Story-Struktur (PLAN-003) | Canvas-Route unter Planen | Struktur-Canvas (Proportionen-Balken, lesend) und Registry (`planning/structures.py`, Default `three-act`) existieren. | **Kein Backend nötig — frei planbar:** weitere Strukturen sind Registry-Einträge (reine Konfiguration, keine Migration). Strukturwechsel läuft über das existierende `POST …/remap`. | Räumliche Akt-/Kapitel-Visualisierung, kein Neben-dem-Text-Lesen. | Storyboard-Canvas (Cross-Link) und Command-Zeile. | Welche Strukturen ins Registry gehören (Fixum vs. benutzerdefiniert)? |
| Szenen-Planung (PLAN-001) | Dock-Tab „Planen" (Switcher, P2) | Szenen-CRUD (`GET`/`PUT scenes`) und `SceneDock.tsx` (Entwurf/Halten/Speichern) existieren. | AI-Entwurf und -Verfeinerung: Endpunkte, die aus Kapitel + KB-Kontext einen Szenen-Breakdown vorschlagen bzw. eine Szene per Anweisung überarbeiten; Entwurf als Vorschlag, Speichern bleibt explizit. Spec: `docs/features/planning/PLAN-001-scene-planning.md` (nennt Dienst-, Vertrags-, Router- und Prompt-Dateien der v1-Planung). | Dock neben dem Editor, Editor bleibt sichtbar. | Planen-Dock am Workspace. | Vorschlags-Ablage: Szenen-Entwürfe als eigene Vorschlags-Tabelle oder als unverbindlicher Entwurf im Dock-State (nichts persistiert bis Speichern)? |
| Gap-Analyse (PLAN-002) | Dock-Tab „Planen" (Switcher) | Nichts (kein Endpunkt, keine Tabelle). | Befund-Lauf: Endpunkt, der fehlende Übergänge, ungelöste Fäden, ungenutzte Entities und Zeitsprünge aus Manuskript + Timeline-Events + KB ableitet, plus Befund-Ablage mit Status (offen/verworfen/behoben). Spec: `docs/features/planning/PLAN-002-gap-analysis.md`. | Befundliste neben dem Text, keine Fläche. | Planen-Dock (Switcher-Eintrag) und Command-Zeile. | Befund-Modell teilen mit CONS-001-Findings oder eigene Tabelle (andere Lebensdauer: Plan vs. Fakt)? |
| Character-Arc (PLAN-006) | Dock-Tab „Planen" (Switcher, P3) | Nichts (kein Endpunkt, keine Tabelle). | Arc-Sitzung: Endpunkt, der aus Start-/Zielzustand + KB-Figur einen mehrphasigen Arc (Phasen, Wendepunkte, Beziehungen, innerer Konflikt) erzeugt, plus Ablage für gespeicherte Arcs pro Figur. Spec: `docs/features/planning/PLAN-006-character-arc.md`. | Dock lesend neben dem Manuskript; Quervergleich per Command in denselben Tab. | Planen-Dock (Switcher-Eintrag). | Arc persistieren (eigene Tabelle pro Figur) oder als Prompt-Sitzung ohne Ablage (jedes Mal neu)? |

## Bereich Analysieren (Nav-Area „Analysieren", Landing: Hub)

Alle elf ANAL-Familien teilen ein Muster (Command → Bericht) und denselben
fehlenden Unterbau: Es existiert **kein** Analyse-Backend — kein Endpunkt, keine
Bericht-Tabelle (verifiziert: kein `analysis`-Capability-Verzeichnis, keine
Analyse-Route in `generated/routes.ts`). Specs: `docs/features/analysis/ANAL-001`
bis `ANAL-011`. Der Vertrag ist pro Familie derselbe: ein Lauf-Endpunkt
(als Job, da LLM-lange Läufe, nach dem Muster `POST /consistency/{novel_id}`
→ 202 + Ergebnis-Abfrage) plus Bericht-Ablage mit Rerun.

| Familie (IDs) | Atlas-Slot (P-Nr.) | Heute vorhanden | Was fehlt (Backend-Vertrag in Prosa) | UI-Form (entschieden) | Einstiegspunkt | Erste Entscheidung der nächsten Planung |
|---|---|---|---|---|---|---|
| Beta-Reader (ANAL-001) | Nav-Area-Hub-Landing (P4) | Nichts. | Bericht-Lauf + Ablage wie oben; Spec: `docs/features/analysis/ANAL-001-beta-reader.md`. | Hub-Landing, menschliches Gesicht des Hubs. | Analysieren-Eintrag (Rail). | Bericht-Format: ein Freitext-Gutachten oder strukturierte Befund-Sektionen (übernehmen/verwerfen pro Punkt)? |
| Sentiment (ANAL-002) | Dock-Tab „Analyse" (Switcher) | Nichts. | Verlaufswerte pro Kapitel/Szene (Tabelle: Zeitreihe) + Lauf-Endpunkt; Spec: `docs/features/analysis/ANAL-002-sentiment.md`. | Ein Bericht unter vielen im Switcher. | Analyse-Dock, Command-Zeile. | Granularität der Ablage: pro Kapitel oder pro Szene? |
| Readability (ANAL-003) | Dock-Tab „Analyse" (Switcher) | Nichts. | Score-Lauf (deterministisch möglich, kein LLM nötig) + Score-Ablage; Spec: `docs/features/analysis/ANAL-003-readability.md`. | Score-Ansicht im Switcher. | Analyse-Dock, Command-Zeile. | **Kein Backend nötig-Prüfung:** Falls rein deterministisch und live berechenbar, entfällt die Ablage — das ist die erste Frage, nicht die Technik. |
| POV-Analyse (ANAL-004) | Dock-Tab „Analyse" (Switcher) | Nichts. | Befundraster Perspektivbrüche (Lauf + Befund-Ablage); Spec: `docs/features/analysis/ANAL-004-pov.md`. | Befundraster im Switcher. | Analyse-Dock, Command-Zeile. | Mit Gap-Analyse (PLAN-002) zusammenlegen oder getrennte Befund-Tabellen? |
| Koreferenz (ANAL-005) | Dock-Tab „Analyse" (Switcher) | Nichts. | Verweis-Check-Lauf + Befunde; Spec: `docs/features/analysis/ANAL-005-coreference.md`. | Ein Check unter vielen. | Analyse-Dock, Command-Zeile. | Deterministisch (Regeln, wie CONS-001) oder LLM-Lauf (Jobs)? |
| Sensitivity-Review (ANAL-006) | Dock-Tab „Analyse" (Switcher) | Nichts. | Flaggenliste (Lauf + Befunde mit Schweregrad); Spec: `docs/features/analysis/ANAL-006-sensitivity.md`. | Flaggenliste im Switcher. | Analyse-Dock, Command-Zeile. | Schweregrad-Modell und ob Flags in CONS-001-Findings wiederverwendet werden. |
| Autoren-Stimme (ANAL-007) | Dock-Tab „Analyse" (Switcher) | Nichts. | Profil-Vergleich (Stimm-Profil-Ablage + Delta-Lauf); Spec: `docs/features/analysis/ANAL-007-voice-author.md`. | Profil-Vergleich im Switcher. | Analyse-Dock, Command-Zeile. | Profil-Modell: wo liegt das Referenz-Profil (Autor-Ebene, Tabelle)? |
| Figuren-Stimme (ANAL-008) | Dock-Tab „Analyse" (Switcher) | Nichts. | Wie ANAL-007, pro Figur; Abgleich gegen Voice-Checker-Dock ist lesend; Spec: `docs/features/analysis/ANAL-008-voice-character.md`. | Profil-Vergleich im Switcher. | Analyse-Dock, Command-Zeile. | Figuren-Profile an KB-Entities hängen oder eigene Profil-Tabelle? |
| Voice-Drift (ANAL-009) | Dock-Tab „Analyse" (Switcher) | Nichts. | Delta-Ansicht über Kapitel (Zeitreihe wie Sentiment); Spec: `docs/features/analysis/ANAL-009-voice-drift.md`. | Delta-Ansicht im Switcher. | Analyse-Dock, Command-Zeile. | Auf ANAL-007/008-Profilen aufbauen (dann erst nach ihnen planbar) oder eigenständig? |
| Plot-Analyse (ANAL-011) | Dock-Tab „Analyse" (Switcher, P5) | Nichts. | Befundliste neben dem Text (Lauf + Befunde); Struktur-Canvas bleibt komplementär; Spec: `docs/features/analysis/ANAL-011-plot-analysis.md`. | Dock, kein Doppel-Heim mit Planen-Canvas. | Analyse-Dock, Command-Zeile. | Abgrenzung zu PLAN-002-Befunden (zwei Listen oder eine mit Quelle)? |
| Literarische Suite (ANAL-010) | Canvas-Route unter Analysieren (P6) | Nichts. | Mehrdimensionaler Bericht (einziger ANAL-Canvas); Spec: `docs/features/analysis/ANAL-010-literary-suite.md`. | Einziger Canvas neben dem Hub (sprengt 352 px). | Analyse-Dock → Cross-Link „Suite öffnen". | Suite als Sammel-Lauf über die Einzel-Berichte (Orchestrierung) oder eigener Lauf mit eigenem Vertrag? |

## Bereich Schreiben (Home-Shelf, kein neuer Rail-Eintrag)

Schreib-Backend heute: Manuskript-CRUD, Kapitel-CRUD + -Reihenfolge,
Fortsetzung (`POST …/continue` als SSE-Lauf) in `writing/router.py`. Es gibt
**keinen** LLM-Endpunkt für Umschreiben, Varianten, Stimme, Recherche, Titel,
Namen oder Sitzungen (verifiziert per `grep` in `writing/router.py` +
`service.py`: nur `continue`). Specs: `docs/features/writing/WRITE-00x`,
`docs/features/ai_assist/ASSIST-00x`, `docs/features/generation/GEN-00x`.

| Familie (IDs) | Atlas-Slot (P-Nr.) | Heute vorhanden | Was fehlt (Backend-Vertrag in Prosa) | UI-Form (entschieden) | Einstiegspunkt | Erste Entscheidung der nächsten Planung |
|---|---|---|---|---|---|---|
| Multi-Draft (WRITE-008) | Dock-Tab „Schreiben" (Switcher, P7) | Nichts. | Varianten-Lauf: aus Passage + Fokus-Vorgabe 2–5 Entwürfe parallel erzeugen, jede mit Fokus-Label und Stärken/Schwächen; Ablage für angenommene/vergleichene Sätze. Spec: `docs/features/writing/WRITE-008-multi-draft.md`. | Vergleich Editor-Spalte + Dock, max. 3 nebeneinander, Toolbar-Sprache wie Diff. | Schreiben-Dock (Switcher). | Varianten persistieren (wiederaufnehmbar) oder transient (nach Entscheidung verworfen)? |
| Co-Author (WRITE-006) | Dock-Tab „Schreiben" (Switcher) | Nichts (nur `continue` als Baustein). | Sitzungs-Modell: mehrtourige Co-Autor-Sitzung mit Verlauf und Übernahme-Contract (Diff/Accept pro Vorschlag). | Laufende Sitzung mit Fläche, kein One-Shot. | Schreiben-Dock (Switcher). | Sitzungs-Verlauf in eigener Tabelle oder als Prompt-Historie-Einträge? |
| Unblock-Werkzeuge (WRITE-009) | Dock-Tab „Schreiben" (Switcher, P8) | Nichts. | Übungs-/Impuls-Sitzung: Anstoß-Läufe (keine Textänderung ohne Übernahme). | Lesefläche neben dem Editor, kein One-Shot. | Schreiben-Dock (Switcher). | Braucht das überhaupt Backend, oder ist es eine Prompt-Bibliothek auf `continue` (dann „kein Backend nötig")? |
| Voice-Checker (WRITE-010) | Dock-Tab „Schreiben" (Switcher) | Nichts. | Schreib-Feedback-Lauf gegen Referenz-Profil (liest ANAL-007/008-Profile, schreibt nichts). | Beim Text, Gegenstück zu ANAL-007..009. | Schreiben-Dock (Switcher). | Erst nach ANAL-007/008-Profilen planbar — Reihenfolge beachten. |
| Kontext-Inspektor (WRITE-014) | Dock-Tab „Schreiben" (Switcher) | Nichts (KB-Suche `POST /search` existiert als Baustein). | Inspektor-Abfrage: was sieht das Modell gerade (Kontext-Fenster, zitierte KB-Fakten) — lesender Endpunkt, keine Generierung. | Inspizierbare Fläche, kein transienter Treffer. | Schreiben-Dock (Switcher). | Format: Roh-Kontext oder kuratierte „verwendete Fakten"-Liste? |
| Plot-Check (ASSIST-001) | Dock-Tab „Schreiben" (Switcher) | Nichts. | Befund-Lauf gegen Manuskript + KB; Spec: `docs/features/ai_assist/ASSIST-001-plot-check.md`. | Befunde brauchen Manuskript daneben. | Schreiben-Dock (Switcher). | Eigene Befunde oder geteilt mit ANAL-011/PLAN-002 (drei Listen sind zwei zu viel)? |
| Dialog-Coach (ASSIST-004) | Dock-Tab „Schreiben" (Switcher) | Nichts. | Mehrtourige Dialog-Sitzung mit Übernahme-Contract; Spec: `docs/features/ai_assist/ASSIST-004-dialogue-coach.md`. | Sitzung, mehrtourig. | Schreiben-Dock (Switcher). | Wie Co-Author-Sitzung: ein Sitzungs-Modell für beide oder je Familie? |
| Recherche (GEN-002) | Dock-Tab „Schreiben" (Switcher, P9) | Nichts (Dokumenten-Upload `POST /documents` existiert als Ablage). | Recherche-Lauf: Quellen-Vorschläge zu Passage/Frage, lesend neben der Prosa; Ablage optional (in Dokumenten wiederfinden). | Liste in 352, kein Graph-Fall. | Schreiben-Dock (Switcher). | Quellen persistieren (Dokumente-Tabelle) oder transient? |
| Workflows (WRITE-013) | Command-only | Jobs-Baustein (`/api/jobs/{job_id}`) existiert. | Mehrschritt-Läufe als Command-Sequenzen mit `JobStatus`; kein neues Backend, nur Orchestrierung pro Workflow. | Keine Fläche, Status via `JobStatus`. | Palette. | Erster Workflow als Muster (welcher?), Rest folgt dem Muster ohne Planung. |
| Inline-Vorschläge (WRITE-007) | Command-only | Nichts (Ghost-Text-Rendering fehlt ebenfalls, ist aber Frontend). | Vorschlag-Lauf: Geistertext für die Cursor-Position aus Manuskript + KB-Kontext (Latenz-kritisch, Streaming). | Fläche ist der Editor selbst. | Editor (automatisch/Shortcut). | Latenz-Budget und Abbruch-Semantik vor dem Vertrag. |
| Rewrite (WRITE-004) | Command-only | Nichts. | Umschreib-Lauf: Passage + Anweisung → Vorschlag mit Diff (Hunk-Accept/Discard, Muster aus §5.5). | Transient + Diff, kein Dock. | Palette / Editor-Selektion. | Vorschlag transient oder als Draft-Variante ablegbar (Brücke zu WRITE-008)? |
| Slash-Commands | Command-only | Mechanik existiert (Palette + `commands.ts`-Register). | **Kein Backend nötig — frei planbar** für die Alias-Mechanik selbst; jede Ziel-Aktion braucht ihren eigenen Familien-Vertrag (s. oben). | Editor-Aliase auf Paletten-Aktionen, kein Menü. | Editor (`/`). | Alias-Katalog: welche Aktionen bekommen Aliase (alle oder kuratiert)? |
| Prompt-History | Command-only | Jobs-API existiert; Prompts-CRUD + Diff existieren. | Lauf-Historie pro Prompt (welcher Lauf, welche Eingabe, Re-Run): Ablage + Abfrage, Jobs-Tabelle als Baustein. | Liste in der Palette, keine Fläche. | Palette (Re-Run-Zeile). | Historie als eigene Tabelle oder fester Bestandteil der Jobs-Ablage? |
| Titel-Vorschläge (ASSIST-002) | Command-only | Nichts. | One-Shot-Liste + Übernehmen (kleinster LLM-Vertrag: Eingabe Manuskript-Kontext, Ausgabe N Titel). | Transient, Übernehmen fügt ein. | Palette. | Muster-Vertrag für alle One-Shot-Listen (Titel, Namen): einmal definieren, zweimal verwenden. |
| Namensgenerator (GEN-001) | Command-only | Nichts. | Wie Titel: One-Shot-Liste + Übernehmen. | Transient. | Palette. | Siehe Titel (gemeinsamer Vertrag). |
| Serien (SERIES-001..004) | Canvas-Route unter Schreiben (P10) | Nichts (kein Serien-Modell, keine bandübergreifenden Endpunkte). | Serien-Vertrag: Band-Verwaltung (Anlage/Reihenfolge), Generierungs-Kontext über Bände, Stimm-Hierarchie, bandübergreifender Drift. Specs: `docs/features/series/SERIES-001` bis `-004`. | Shelf-nahe Canvas, kein Rail-Eintrag. | Shelf-Card. | Serien-Modell zuerst (Bände als Novel-Gruppe): ohne das ist kein Untervertrag baubar. |
| Schreib-Statistik (STATS-001) | Canvas-Route „Auswertung" unter Schreiben | Nichts. | Zeitreihen aus vorhandenen Daten (Wortzahlen, Sitzungen): Aggregations-Abfrage, keine neue Schreib-Tabelle nötig, nur Lese-Endpunkt. Spec: `docs/features/analytics/STATS-001-writing-stats.md`. | Charts brauchen Breite, kein Dock. | Shelf-Card. | Welche Kennzahlen v1 (Worte/Zeit genügt als Anfang)? |
| Kosten-Tracking (STATS-002) | Canvas-Route „Auswertung" (Reiter, P11) | Modell-/Provider-Verwaltung existiert (`settings`-Router). | Verbrauchs-Protokoll pro Lauf (Tokens/Kosten) + Abfrage für den Reiter; Keys/Quotas bleiben in Settings. Spec: `docs/features/analytics/STATS-002-cost-tracking.md`. | Reiter der Stats-Canvas, kein Doppel-Heim. | Auswertung-Canvas. | Protokoll-Pflicht: jeder LLM-Lauf schreibt einen Verbrauchs-Satz (Querschnitt über alle Familien). |

## Bereich Wissen (existierender Rail-Eintrag)

| Familie (IDs) | Atlas-Slot (P-Nr.) | Heute vorhanden | Was fehlt (Backend-Vertrag in Prosa) | UI-Form (entschieden) | Einstiegspunkt | Erste Entscheidung der nächsten Planung |
|---|---|---|---|---|---|---|
| Knowledge-Graph (KB-008) | Canvas-Route unter Wissen | Vollgraph-Canvas (`GraphPage.tsx`) + Graph-CRUD (Entities, Relationen, Vorschläge, Extraktion) existieren. | Nur Frontend-Rest: Pan/Zoom und große Graphen (Layout/Clustern) — **kein Backend nötig, frei planbar**. Querschnitt-Notiz: hybride KB-Referenzen (Vektor + Stichwort) als Retrieval-Verbesserung betreffen `POST /search`, sind aber ein späterer Vertrags-Zusatz, kein Blocker. | Volle Seite, kein Dock. | Wissen-Eintrag (Rail). | Darstellungs-Budget: ab welcher Knotenzahl wird geclustert (verbindliche Zahl)? |
| Editor-Graph (KB-010) | Dock-Tab „Wissen" (Switcher, P12) | Nachbarschafts-Linse (`NeighborhoodLens.tsx`) auf `GET /entities/{id}/relations` — dieser Slice. | Erledigt bis auf Feinschliff; Cross-Link „Im Graphen öffnen" existiert als Entscheidung, Umsetzung prüfen. | Lokale Linse neben der Selektion. | Wissen-Dock. | Keine — als gebaut abnehmen, Rest als normale Bugs. |
| Worldbuilding (KB-006) | Dock-Tab „Wissen" (Switcher) | Entity-CRUD existiert als Ablage-Baustein; keine geführte Erstellung. | Geführte Erstellungs-Sitzung: Fragen → Entity-Entwürfe → Übernahme in Entity-Tabelle (Baustein `POST`-Entity-Endpunkte vorhanden). | Konversationell, nicht räumlich. | Wissen-Dock (Switcher). | Fragenkatalog als Prompt-Bibliothek (dann „kein Backend nötig") oder eigene Sitzungs-Ablage? |
| KB-Merge (KB-009) | Dock-Tab „Wissen" (Switcher, P13) | **Gebaut:** `POST /entities/{entity_id}/merge` + `MergeEntityDialog.tsx`. | Nichts offen. | Paar-Entscheidung neben den Einträgen. | Wissen-Dock. | Keine — erledigt, kein Planungsgegenstand. |

## Bereich Settings (existierender Anker, Cluster pro `settingsRoutes`)

| Familie (IDs) | Atlas-Slot (P-Nr.) | Heute vorhanden | Was fehlt (Backend-Vertrag in Prosa) | UI-Form (entschieden) | Einstiegspunkt | Erste Entscheidung der nächsten Planung |
|---|---|---|---|---|---|---|
| Konsistenz-Regeln (CONS-002) | Settings-Cluster (P14) | Regel-Checker (CONS-001: Job + Befunde + Dock) existiert; Regeln selbst nicht (kein Regel-Endpunkt in `knowledge/router.py`). | Regel-CRUD: Regel-Tabelle (Muster, Schwere, an/aus) + Einbindung in den Checker-Lauf. Spec: `docs/features/consistency/CONS-002-rules.md`. | Regel-CRUD mit Toggles ist Konfiguration. | Settings-Hub (eigener Cluster). | Regel-Sprache: Freitext-Muster oder strukturierte Bedingungen (legt Tabellen-Schema fest)? |
| Shortcuts (SET-004) | Settings-Cluster | Tastaturführung der Palette existiert; keine Shortcut-Verwaltung. | **Kein Backend nötig — frei planbar:** UI-gesteuerte Verwaltung, Ablage in lokalen Einstellungen (so sieht es die Spec vor: `docs/features/settings/SET-004-shortcuts.md`). | Konfiguration neben den übrigen Clustern. | Settings-Hub (eigener Cluster). | Kanonische Aktions-Liste (welche Aktionen bekommen IDs)? |
| Prompt-UX (PROMPT-001..003 + Custom-UX) | Settings-Cluster | Beheimatet: Prompts-CRUD + Diff (`prompts`-Capability, `settingsPages`-Zeile). | Nichts Grundsätzliches; Custom-UX-Anteile (eigene Variablen, Vorschau) als Erweiterung des bestehenden Vertrags. | Kein Neubau, Atlas bestätigt. | Settings-Hub (Prompts-Cluster). | Welche Custom-UX-Anteile in v1 (Variablen zuerst)? |
| Extern-Sync (IO-003) | Settings-Cluster (P15) | Nichts. | Sync-Vertrag: Ziel-Konfiguration (Credentials/Zeitpläne, Cluster-Seite) + „Jetzt synchronisieren"-Lauf als Job mit Fortschritt. Spec: `docs/features/io/IO-003-sync.md`. | Konfiguration mit Heim; Sync-Button auf der Cluster-Seite. | Settings-Hub (eigener Cluster). | Erstes Sync-Ziel (ein Anbieter als Muster)? |
| Manuskript-Export (IO-001) | Command-only | **Backend vorhanden:** `POST …/export` in `writing/router.py`. | **Kein Backend nötig — frei planbar:** One-Shot-Job + `JobStatus` + Download als Paletten-Aktion. Spec: `docs/features/io/IO-001-export.md`. | Keine Fläche. | Palette. | Export-Formate v1 (welche Formate, welche Optionen)? |
| Import/Corpus-Pass (IO-002, inkl. SETUP-003) | Command-only | **Backend vorhanden:** `POST …/import` in `writing/router.py`. | **Kein Backend nötig — frei planbar:** Job mit Fortschritt, Einstieg via Shelf-Command. Spec: `docs/features/io/IO-002-import.md`. | Keine Fläche. | Shelf-Command. | Corpus-Pass-Umfang (nur Text oder auch KB-Extraktion im selben Lauf)? |

Bereits beheimatet, keine offenen Zeilen (Präzedenz aus Atlas §5.7):
CONS-001-Checker (Konsistenz-Dock), Free-Form-Chat (CHAT-001, Chat-Dock),
KB-005-Vorschläge und KB-002..004-/KB-007-Verbessern/Extraktion (Command-Zeilen
bzw. Wissen-Dock), Lern-Flächen (LEARN-001/002, nur per Atlas-Amendment).

Querschnitt-Deferrals aus dem Task-3-Brief, wo sie oben wohnen: hybride
KB-Referenzen → KB-008-Zeile; Szenen-AI → PLAN-001; Storyboard-DnD/AI-Remap/
Extra-Strukturen → PLAN-005/PLAN-003 (Backend vorhanden); Timeline-AI/Alter/
Konsistenz → PLAN-004; Graph-Pan/Zoom → KB-008 (Frontend); Stats/Kosten →
STATS-001/002; Serien → SERIES-Zeile; Shortcuts → SET-004 (Frontend);
Konsistenz-Regeln → CONS-002; Extern-Sync → IO-003; Worldbuilding → KB-006;
Multi-Draft/Co-Author/Unblock/Voice/Kontext/Plot-Check/Dialog-Coach/Recherche →
ihre Schreiben-Zeilen; Command-only-mit-LLM (Rewrite, Titel, Namen,
Inline, Workflows, Prompt-History) → ihre Command-Zeilen.

## Reihenfolge-Empfehlung

Drei Gegenstände schalten die meisten Atlas-Zeilen frei — in dieser Reihenfolge:

1. **Einheitlicher LLM-Lauf-Vertrag (Jobs + Befund-/Bericht-Ablage + Verbrauchs-Satz).**
   Warum: Alle elf ANAL-Berichte, Gap-Analyse, Plot-Check, Voice-Familien und
   die One-Shot-Listen (Titel, Namen, Rewrite) brauchen dieselbe Form —
   Lauf-als-Job, Ergebnis-Ablage mit Status, Re-Run aus der Prompt-Historie,
   ein Verbrauchs-Satz pro Lauf für STATS-002. Ein Muster statt elf Verträge;
   Readability (ANAL-003) und Koreferenz (ANAL-005) klären dabei nebenbei, ob
   sie das Muster überhaupt brauchen (deterministisch → keine Ablage).
   Schaltet direkt frei: ANAL-001..011, PLAN-002, ASSIST-001, STATS-002,
   Prompt-History-Re-Run.

2. **Stimm-Profil-Modell (ANAL-007/008) vor den Verbrauchern.**
   Warum: Autoren-Stimme, Figuren-Stimme und Voice-Drift teilen ein
   Profil-Schema; Voice-Checker (WRITE-010) und Figuren-Stimme lesen dasselbe
   Modell. Profil-Schema zuerst festlegen (wo liegt das Referenz-Profil, hängt
   das Figuren-Profil an der KB-Entity?), dann sind vier Zeilen reine
   Lauf-Varianten nach Muster 1. Schaltet frei: ANAL-007/008/009, WRITE-010.

3. **Serien-Modell (SERIES-001) vor Serien-UI.**
   Warum: Die Serien-Canvas ist die einzige offene Canvas-Route mit neuem
   Datenmodell (Band-Gruppe über Novels). Ohne das Gruppen-Modell ist kein
   Untervertrag (Generierungs-Kontext, Stimm-Hierarchie, Drift) baubar; mit ihm
   ist die Canvas lesende Aggregation vorhandener Bausteine. Schaltet frei:
   SERIES-001..004 und die Serien-Canvas als Einstieg.

Danach sind die „kein Backend nötig"-Zeilen (Export-/Import-Commands,
Storyboard-DnD, Shortcuts, Graph-Pan/Zoom, Extra-Strukturen, Slash-Aliase)
freie Frontend-Planung ohne Backend-Abhängigkeit — sie können parallel laufen,
sobald Kapazität da ist, und brauchen keine weitere Backend-Planung.
