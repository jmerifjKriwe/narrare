#!/usr/bin/env bash
# Update external skills:
#   1. .agents/skills          — vercel-labs / anthropics ecosystem (npx skills)
#   2. .opencode/skills/<12>   — vendored superpowers (from upstream git)
#
# Afterwards: review `git diff` — NEVER auto-commit skill updates.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

echo "==> 1/2  .agents/skills (npx skills / vercel-labs ecosystem)"
if command -v npx >/dev/null 2>&1; then
  npx -y skills update || echo "WARN: 'npx skills update' fehlgeschlagen (Tool nicht installiert? Skill-Set manuell prüfen)."
else
  echo "SKIP: npx nicht verfügbar."
fi

echo ""
echo "==> 2/2  vendored superpowers skills (.opencode/skills)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
if git clone --depth 1 https://github.com/obra/superpowers.git "$TMP/superpowers" 2>/dev/null; then
  SK="$TMP/superpowers/skills"
  # Genutzte Skills (ohne using-superpowers = Bootstrap, ohne writing-skills = 0 Loads).
  for s in brainstorming dispatching-parallel-agents executing-plans \
           finishing-a-development-branch receiving-code-review requesting-code-review \
           subagent-driven-development systematic-debugging test-driven-development \
           using-git-worktrees verification-before-completion writing-plans; do
    if [ -d "$SK/$s" ]; then
      rm -rf ".opencode/skills/$s"
      cp -r "$SK/$s" ".opencode/skills/$s"
      echo "  aktualisiert: $s"
    else
      echo "  WARN: superpowers-Skill '$s' im Upstream nicht gefunden"
    fi
  done
else
  echo "WARN: superpowers-Upstream nicht erreichbar — vendored Skills nicht aktualisiert."
fi

echo ""
echo "==> Geänderte Skills:"
git diff --stat -- .agents/skills .opencode/skills 2>/dev/null || true
echo ""
echo "Fertig. Bitte 'git diff' reviewen — NICHT blind committen."
