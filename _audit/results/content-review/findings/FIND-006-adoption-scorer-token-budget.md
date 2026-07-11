# FIND-006: Adoption-Scorer wertet token_budget als "adopted" ohne Code-Nachweis
Priorität: 🟡 Mittel
Status: Offen
Review: cr-03
CR-AUFG: CR-AUFG-03-07

## Befund

Der Adoption-Scorer (`scripts/adoption/scorer_checks.py`) wertet `token_budget`
als "assumed adopted if bundled prompts exist" — **ohne Code-Nachweis**.
Analysis/KB/Planning passieren das `token_budget: required`-Gate problemlos,
obwohl ihre Services kein Budget-System nutzen.

Die `infrastructure_definition` sagt: *evidence: "uses TokenBudgetManager or
ContextAssembler with budget parameter"* — aber der Scorer prüft diese Evidence
**nicht** im Code, sondern nur Datei-Präsenz.

Dies erklärt, warum Analysis-Services ohne Budget-System das Gate passieren
(siehe FIND-003, FIND-004).

## Evidenz

- `scripts/adoption/scorer_checks.py:60-62`:
  ```python
  # token_budget / injection_defense: assume adopted if bundled prompts exist.
  adopted = 1.0 if has_prompts else 0.0
  ```
- `scripts/architecture/adoption-registry.yaml` (v2.0.0) — definiert
  `token_budget: required` für alle Kategorien.
- `injection_defense` leidet unter demselben Problem ("assumed adopted").

## Auswirkung

Die Adoption-Gate hat eine systematische Lücke: `token_budget` und
`injection_defense` werden als "adopted" gewertet ohne Code-Nachweis. Neue
Features ohne Budget-System passieren das Gate ungeprüft. Das Gate suggeriert
Compliance, die nicht real existiert (False Control).

## Empfehlung

Erweitere den Scorer (oder einen neuen Checker), dass er verifiziert: "Nutzt
dieser Service-Code `TokenBudgetManager` oder `ContextAssembler(total_budget=...)`?".
Mindestens: Flagge Kategorien als "unverified" statt "adopted", wenn nur
Datei-Präsenz vorliegt.

**Owner:** Platform (CI/Enforcement). **Abstimmung:** Mit Platform-Specialist.

## Verifikation

- [ ] Scorer prüft Code-Nachweis für `token_budget` (nicht nur Datei-Präsenz)
- [ ] Analysis/KB/Planning werden als "unverified" oder "not adopted" markiert
- [ ] `injection_defense` analog gegen Code verifiziert
- [ ] CI-Report zeigt tatsächlichen Adoptions-Status
