<!-- Context: narrare-dev/processes/graph-fallback-process | Priority: high | Source: code-review-graph + codebase-memory-mcp behaviour + graph-exploration.md | Updated: 2026-06-30 -->

# Graph-Stabilität: Strategie & Fallback-Prozess

> **Ziel**: Wenn Graph-Tools (`code-review-graph`, `codebase-memory-mcp`) nicht
> verfügbar sind, müssen alle Specialists und der Coordinator einen dokumentierten,
> schrittweisen Fallback-Prozess haben — ohne Spekulation, ohne Workarounds, ohne
> Zeitverlust.
>
> **Primary Standard**: `graph-exploration.md` — dieses Dokument ist der Backup-Prozess.
> Der Graph ist immer der erste Weg. Fallback ist der zweite.

---

## 1. Root Cause Analysis

### 1.1 Warum passiert "not connected"?

Das Projekt hat **zwei** Graph-Systeme: `code-review-graph` und `codebase-memory-mcp`.
Jedes hat seine eigene Verfügbarkeitscharakteristik:

**code-review-graph** — ein **externer MCP Sidecar-Prozess**,
definiert in `opencode.json`:

```json
"code-review-graph": {
  "type": "local",
  "command": ["/path/to/code-review-graph", "serve"],
  "timeout": 120000
}
```

**Lebenszyklus:**
1. Die IDE (opencode) startet den `code-review-graph serve` Prozess beim
   Öffnen einer Session.
2. Der Server öffnet eine **SQLite In-Memory Connection** zur Datei
   `.code-review-graph/graph.db` (SQLite WAL-Modus: `.db-shm`, `.db-wal`).
3. Solange der Server läuft, antworten alle MCP-Tools.
4. **Zwischen Sessions** (IDE schließen/öffnen, MCP-Server-Crash, Hibernation):
   Der Server-Prozess wird beendet → die SQLite-Connection ist verloren.
5. Beim nächsten Aufruf eines graph-Tools kommt: `MCP error -32001: Request timed out`
   oder `not connected`.

**Das ist kein Bug.** Der MCP-Server hat keinen Auto-Restart-Mechanismus.
Das ist normales MCP-Verhalten — eine Betriebstatsache.

**codebase-memory-mcp** — ein zweites Graph-System, das **unabhängig** von
code-review-graph läuft. Seine Verfügbarkeit kann sich unterscheiden:

- Eines der beiden Systeme kann verfügbar sein, während das andere ausfällt.
- **Konsequenz**: Bevor Read/Glob/Grep-Fallback aktiviert wird, MUSS das
  jeweils andere Graph-System als Alternative geprüft werden (siehe §3).
- Die Tool Selection Matrix in `graph-exploration.md` §2 zeigt,
  welche Tools in welchem System verfügbar sind.

### 1.2 Was ist betroffen?

| Komponente | Status | Details |
|------------|--------|---------|
| `graph.db` auf Disk | ✅ Persistent | Daten bleiben erhalten |
| SQLite Connection | ❌ Flüchtig | Stirbt mit dem Server-Prozess |
| MCP Tools | ❌ Nicht erreichbar | Zeitüberschreitung beim Aufruf |
| Graph-Daten | ✅ Erhaltbar | `build_or_update_graph_tool` mit `full_rebuild=False` (inkrementell) |

### 1.3 Was NICHT hilft

- **Neustart des Tools im selben Aufruf**: Ein wiederholter Aufruf schlägt
  erneut fehl — der Server läuft nicht.
- **Manuelles Editieren von `graph.db`**: Die Datenbank wird exklusiv durch
  den code-review-graph Server verwaltet.
- **`graph.db` löschen**: Datenverlust ohne Nutzen — der Server muss trotzdem
  neugestartet werden.

---

## 2. Prevention Strategy

### 2.1 Session-Opening Checklist (Stage 1)

Bei **Session-Beginn** führt der Coordinator automatisch aus:

```
1. code-review-graph_build_or_update_graph_tool
   → Parameter: full_rebuild=False (inkrementell)
   → Timeout: 120s (wie in opencode.json konfiguriert)
2. Bei Erfolg → Graph ist warm, Session kann beginnen
3. Bei "not connected" oder Timeout → Fallback-Prozess (siehe §3)
```

