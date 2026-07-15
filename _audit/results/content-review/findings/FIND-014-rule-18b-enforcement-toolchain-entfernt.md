# FIND-014: RULE-18b-Enforcement-Toolchain entfernt, CONSTRAINTS.md stale
Priorität: 🔴 Hoch
Status: ✅ Resolved (2026-07-15)
Review: cr-08
CR-AUFG: CR-AUFG-08-15
Entscheidung: Option A — Matrix-Enforcement bewusst entfernt (f8abb42c), RULE-18b
als Prinzip beibehalten, Enforcement via Regressionstests + ADR-045 + ad-hoc Audits.

> **Strukturmarker:** [P1] [category: configuration-effect] FIND-014 / CR-AUFG-08-15:
> RULE-18b-Enforcement-Toolchain entfernt, CONSTRAINTS.md referenziert gelöschte
> Artefakte als "CI-validated"

## Befund

Die gesamte P0-P5-Governance-Toolchain wurde im Commit `f8abb42c`
("chore: remove P0-P5 governance toolchain (ADR-047/051/061/062)")
bewusst gelöscht:

- `docs/architecture/governance/configuration-adoption-matrix.yaml` (815 Zeilen)
- `scripts/check_configuration_matrix.py` (120 Zeilen)
- `scripts/governance/` (gesamtes Verzeichnis, ~60 Dateien)
- `configuration-adoption-matrix.schema.json`, `matrix-effect-evidence.yaml`,
  `status_vocabulary.yaml`, `aufg-registry.md` (2.346 Zeilen)
- ADR-047/051/061/062 alle auf "⏸ Superseded" gesetzt.

**Das Problem:** `CONSTRAINTS.md` RULE-18b (Zeile 601-609) referenziert diese
Artefakte weiterhin als live-erzwungen ("CI-validated", "fails when…"). Diese
Aussagen sind **falsch** — weder die Matrix noch der Checker noch der
Review-Gate existieren.

Dies ist eine RULE-18b-Verletzung Typ 3 ("No regression evidence of effect")
auf Meta-Ebene: die Enforcement-Behauptung selbst hat keinen Runtime-Effekt mehr.

**Zusätzlich stale:**
- ADR-051-Body (Zeile 209-252) behauptet "Accepted" mit Implementation/Enforcement
  Evidence, die ins Leere laufen.
- `cr-08-configuration-effect-drift.md` behauptet "resolved — P0–P4 complete"
  und listet gelöschte Evidence-Dateien.
- `cr-08-p3-governed-defaults-manifest.md` verweist auf nicht-existierende
  Matrix-Einträge.
- CR-AUFG-08-14 Strukturpflicht in Review-Templates ist nicht erfüllbar
  (Matrix existiert nicht).

## Evidenz

- Commit `f8abb42c` — löschte ~60 Dateien der Governance-Toolchain.
- `docs/_shared/CONSTRAINTS.md` Zeile 601-609 — referenziert Matrix + Review-Gate
  als "CI-validated" (stale).
- `ls scripts/governance/` → Verzeichnis existiert nicht.
- `ls scripts/check_configuration_matrix.py` → Datei existiert nicht (nur
  stale `.pyc` in `scripts/__pycache__/`).
- ADR-047/051/061/062 → "⏸ Superseded" im Header, aber Body nicht bereinigt.

## Auswirkung

Kein Produktions-Ausfall — die Runtime-Werte funktionieren weiterhin korrekt.
Aber das **Präventions-Gate** für zukünftige Konfigurations-Drift-Befunde fehlt:
Neue hardcodierte Werte können unentdeckt als False Controls eindringen, weil
keine CI-Blockade mehr existiert. Dies schwächt RULE-18b auf eine reine
Dokumentations-Aussage ohne maschinelle Erzwingung.

CR-AUFG-08-14 Strukturpflicht (Matrix-Klassifikation für jeden P0/P1
`configuration-effect`-Wert) ist **nicht erfüllbar**, solange diese Entscheidung
offen ist.

