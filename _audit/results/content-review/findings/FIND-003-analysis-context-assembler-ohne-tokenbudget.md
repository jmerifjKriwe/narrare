# FIND-003: Analysis-ContextAssembler ohne TokenBudget-System
Priorität: 🟡 Mittel
Status: Offen
Review: cr-03
CR-AUFG: CR-AUFG-03-03
Querverweise: cr-04 §4.1 (oberflächlicher Kontext für Beta-Reader)

## Befund

`apps/api/narrare/analysis/context_assembler.py` ist ein völlig eigener
ContextAssembler, der **nicht** von `WritingContextAssembler` /
`TokenBudgetManager` erbt. Er trunciert KB-Einträge auf 200 Zeichen
(`kb_summary_truncation=200`) ohne Token-Bewusstsein. Kein Overflow-Handling,
keine Priorisierung, keine Tier-Logik.

Dies ist der BetaReader-Pfad — das Modell arbeitet potenziell mit
unvollständigem KB-Kontext (200-Zeichen-Stumps statt voller Entries).

Symptomatisch für einen **strukturellen Adoptions-Flickenteppich**: Writing
nutzt das vollständige 5-Tier-Budget-System, Analysis/KB/Planning ignorieren
es und truncieren blind nach Zeichen.

## Evidenz

- `apps/api/narrare/analysis/context_assembler.py:50` — hardcoded
  `kb_summary_truncation=200` Zeichen.
- Keine Vererbung von `TokenBudgetManager` oder `WritingContextAssembler`.
- Verifiziert via `query_graph_tool(callers_of, TokenBudgetManager)` (46 Caller,
  fast alle Writing-Tests) + Read der Analysis-Context-Builder.
- `core/context/budget.py:59` — `DEFAULT_TOTAL_BUDGET=6000` (das etablierte
  System, das Analysis nicht nutzt).

## Auswirkung

Bei großen KBs oder langen Kapiteln schneidet der BetaReader-Kontext still ab.
Feld-Widersprüche, die im abgeschnittenen Teil liegen (>200 Zeichen), werden
übersehen. Das Modell arbeitet mit oberflächlichen KB-Stumps für eine Aufgabe,
die Tiefe braucht.

## Empfehlung

Evaluieren, ob Analysis von einem analogen Tier-System profitiert (oder ob eine
`AnalysisContextAssembler(TokenBudgetManager)`-Subklasse sinnvoll ist).
Mindestens: Char-Truncation durch Token-bewusste Truncation ersetzen.

**Owner:** Backend + Core. **Abstimmung:** Architecture-Specialist (RULE-03
Contract first).

## Verifikation

- [ ] Analysis-ContextAssembler nutzt Token-bewusste Truncation statt 200-Zeichen
- [ ] Overflow-Handling implementiert (oder begründet, warum nicht nötig)
- [ ] BetaReader erhält vollen oder priorisierten KB-Kontext
- [ ] Contract (Protocol) definiert vor Implementierung (RULE-03)