Dieser Schritt wird in `navigation.md` als Teil von **Stage 1 (SessionOpening)**
verankert. Er ist der erste Tool-Aufruf nach dem Laden der Context-Files.

### 2.2 Auto-Recovery

Wenn ein graph-Tool während der Session mit "not connected" fehlschlägt:

```
Schritt 1: Einmal wiederholen
→ code-review-graph_build_or_update_graph_tool (inkrementell)
→ Timeout: 120s

Schritt 2: Bei Erfolg → normal weitermachen
Schritt 3: Bei Fehler → Fallback-Prozess (§3)
```

**Warum inkrementell statt full rebuild:**
- Inkrementell (`full_rebuild=False`): Nur geänderte Dateien neu parsen
  → typischerweise < 30s bei normalen Changesets
- Full rebuild (`full_rebuild=True`): Alle Dateien neu parsen
  → typischerweise 2-5 Minuten (188 MB `graph.db`-Datei)
- **Faustregel**: Inkrementell nach jedem Session-Start. Full rebuild nur bei
  Staleness-Verdacht (z.B. nach Branch-Wechsel, nach grossem Rebase,
  nach Pull mit vielen Änderungen).

### 2.3 Wann Full Rebuild vs. Incremental

| Situation | Empfohlen | Begründung |
|-----------|-----------|------------|
| Session-Beginn | Incremental | Normaler Betrieb |
| Nach `git pull` | Incremental | Meist wenige geänderte Dateien |
| Nach Branch-Wechsel | Incremental | Graph passt sich an neuen HEAD an |
| Nach Rebase/Merge mit Konflikten | **Full Rebuild** | Graph könnte inkonsistent sein |
| Nach "not connected" Recovery | Incremental | Zuerst Verbindung wiederherstellen |
| Staleness-Verdacht (alte Ergebnisse) | **Full Rebuild** | Graph-Daten könnten veraltet sein |
| Wöchentliche Wartung | **Full Rebuild** | Präventive Konsolidierung |

### 2.4 Fehlgeschlagene Rebuilds erkennen

Der graph-Tool-Aufruf gibt eine Exception zurück. Typische Muster:

```
MCP error -32001: Request timed out
→ Server läuft nicht → Fallback (§3)

MCP error -32603: Internal error
→ Server läuft, aber DB ist korrupt → Full rebuild versuchen
→ Falls auch das fehlschlägt → Fallback (§3) + Issue tracken
```

---

## 3. Fallback Process

### 3.1 Entscheidungsbaum

```
graph-Tool-Aufruf fehlschlägt?
├─→ Einmal wiederholen (build_or_update_graph_tool incremental)
│   ├─→ Erfolg → Normalbetrieb
│   └─→ Fehlschlag → Anderes Graph-System prüfen
│
└─→ Anderes Graph-System verfügbar? (siehe Matrix §3.2a)
    ├─→ Ja → Ersatz-Tool aus Matrix nutzen
    │   └─→ Auch ausgefallen? → Fallback aktivieren (§3.2)
    │
    └─→ Nein → Fallback aktivieren (§3.2)

Fallback-Zähler: 2 consecutive Failures?
├─→ Ja → Fallback-Prozess starten (§3.2)
└─→ Nein → Ersten Fehler als transient behandeln, später nochmal versuchen
```

**Abbruchkriterium**: Wenn 2 aufeinanderfolgende graph-Tool-Aufrufe fehlschlagen
(egal welche Tools), wird der Fallback-Prozess aktiviert.

**Wichtig**: Der Fallback zu Read/Glob/Grep wird erst aktiviert, wenn BEIDE
Graph-Systeme (code-review-graph UND codebase-memory-mcp) nicht verfügbar sind.
Das jeweils andere System ist immer der erste Fallback-Schritt.

### 3.2 Graph-Tool → Fallback Mapping

