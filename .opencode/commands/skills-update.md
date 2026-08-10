---
description: Externe Skills aktualisieren (.agents/skills + vendored superpowers)
---

Aktualisiere die externen Skills und stelle das Ergebnis zur Review.

!`bash scripts/update-skills.sh 2>&1 | tail -40`

Geänderte Skills:
!`git -c color.ui=never diff --stat -- .agents/skills .opencode/skills 2>/dev/null`

**Nicht committen** — der User reviewt die Änderungen vorher (Lockfile-Drift,
Skill-Inhalte, evtl. Breaking-Changes im Upstream).
