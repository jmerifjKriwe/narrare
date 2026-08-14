---
description: Systematisches Debugging — Skill + Regression-First
---

Debugge das gemeldete Issue systematisch.

Lade ZUERST den Skill `systematic-debugging` und folge seinem Prozess.
Issue/Report: $ARGUMENTS

Ablauf:
1. **Reproduzieren** — kürzester Weg, das Issue zuverlässig auslösen.
2. **Root-Cause** — ≥2× "Warum?". Ursache via `graphify`/Read finden, **nicht** via
   `git bisect`/`blame` (das ist Rechtfertigung, nicht Analyse).
3. **Regression-Test** — failing Test schreiben, der das Issue reproduziert.
4. **Fix** — erst nach Freigabe; minimale, architektonisch korrekte Lösung (kein Workaround).
5. **Verifikation** — alle Tests grün, `just typecheck` + `just lint`.

Keine Symptom-Behandlung, keine Quick-Fixes.