| Graph Tool (code-review-graph) | codebase-memory-mcp Alternativ-Tool | Read/Glob/Grep Alternative | Genauigkeit | Performance |
|-------------------------------|-------------------------------------|---------------------------|-------------|-------------|
| `semantic_search_nodes_tool` | `search_graph` (BM25 + semantic_query) | `grep` + `glob` — Funktions-/Klassennamen suchen | Mittel — findet nur exakte Textmatches, keine Semantik | Langsamer bei grossen Codebasen |
| `query_graph_tool callers_of` | `trace_path` (inbound, risk_labels) | `grep` für Funktionsreferenzen — `rg "function_name" --include '*.py'` | Hoch — findet alle Textreferenzen | Manuelle Deduplikation nötig |
| `query_graph_tool callees_of` | `trace_path` (outbound, depth) | Quelltext-Lesen — `read` der Datei + manuelles Tracing | Niedrig — hängt vom Leser ab | Zeitaufwändig |
| `query_graph_tool imports_of` | `query_graph` (Cypher) | `read` der Datei + manuelle Prüfung der Import-Blöcke | Hoch — aber kein automatisches Transitives | Direkt |
| `query_graph_tool importers_of` | `search_graph` (file_pattern) | `grep` für Modul-Importe — `rg "from module"` | Mittel — erfasst nur direkte Imports | Erfordert mehrere Grep-Durchläufe |
| `query_graph_tool tests_for` | `search_graph` + label=Test | `glob` nach Testdateien — `glob tests/**/test_*` + `grep` | Hoch — wenn Tests benannt sind | Meist ausreichend |
| `query_graph_tool children_of` | `get_architecture` (clusters) | `read` der Datei + Verzeichnisstruktur (`ls`) | Hoch — für einzelne Dateien | Manuelle Analyse |
| `get_impact_radius_tool` ⭐ | — (kein Equivalent) | **Manuelles Tracing**: Änderungsdateien lesen, dann `grep` callees | Niedrig — fehleranfällig | Sehr zeitaufwändig |
| `get_architecture_overview_tool` | `get_architecture` (Leiden communities) | `docs/reference/directory-structure.md` + `module-map.md` | Mittel — statische Doku | Sofort verfügbar |
| `detect_changes_tool` | `detect_changes` (basic) | `git diff HEAD~1` + `git log --oneline -10` | Hoch — präzise, aber ohne Risiko-Scoring | Manuelle Analyse |
| `get_affected_flows_tool` ⭐ | — (kein Equivalent) | Manuelle Code-Verfolgung — `grep` + `read` der Call-Chain | Niedrig — kein automatisches Flow-Tracing | Sehr zeitaufwändig |
| `get_minimal_context_tool` ⭐ | — (kein Equivalent) | `read` der relevanten Dateien + `git log` | Mittel — kein strukturierter Kontext | Manuelle Synthese |
| `get_hub_nodes_tool` ⭐ | — (kein Equivalent) | Expertise-basiert — bekannte Hotspots aus `module-map.md` | Niedrig — veraltet schnell | Kein automatisierter Check |
| `get_bridge_nodes_tool` ⭐ | — (kein Equivalent) | Nicht ersetzbar — Bridge-Analyse ist rein graph-basiert | ❌ Nicht verfügbar | Akzeptieren |
| `refactor_tool (rename)` ⭐ | — (kein Equivalent) | `grep` + `sed` — manuelles Find-and-Replace | Niedrig — kein sicherer Preview | Riskant ohne Graph |
| `refactor_tool (dead_code)` ⭐ | — (kein Equivalent) | Manuelle Code-Inspektion — `grep` nach ungenutzten Funktionen | Niedrig — falsch-positive | Zeitaufwändig |
| `find_large_functions_tool` ⭐ | — (kein Equivalent) | `wc -l` auf Dateien + manuelle Durchsicht | Niedrig — nur auf Datei-Ebene | Manuell |
| `get_knowledge_gaps_tool` ⭐ | — (kein Equivalent) | Nicht ersetzbar — Graph-Analyse | ❌ Nicht verfügbar | Akzeptieren |
| `get_surprising_connections_tool` ⭐ | — (kein Equivalent) | Nicht ersetzbar — Graph-Analyse | ❌ Nicht verfügbar | Akzeptieren |
| `traverse_graph_tool` | `trace_path` (BFS/DFS limited) | Nicht ersetzbar — Graph-Traversal | ❌ Nicht verfügbar | Akzeptieren |
| `list_graph_stats_tool` | `index_status` | `ls -lh .code-review-graph/graph.db` — Dateigrösse prüfen | Mittel — nur Metadaten | Trivial |

⭐ = code-review-graph unique tool (kein Equivalent in codebase-memory-mcp)

> **Hinweis**: Tools, die in **beiden** Systemen existieren, sind im Fallback
> unkritisch — das jeweils andere System übernimmt. Nur bei ⭐-Tools ist der
> Fallback auf Read/Glob/Grep oder Akzeptanz angewiesen.

