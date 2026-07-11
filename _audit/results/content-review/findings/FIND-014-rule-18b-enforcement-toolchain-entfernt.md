# FIND-014: RULE-18b-Enforcement-Toolchain entfernt, CONSTRAINTS.md stale
Priorität: 🔴 Hoch
Status: Offen
Review: cr-08
CR-AUFG: CR-AUFG-08-15

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

- [ ] Architektur-Entscheidung dokumentiert (Option A oder B)
- [ ] CONSTRAINTS.md RULE-18b-Abschnitt konsistent zur Realität
- [ ] ADR-051-Body bereinigt (keine Referenzen auf gelöschte Dateien)
- [ ] Remediation-Spec und P3-Manifest aktualisiert
- [ ] Falls Option A: CR-AUFG-08-14 Strukturpflicht aus Templates entfernt
- [ ] Falls Option B: Toolchain wiederhergestellt und CI-blocking
