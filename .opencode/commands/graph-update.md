---
description: Code-Knowledge-Graph inkrementell neu bauen (graphify, lokal)
---

Aktualisiere den graphify-Code-Graphen (inkrementell, lokal, nur Code → kein API-Key):

!`graphify . --code-only --no-viz 2>&1 | tail -6`

Bestätige die neuen Node-/Edge-Zahlen. Der graphify-MCP-Server nutzt automatisch die
aktuelle `graphify-out/graph.json`. Für eine vollständige Re-Extraktion inkl. Docs
(semantischer Pass via Session-Modell) stattdessen `/graphify .` direkt im Assistant nutzen.