### 3.3 Severity Classification

| Severity | Definition | Verhalten |
|----------|------------|-----------|
| **Must-fix** | Graph-Tool-Ausfall blockiert den aktuellen Task | **Fallback sofort aktivieren** — die Alternative ist implementierbar, aber mit geringerer Effizienz. Task kann trotzdem abgeschlossen werden. |
| **Should-track** | Graph-Tool-Ausfall reduziert Effizienz, blockiert aber nichts | **Fallback aktivieren, später tracken** — Task läuft mit manuellen Alternativen. Ein Issue sollte erstellt werden, wenn das Muster sich wiederholt. |
| **Accept** | Graph-Tool ist nicht durch manuelle Methoden ersetzbar | **Task ohne das Tool fortsetzen** — die Analyse muss übersprungen oder mit reduzierter Qualität akzeptiert werden. |

**Severity pro Tool im Fallback (beide Systeme ausgefallen):**

> **Hinweis**: Die Severity gilt NUR, wenn BEIDE Graph-Systeme ausgefallen sind.
> Ist nur ein System ausgefallen, wird das andere als Ersatz genutzt — Severity
> ist dann immer "kein Fallback nötig" (siehe §3.2a für Äquivalente).

| Graph Tool (code-review-graph) | Fallback Severity | codebase-memory Equivalent? | Begründung |
|--------------------------------|-------------------|----------------------------|------------|
| `semantic_search_nodes_tool` | Must-fix | ✅ `search_graph` | `grep`/`glob` sind akzeptable Alternativen, aber weniger effizient |
| `query_graph_tool callers_of` | Must-fix | ✅ `trace_path` | `grep`-basierte Suche ist machbar |
| `query_graph_tool callees_of` | Should-track | ✅ `trace_path` | Manuelles Tracing ist machbar, aber zeitaufwändig |
| `query_graph_tool imports_of` | Must-fix | ✅ `query_graph` (Cypher) | Direkt via `read` machbar |
| `query_graph_tool importers_of` | Should-track | ✅ `search_graph` | `grep`-Suche erfordert mehrere Durchläufe |
| `query_graph_tool tests_for` | Must-fix | ✅ `search_graph` + label | Glob-Patterns liefern zuverlässige Ergebnisse |
| `query_graph_tool children_of` | Must-fix | ✅ `get_architecture` | Direkt via `read` machbar |
| `get_impact_radius_tool` ⭐ | **Unique** — Should-track | ❌ Kein Equivalent | Manuelles Tracing ist fehleranfällig und zeitaufwändig |
| `get_architecture_overview_tool` | Must-fix | ✅ `get_architecture` | Statische Doku ist sofort verfügbar |
| `detect_changes_tool` | Must-fix | ✅ `detect_changes` | `git diff` + `git log` sind machbar |
| `get_affected_flows_tool` ⭐ | **Unique** — Should-track | ❌ Kein Equivalent | Manuelle Code-Verfolgung ist möglich aber ineffizient |
| `get_minimal_context_tool` ⭐ | **Unique** — Should-track | ❌ Kein Equivalent | Manuelle Synthese mehrerer Quellen nötig |
| `get_hub_nodes_tool` ⭐ | **Unique** — Accept | ❌ Kein Equivalent | Expertise-basiert, keine gute manuelle Alternative |
| `get_bridge_nodes_tool` ⭐ | **Unique** — Accept | ❌ Kein Equivalent | Nicht manuell ersetzbar |
| `refactor_tool (rename)` ⭐ | **Unique** — Must-fix | ❌ Kein Equivalent | `grep` + manuelle Edits sind machbar (aber riskant) |
| `refactor_tool (dead_code)` ⭐ | **Unique** — Should-track | ❌ Kein Equivalent | Manuelle Inspektion ist aufwändig |
| `find_large_functions_tool` ⭐ | **Unique** — Must-fix | ❌ Kein Equivalent | `wc -l` auf Dateiebene machbar |
| `get_knowledge_gaps_tool` ⭐ | **Unique** — Accept | ❌ Kein Equivalent | Nicht manuell ersetzbar |
| `get_surprising_connections_tool` ⭐ | **Unique** — Accept | ❌ Kein Equivalent | Nicht manuell ersetzbar |
| `traverse_graph_tool` | Accept | ✅ `trace_path` (limitiert) | Nicht manuell ersetzbar |

