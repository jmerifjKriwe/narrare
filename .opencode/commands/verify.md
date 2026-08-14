---
description: Vollständige Verifikation (Architektur + Types + Lint + Unit-Tests)
---

Vollständige Verifikation des aktuellen Stands.

## 1. Architektur-Regeln
!`python3 scripts/check_architecture.py 2>&1 | tail -30`

## 2. Typecheck
!`just typecheck 2>&1 | tail -20`

## 3. Lint
!`just lint 2>&1 | tail -20`

## 4. Unit-Tests
!`just test-unit 2>&1 | tail -30`

Fasse zusammen: welche Gates sind grün, welche rot. Bei roten Gates: Root-Cause und
konkrete Behebung — keine Symptom-Behandlung, kein `--no-verify`.
