# FIND-001: Consistency-Check ohne KG-Relationships
Priorität: 🔴 Hoch
Status: Offen
Review: cr-03
CR-AUFG: CR-AUFG-03-01
Querverweise: cr-04 §3.2, §4.1 (höchstwertige Cross-Feature-Unternutzung)

## Befund

Der Consistency-Check (`ConsistencyAgent`) kann Beziehungs-Widersprüche
zwischen Knowledge Graph und Kapitel-Text strukturell nicht erkennen.
`ConsistencyDeps` enthält kein Feld für `kb_relationships`. Der
`ConsistencyCheckType.WORLD` ("faction relationships") existiert als Typ,
ist aber mangels Daten funktionslos.

Dies ist die **größte Unternutzung** des Knowledge Graph in der gesamten
Plattform — der höchstwertige Use-Case (beziehungsbasierte Konsistenz-Prüfung)
ist ungenutzt.

## Evidenz

- `apps/api/narrare/consistency/consistency_types.py:107-127` — `ConsistencyDeps`
  hat nur `kb_entity_summaries`, `timeline_events`, `extracted_facts`. Kein
  `kb_relationships`-Feld.
- `apps/api/narrare/kb/consistency_analyzer.py` — prüft nur entry-internal
  Feld-Widersprüche, keine cross-entity-Beziehungs-Konsistenz.
- `consistency_types.py:32` — `ConsistencyCheckType.WORLD` existiert, kann
  aber mangels Daten nicht effektiv arbeiten.
- Verifiziert via `query_graph_tool(callers_of, GraphService)` + Read der
  `consistency_types.py`.

## Auswirkung

Wenn der KG sagt "Aria ist Feindin von Malachai" (`relationship_type=enemy`),
der Text aber beschreibt, wie sie verbündet kämpfen, würde der
Consistency-Check dies **nicht** erkennen — die beziehungsbasierte
Konsistenz-Prüfung (der wertvollste Cross-Feature-Check) ist strukturell blind.

## Empfehlung

Erweitere `ConsistencyDeps` um `kb_relationships` (formatiert wie in Writing
via `fetch_formatted_relationships`). Wire den `ConsistencyOrchestrator`,
dass er Relationships lädt und übergibt. Aktualisiere den Consistency-Prompt
(`_bundled/analysis/en/consistency/system.md`), damit er Relationships
explizit prüft.

**Owner:** Backend + Core. **Abstimmung:** Architecture-Specialist (RULE-03
Contract-Erweiterung).

## Verifikation

- [ ] `ConsistencyDeps` hat ein `kb_relationships`-Feld
- [ ] `ConsistencyOrchestrator` lädt und übergibt Relationships
- [ ] Consistency-Prompt prüft Beziehungs-Widersprüche explizit
- [ ] Test: Beziehungs-Konflikt (KG=enemy, Text=alliiert) wird als Issue erkannt
- [ ] `ConsistencyCheckType.WORLD` funktioniert mit echten Daten