### 3.4 Fallback Workflow (Schritt für Schritt)

Wenn der Fallback aktiviert wird:

```
1. FALLBACK AKTIVIERT (nach 2 consecutive Failures im selben System)
   ↓
2. Anderes Graph-System verfügbar? (Matrix in §3.2 prüfen)
   ├─→ Ja → Ersatz-Tool aus der codebase-memory-mcp-Spalte nutzen
   │   → Task kann normal fortgesetzt werden (kein Read/Glob/Grep nötig)
   │
   └─→ Nein → BEIDE Systeme ausgefallen → Weiter mit Schritt 3
   ↓
3. BEIDE Graph-Systeme ausgefallen. Welches Tool wird benötigt?
   ├─→ Tool hat codebase-memory-mcp Equivalent?
   │   → ⚠️ Wurde in Schritt 2 bereits geprüft. Hier liegt ein logischer Fehler vor.
   │   → Beide Systeme wirklich down? Dann zur Severity-Einschätzung.
   │
   ├─→ Severity = Must-fix (oder Unique + Must-fix)
   │   → Dokumentierte Read/Glob/Grep-Alternative aus §3.2 ausführen
   │   → Task kann normal fortgesetzt werden
   │
   ├─→ Severity = Should-track (oder Unique + Should-track)
   │   → Alternative aus §3.2 ausführen
   │   → Task läuft, aber mit reduzierter Effizienz rechnen
   │   → Nach Task-Abschluss: Issue erfassen
   │
   └─→ Severity = Accept (oder Unique + Accept)
       → Task ohne diese Analyse fortsetzen
       → Im Handoff dokumentieren: "Graph-Tool X war nicht verfügbar"
       → Nach Task-Abschluss: Issue erfassen
   ↓
4. Graph bleibt deaktiviert für den Rest der Session
   → Nicht jede Tool-Anfrage einzeln prüfen
   → Nur bei Session-Neustart oder explizitem Rebuild-Versuch wieder aktivieren
```

### 3.5 Dokumentation im Handoff

Wenn der Fallback verwendet wurde, muss der Coordinator im Handoff
vermerken:

```
## Graph Fallback Active
- Auslöser: [z.B. "build_or_update_graph_tool timed out at session start"]
- Ausgefallenes System: [code-review-graph | codebase-memory-mcp | beide]
- Betroffene Tools: [Liste der Tools, die nicht genutzt werden konnten]
- Ersatzmethoden: [Liste der verwendeten Fallback-Alternativen + genutztes Alternativ-Graph-System]
- Offene Risiken: [z.B. "Impact Analysis wurde manuell durchgeführt — könnte Übersehenes enthalten"]
```

---

## 4. Integration mit Coordinator Workflow (Stage 3: Discover)

### 4.1 Wo der Fallback-Prozess im Workflow sitzt

Der `feature-pipeline.md` definiert Stage 3 (Spec → Implementation) als die
Discover-Phase. Der Graph-Fallback ist kein Stage-Wechsel — er ist ein
**operationaler Sub-Prozess**, der in jeder Stage greifen kann, in der
graph-Tools verwendet werden.

### 4.2 Integration in die Stage-Struktur

| Stage | Graph-Tools typischerweise genutzt | Fallback-Verhalten |
|-------|-----------------------------------|-------------------|
| **Stage 1** (Session Opening) | `build_or_update_graph_tool` (Prevention) | Fallback → Session startet ohne Graph. Alle nachfolgenden Stages nutzen Read/Glob/Grep. |
| **Stage 2** (Architecture → Specification) | `get_architecture_overview_tool`, `query_graph_tool` | Fallback → Architecture Spec nutzt `directory-structure.md` + `module-map.md` + manuelles Lesen |
| **Stage 2.5** (Semantic Review) | `query_graph_tool` (callers_of/imports_of) | Fallback → manuelle Import-Prüfung via `grep` |
| **Stage 3** (Implementation) | `query_graph_tool`, `semantic_search_nodes_tool` | Fallback → `grep` + `glob` für Code-Suche |
| **Stage 4** (Validation) | `detect_changes_tool`, `get_impact_radius_tool` | Fallback → `git diff` + manuelle Impact-Analyse |
| **Stage 6** (Commit Review) | `detect_changes_tool` | Fallback → `git diff` + manuelle Inspektion |

