---
description: Unabhängiges Review aktueller Änderungen (Reviewer-Subagent, read-only)
agent: NarrareReviewerSpecialist
subtask: true
---

Mache ein unabhängiges Review der aktuellen Änderungen.

Geänderter Bestand:
!`git -c color.ui=never diff --stat`

Vollständiger Diff:
!`git -c color.ui=never diff`

Prüfe: Correctness, Architektur (RULE-XX aus @docs/_shared/CONSTRAINTS.md), Sicherheit,
Tests (sinnvoll, nicht nur vorhanden), Regressionen (Impact via `graphify path`/`explain`
auf Aufrufer). Output als strukturierte Findings mit Schweregrad (CRITICAL/MAJOR/MINOR/NIT)
und konkreter Behebung. Keine Edits — du bist read-only.