## Empfehlung

Architektur-Entscheidung erforderlich (nicht im Scope des Content-Reviews):

- **(A)** RULE-18b-Enforcement-Abschnitt in CONSTRAINTS.md aktualisieren:
  Matrix als "removed/superseded" markieren, Stale-Referenzen aus ADR-051-Body,
  Remediation-Spec und P3-Manifest bereinigen. CR-AUFG-08-14 Strukturpflicht
  aus Review-Templates entfernen. → Akzeptiert die Enforcement-Lücke.
- **(B)** Configuration Adoption Matrix + Checker wiederherstellen (oder
  leichtgewichtigen Nachfolger bauen), RULE-18b bleibt voll erzwungen.

**Owner:** Architecture + Platform.

## Verifikation

- [x] Architektur-Entscheidung dokumentiert — **Option A** gewählt (siehe Resolution evidence)
- [x] CONSTRAINTS.md RULE-18b-Abschnitt konsistent zur Realität ("Enforcement boundary" umgeschrieben)
- [x] ADR-051-Body bereinigt (keine Referenzen auf gelöschte Dateien als live-erzwungen)
- [x] Remediation-Spec und P3-Manifest aktualisiert
- [x] Falls Option A: CR-AUFG-08-14 Strukturpflicht aus Templates entfernt
- [x] Falls Option B: _n.a. — Option B nicht gewählt; Option A wurde umgesetzt (Toolchain bewusst entfernt, nicht wiederhergestellt)._

## Resolution evidence

**Status:** ✅ Resolved (2026-07-15) — Implementation + Enforcement vorhanden (per
`docs/development/finding-lifecycle.md` §5). Option A wurde umgesetzt.

**Design —** Option A: Die Configuration Adoption Matrix /
`check_configuration_matrix.py` / `scripts/governance/`-Toolchain wurde im Commit
`f8abb42c` bewusst entfernt (ADR-047/051/061/062 ⛔ Superseded). Stated Policy:
"Audits bleiben ad-hoc, Review-File als SSOT". RULE-18b wird als Prinzip
beibehalten; sein Matrix-Enforcement-Mechanismus wurde zurückgezogen. Die
Entscheidung ist im Review-File (`cr-08-hardcoded-values.md` §6 + Aufgaben) und in
`CONSTRAINTS.md` dokumentiert.

**Implementation —** `docs/_shared/CONSTRAINTS.md` RULE-18b ("Enforcement
boundary") auf Realität umgeschrieben. Stale-Referenzen auf gelöschte Artefakte
bereinigt in: ADR-051/060/061/064, `docs/architecture/decisions/INDEX.md`,
`docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md`,
`docs/features/remediation/cr-08-configuration-effect-drift.md`,
`docs/development/testing-standards.md` und den beiden
`_audit/review-prompts/content-review-prompts/`-Templates (CR-AUFG-08-14
Matrix-Klassifikations-Strukturpflicht aus den Templates entfernt). Verwaiste
`scripts/__pycache__/check_configuration_matrix.cpython-314.pyc` gelöscht.

**Enforcement —** Neuer WARNING-Only-Checker
`scripts/doc_drift/removed_governance_refs_checks.py` (eingebunden in
`scripts/check_doc_drift.py`), der Referenzen auf die bekannten gelöschten
Governance-Artefakte markiert, mit geratchettem clean Baseline (Datei-Level-Allowlist
für legitime historische Referenzen). Verifiziert gegen den aktuellen Baum:
**0 Findings, Exit 0**. Der Checker verhindert exakt die Regressionsklasse, die
FIND-014 dokumentiert hat — stale Referenzen auf entfernte Governance-Artefakte
schleichen wieder ein. RULE-18b wird nun über per-value-Regressionstests +
ADR-045 (Runtime Adoption Enforcement) + ad-hoc Audits erzwungen (nicht mehr über
die entfernte Matrix).