### 4.3 Koordination mit graph-exploration.md

```
graph-exploration.md:      PRIMARY — "Graph-Tools nutzen, wenn verfügbar"
                               ↓
graph-fallback-process.md: BACKUP — "Wenn Graph-Tools nicht gehen, so geht's weiter"
```

**Regel:**
1. `graph-exploration.md` ist die primäre Anweisung — sie wird immer zuerst versucht.
   Sie definiert, welches Graph-System für welche Aufgabe am besten geeignet ist.
2. Dieses Dokument wird NUR aktiviert, wenn Graph-Tools tatsächlich fehlschlagen.
   **Wichtig:** Bevor Read/Glob/Gref-Fallback aktiviert wird, wird das jeweils
   andere Graph-System als Alternative geprüft (§3.2a).
3. Der Fallback ersetzt NICHT `graph-exploration.md` — er ist eine temporäre
   Abweichung für die laufende Session.
4. Nach Session-Ende: Nächste Session startet wieder mit `graph-exploration.md`.

### 4.4 Rollen im Fallback

| Rolle | Verantwortung |
|-------|--------------|
| **Coordinator** | Erkennt Graph-Ausfall, prüft Alternativ-System (§3.2a), aktiviert Fallback, dokumentiert im Handoff |
| **Architecture Specialist** | Nutzt statische Doku (`directory-structure.md`, `module-map.md`) oder codebase-memory-mcp (`get_architecture`) statt code-review-graph |
| **Implementation Specialist** | Nutzt `grep`/`glob` oder codebase-memory-mcp (`search_graph`, `trace_path`) statt `semantic_search_nodes_tool` |
| **Testing Specialist** | Nutzt `glob` + `grep` oder codebase-memory-mcp (`search_graph` + label) statt `query_graph_tool tests_for` |
| **Platform Specialist** | Nutzt `git diff` oder codebase-memory-mcp (`detect_changes`) statt `detect_changes_tool` |

---

## 5. Long-Term Mitigation

### 5.1 Script: Graph Auto-Build bei Session-Start

Ein `just`-Command für manuelles und automatisiertes Graph-Rebuilding:

```justfile
# Rebuild the code knowledge graph (incremental)
graph-rebuild:
    echo "⚠️  Run code-review-graph_build_or_update_graph_tool in opencode"
    echo "    This must be done inside an opencode session — cannot be scripted externally"
    echo "    → Full rebuild:  full_rebuild=True"
    echo "    → Incremental:   (default, no parameter)"
```

> **Hinweis**: Da der MCP-Server von opencode gemanagt wird, kann der Rebuild
> nicht vollständig extern via Skript erfolgen. Der MCP-Tool-Aufruf muss innerhalb
> der opencode-Session passieren. Ein `just graph-rebuild` kann aber als Erinnerung
> und Dokumentation dienen.

### 5.2 Session-Opening Automatisierung

**Kurzfristig** (heute umsetzbar):
- Coordinator führt `build_or_update_graph_tool` (inkrementell) als ersten
  Schritt nach dem Laden der Context-Files aus.
- Dies ist bereits in §2.1 dokumentiert.

**Mittelfristig** (nach opencode-Update):
- Prüfen, ob opencode ein `onSessionOpen` Hook oder Pre-Script unterstützt.
- Falls ja: `build_or_update_graph_tool` automatisch beim Session-Start ausführen.

**Langfristig** (opencode Feature Request):
- Feature Request an opencode: MCP-Server-Session-Persistenz oder Auto-Restart
  bei Connection-Timeout.
- Status: `docs/architecture/questions/Q-003-graph-mcp-stability.md` (neu anlegen)

### 5.3 MCP Server Stability Tracking

| Datum | Beobachtung | Frequency | Aktion |
|-------|------------|-----------|--------|
| TBD | Erster Session-Start nach IDE-Öffnung | Jede Session | Immer Rebuild nötig |
| TBD | Innert einer Session | Selten | Meist stabil — Server stirbt selten |
| TBD | Nach IDE-Hibernation/Standby | Häufig | Server wird beendet → Rebuild nötig |

