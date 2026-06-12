<!-- Context: narrare-dev/processes/graph-fallback-process | Priority: high | Source: code-review-graph MCP behaviour + code-graph-first.md | Updated: 2026-06-12 -->

# Graph-Stabilität: Strategie & Fallback-Prozess

> **Ziel**: Wenn der `code-review-graph` MCP Server nicht verfügbar ist, müssen
> alle Specialists und der Coordinator einen dokumentierten, schrittweisen
> Fallback-Prozess haben — ohne Spekulation, ohne Workarounds, ohne Zeitverlust.
>
> **Primary Standard**: `code-graph-first.md` — dieses Dokument ist der Backup-Prozess.
> Der Graph ist immer der erste Weg. Fallback ist der zweite.

---

## 1. Root Cause Analysis

### 1.1 Warum passiert "not connected"?

Der `code-review-graph` Server ist ein **externer MCP Sidecar-Prozess**,
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
│   └─→ Fehlschlag → Fallback aktivieren
│
└─→ Fallback-Zähler: 2 consecutive Failures?
    ├─→ Ja → Fallback-Prozess starten (§3.2)
    └─→ Nein → Ersten Fehler als transient behandeln, später nochmal versuchen
```

**Abbruchkriterium**: Wenn 2 aufeinanderfolgende graph-Tool-Aufrufe fehlschlagen
(egal welche Tools), wird der Fallback-Prozess aktiviert.

### 3.2 Graph-Tool → Fallback Mapping

| Graph Tool | Alternative(n) | Genauigkeit | Performance |
|------------|----------------|-------------|-------------|
| `semantic_search_nodes_tool` | `grep` + `glob` — Funktions-/Klassennamen suchen; `grep` für Muster | Mittel — findet nur exakte Textmatches, keine Semantik | Langsamer bei grossen Codebasen |
| `query_graph_tool callers_of` | `grep` für Funktionsreferenzen — `rg "function_name" --include '*.py'` | Hoch — findet alle Textreferenzen (auch Kommentare) | Manuelle Deduplikation nötig |
| `query_graph_tool callees_of` | Quelltext-Lesen — `read` der Datei + manuelle Tracing | Niedrig — hängt vom Leser ab | Zeitaufwändig |
| `query_graph_tool imports_of` | `read` der Datei + manuelle Prüfung der Import-Blöcke | Hoch — aber kein automatisches Transitives | Direkt |
| `query_graph_tool importers_of` | `grep` für Modul-Importe — `rg "from module"` | Mittel — erfasst nur direkte Imports | Erfordert mehrere Grep-Durchläufe |
| `query_graph_tool tests_for` | `glob` nach Testdateien — `glob tests/**/test_*` + `grep` für Klassennamen | Hoch — wenn Tests benannt sind | Meist ausreichend |
| `query_graph_tool children_of` | `read` der Datei + Verzeichnisstruktur (`ls`) | Hoch — für einzelne Dateien | Manuelle Analyse |
| `get_impact_radius_tool` | **Manuelles Tracing**: Änderungsdateien lesen, dann `grep` callees, dann Gelesenes manuell verketten | Niedrig — fehleranfällig | Sehr zeitaufwändig |
| `get_architecture_overview_tool` | `docs/reference/directory-structure.md` lesen + `module-map.md` | Mittel — statische Doku, kein Live-Graph | Sofort verfügbar |
| `detect_changes_tool` | `git diff HEAD~1` + `git log --oneline -10` — manuelle Code-Inspektion | Hoch — präzise, aber ohne Risiko-Scoring | Manuelle Analyse |
| `get_affected_flows_tool` | Manuelle Code-Verfolgung — `grep` + `read` der Call-Chain | Niedrig — kein automatisches Flow-Tracing | Sehr zeitaufwändig |
| `get_minimal_context_tool` | `read` der relevanten Dateien + `git log` für History | Mittel — kein strukturierter Kontext | Manuelle Synthese |
| `get_hub_nodes_tool` | Expertise-basiert — bekannte Hotspots aus `module-map.md` | Niedrig — veraltet schnell | Kein automatisierter Check |
| `get_bridge_nodes_tool` | Nicht ersetzbar — Bridge-Analyse ist rein graph-basiert | ❌ Nicht verfügbar | Akzeptieren |
| `refactor_tool (rename)` | `grep` + `sed` — manuelles Find-and-Replace | Niedrig — kein sicherer Preview | Riskant ohne Graph |
| `refactor_tool (dead_code)` | Manuelle Code-Inspektion — `grep` nach ungenutzten Funktionen | Niedrig — falsch-positive und falsch-negative | Zeitaufwändig |
| `find_large_functions_tool` | `wc -l` auf Dateien + manuelle Durchsicht | Niedrig — nur auf Datei-Ebene | Manuell |
| `get_knowledge_gaps_tool` | Nicht ersetzbar — Graph-Analyse | ❌ Nicht verfügbar | Akzeptieren |
| `get_surprising_connections_tool` | Nicht ersetzbar — Graph-Analyse | ❌ Nicht verfügbar | Akzeptieren |
| `traverse_graph_tool` | Nicht ersetzbar — Graph-Traversal | ❌ Nicht verfügbar | Akzeptieren |
| `list_graph_stats_tool` | `ls -lh .code-review-graph/graph.db` — Dateigrösse prüfen | Mittel — nur Metadaten | Trivial |

### 3.3 Severity Classification

| Severity | Definition | Verhalten |
|----------|------------|-----------|
| **Must-fix** | Graph-Tool-Ausfall blockiert den aktuellen Task | **Fallback sofort aktivieren** — die Alternative ist implementierbar, aber mit geringerer Effizienz. Task kann trotzdem abgeschlossen werden. |
| **Should-track** | Graph-Tool-Ausfall reduziert Effizienz, blockiert aber nichts | **Fallback aktivieren, später tracken** — Task läuft mit manuellen Alternativen. Ein Issue sollte erstellt werden, wenn das Muster sich wiederholt. |
| **Accept** | Graph-Tool ist nicht durch manuelle Methoden ersetzbar | **Task ohne das Tool fortsetzen** — die Analyse muss übersprungen oder mit reduzierter Qualität akzeptiert werden. |

**Severity pro Tool im Fallback:**

| Graph Tool | Fallback Severity | Begründung |
|------------|-------------------|------------|
| `semantic_search_nodes_tool` | Must-fix | `grep`/`glob` sind akzeptable Alternativen, aber weniger effizient |
| `query_graph_tool callers_of` | Must-fix | `grep`-basierte Suche ist machbar |
| `query_graph_tool callees_of` | Should-track | Manuelles Tracing ist machbar, aber zeitaufwändig |
| `query_graph_tool imports_of` | Must-fix | Direkt via `read` machbar |
| `query_graph_tool importers_of` | Should-track | `grep`-Suche erfordert mehrere Durchläufe |
| `query_graph_tool tests_for` | Must-fix | Glob-Patterns liefern zuverlässige Ergebnisse |
| `query_graph_tool children_of` | Must-fix | Direkt via `read` machbar |
| `get_impact_radius_tool` | Should-track | Manuelles Tracing ist fehleranfällig und zeitaufwändig |
| `get_architecture_overview_tool` | Must-fix | Statische Doku ist sofort verfügbar |
| `detect_changes_tool` | Must-fix | `git diff` + `git log` sind machbar |
| `get_affected_flows_tool` | Should-track | Manuelle Code-Verfolgung ist möglich aber ineffizient |
| `get_minimal_context_tool` | Should-track | Manuelle Synthese mehrerer Quellen nötig |
| `get_hub_nodes_tool` | Accept | Expertise-basiert, keine gute manuelle Alternative |
| `get_bridge_nodes_tool` | Accept | Nicht manuell ersetzbar |
| `refactor_tool (rename)` | Must-fix | `grep` + manuelle Edits sind machbar (aber riskant — vorher testen!) |
| `refactor_tool (dead_code)` | Should-track | Manuelle Inspektion ist aufwändig |
| `find_large_functions_tool` | Must-fix | `wc -l` auf Dateiebene machbar |
| `get_knowledge_gaps_tool` | Accept | Nicht manuell ersetzbar |
| `get_surprising_connections_tool` | Accept | Nicht manuell ersetzbar |
| `traverse_graph_tool` | Accept | Nicht manuell ersetzbar |

### 3.4 Fallback Workflow (Schritt für Schritt)

Wenn der Fallback aktiviert wird:

```
1. FALLBACK AKTIVIERT (nach 2 consecutive Failures)
   ↓
