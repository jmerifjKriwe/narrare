---
description: RULE-XX- & Architektur-Validierung (check_architecture.py)
---

Architektur- und Constraint-Validierung für den aktuellen Stand:

!`python3 scripts/check_architecture.py 2>&1 | tail -40`

Bewerte das Ergebnis gegen @docs/_shared/CONSTRAINTS.md. Bei jeder RULE-Verletzung:
nenne RULE-XX, betroffene Datei:Zeile und die konkrete Behebung. Falls alles grün ist,
bestätige kurz die eingehaltenen Regeln.