**Zu tracken:**
- Wie oft tritt "not connected" pro Woche auf?
- Wie lange dauert der inkrementelle Rebuild (Sekunden)?
- Gibt es Sessions ohne Graph-Ausfall?

Wenn "not connected" seltener als 1x pro 10 Sessions auftritt → Fallback-Prozess
ist ausreichend. Wenn häufiger → MCP-Server-Konfiguration in `opencode.json`
prüfen (timeout erhöhen? restart mechanism?).

### 5.4 Potenzielle Verbesserungen

| Idee | Aufwand | Nutzen | Priority |
|------|---------|--------|----------|
| `just graph-rebuild` Command | Gering | Erinnerung/Doku | Niedrig |
| Session-Start automatischer Rebuild | Gering | Prevention | Hoch |
| Q-003: MCP Stability Issue tracken | Gering | Langfristige Beobachtung | Mittel |
| opencode Feature Request (Session-Persistenz) | Recherche | Könnte Problem eliminieren | Mittel |
| Graph-Fallback-Erkennung in CI | Hoch | Automatische Meldung | Niedrig |
| Health-Check vor erstem graph-Aufruf | Recherche | Früherkennung | Mittel |

---

## Anhang A: Quick Reference Card

### Fallback in 3 Schritten

```
1. build_or_update_graph_tool versuchen (inkrementell, 120s timeout)
   ├─→ Erfolg → Normal
   └─→ Fehler → weiter mit Schritt 2

2. Zweiten graph-Tool-Aufruf versuchen (irgendein Tool)
   ├─→ Erfolg → Normal (erster Fehler war transient)
   └─→ Fehler → weiter mit Schritt 3

3. codebase-memory-mcp als Alternative prüfen (§3.2a Matrix)
   ├─→ Verfügbar → Equivalentes Tool aus Matrix nutzen
   └─→ Nicht verfügbar → BEIDE Systeme ausgefallen → weiter mit Schritt 4

4. Fallback auf Read/Glob/Grep aktivieren:
   - Must-fix Tools     → Mapping aus §3.2 verwenden
   - Should-track       → Mapping + Issue erfassen
   - Accept / Unique    → Überspringen, im Handoff dokumentieren
```

### Häufigste Fallback-Pfade

| Brauche | Primäres Graph-Tool | codebase-memory-mcp Equivalent | Read/Glob/Grep Fallback |
|---------|---------------------|-------------------------------|------------------------|
| "Wo ist die Funktion X?" | `semantic_search_nodes_tool` | `search_graph` (BM25) | `grep "def X" -r packages/ apps/ --include '*.py'` |
| "Wer ruft X auf?" | `query_graph_tool callers_of` | `trace_path` (inbound) | `grep "X(" -r packages/ apps/ --include '*.py'` |
| "Was ist der Impact?" | `get_impact_radius_tool` ⭐ | — (kein Equivalent) | Manuelles Tracing: betroffene Dateien lesen, callees per `grep` finden |
| "Architektur-Überblick" | `get_architecture_overview_tool` | `get_architecture` (Leiden) | `docs/reference/directory-structure.md` + `module-map.md` |
| "Was hat sich geändert?" | `detect_changes_tool` | `detect_changes` | `git diff HEAD~1` + `git log --oneline -10` |
| "Tests für X?" | `query_graph_tool tests_for` | `search_graph` + label=Test | `glob tests/**/test_*.py` + `grep "class.*X"` |

---

## Anhang B: Relation zu anderen Dokumenten

| Dokument | Beziehung |
|----------|-----------|
| `graph-exploration.md` | **Primary Standard** — dieses Dokument ist der Backup-Prozess |
| `feature-pipeline.md` | Definiert Stage 3 (Discover) — Fallback ist operationaler Sub-Prozess |
| `quality-gates.md` | Qualitäts-Gates bleiben unberührt — Fallback ist ein Effizienz-, kein Qualitätsverlust |
| `coordinator-cross-section-checklist.md` | Checkliste bleibt unberührt — Fallback kann einzelne Checks erschweren (im Handoff vermerken) |
| `navigation.md` | Priority Reading Order: Fallback-Dokument ist Teil der processes/ (Tier 2, on-demand) |

---

> **Letzte Aktualisierung**: 2026-06-30
> **Betreut durch**: Architecture Agent
> **Review-Zyklus**: Bei jedem MCP-Update oder opencode-Update auf Relevanz prüfen