2. Welches Graph-Tool wird benötigt?
   ├─→ Severity = Must-fix
   │   → Dokumentierte Alternative aus §3.2 ausführen
   │   → Task kann normal fortgesetzt werden
   │
   ├─→ Severity = Should-track
   │   → Alternative aus §3.2 ausführen
   │   → Task läuft, aber mit reduzierter Effizienz rechnen
   │   → Nach Task-Abschluss: Issue erfassen
   │
   └─→ Severity = Accept
       → Task ohne diese Analyse fortsetzen
       → Im Handoff dokumentieren: "Graph-Tool X war nicht verfügbar"
       → Nach Task-Abschluss: Issue erfassen
   ↓
3. Graph bleibt deaktiviert für den Rest der Session
   → Nicht jede Tool-Anfrage einzeln prüfen
   → Nur bei Session-Neustart oder explizitem Rebuild-Versuch wieder aktivieren
```

### 3.5 Dokumentation im Handoff

Wenn der Fallback verwendet wurde, muss der Coordinator im Handoff
vermerken:

```
## Graph Fallback Active
- Auslöser: [z.B. "build_or_update_graph_tool timed out at session start"]
- Betroffene Tools: [Liste der Tools, die nicht genutzt werden konnten]
- Ersatzmethoden: [Liste der verwendeten Fallback-Alternativen]
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

### 4.3 Koordination mit code-graph-first.md

```
code-graph-first.md:      PRIMARY — "Immer zuerst den Graph nutzen"
                              ↓
graph-fallback-process.md: BACKUP — "Wenn der Graph nicht geht, so geht's weiter"
```

**Regel:**
1. `code-graph-first.md` ist die primäre Anweisung — sie wird immer zuerst versucht.
2. Dieses Dokument wird NUR aktiviert, wenn graph-Tools tatsächlich fehlschlagen.
3. Der Fallback ersetzt NICHT `code-graph-first.md` — er ist eine temporäre
   Abweichung für die laufende Session.
4. Nach Session-Ende: Nächste Session startet wieder mit `code-graph-first.md`.

### 4.4 Rollen im Fallback

| Rolle | Verantwortung |
|-------|--------------|
| **Coordinator** | Erkennt Graph-Ausfall, aktiviert Fallback, dokumentiert im Handoff |
| **Architecture Specialist** | Nutzt statische Doku (`directory-structure.md`, `module-map.md`) statt Graph |
| **Implementation Specialist** | Nutzt `grep`/`glob` statt `semantic_search_nodes_tool` |
| **Testing Specialist** | Nutzt `glob` + `grep` statt `query_graph_tool tests_for` |
| **Platform Specialist** | Nutzt `git diff` statt `detect_changes_tool` |

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

3. Fallback aktivieren:
   - Must-fix Tools  → Mapping aus §3.2 verwenden
   - Should-track    → Mapping + Issue erfassen
   - Accept          → Überspringen, im Handoff dokumentieren
```

### Häufigste Fallback-Pfade

| Brauche | Graph-Tool | Fallback |
|---------|------------|----------|
| "Wo ist die Funktion X?" | `semantic_search_nodes_tool` | `grep "def X" -r packages/ apps/ --include '*.py'` |
| "Wer ruft X auf?" | `query_graph_tool callers_of` | `grep "X(" -r packages/ apps/ --include '*.py'` |
| "Was ist der Impact?" | `get_impact_radius_tool` | Manuelles Tracing: betroffene Dateien lesen, callees per `grep` finden |
| "Architektur-Überblick" | `get_architecture_overview_tool` | `docs/reference/directory-structure.md` + `module-map.md` |
| "Was hat sich geändert?" | `detect_changes_tool` | `git diff HEAD~1` + `git log --oneline -10` |
| "Tests für X?" | `query_graph_tool tests_for` | `glob tests/**/test_*.py` + `grep "class.*X"` |

---

## Anhang B: Relation zu anderen Dokumenten

| Dokument | Beziehung |
|----------|-----------|
| `code-graph-first.md` | **Primary Standard** — dieses Dokument ist der Backup-Prozess |
| `feature-pipeline.md` | Definiert Stage 3 (Discover) — Fallback ist operationaler Sub-Prozess |
| `quality-gates.md` | Qualitäts-Gates bleiben unberührt — Fallback ist ein Effizienz-, kein Qualitätsverlust |
| `coordinator-cross-section-checklist.md` | Checkliste bleibt unberührt — Fallback kann einzelne Checks erschweren (im Handoff vermerken) |
| `navigation.md` | Priority Reading Order: Fallback-Dokument ist Teil der processes/ (Tier 2, on-demand) |

---

> **Letzte Aktualisierung**: 2026-06-12
> **Betreut durch**: Architecture Agent
> **Review-Zyklus**: Bei jedem MCP-Update oder opencode-Update auf Relevanz prüfen
