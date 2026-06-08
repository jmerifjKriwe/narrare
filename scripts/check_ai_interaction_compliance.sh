#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# ADR-043 / §16 AI Interaction Compliance — Pre-Commit / CI Hook
#
# Wrapper around checks/check_ai_interaction_compliance.py for use as
# a pre-commit hook or CI step.
#
# Usage:
#   ./scripts/check_ai_interaction_compliance.sh
#   ./scripts/check_ai_interaction_compliance.sh --fix
#   ./scripts/check_ai_interaction_compliance.sh --json
# ---------------------------------------------------------------------------
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$REPO_ROOT"

echo "=== ADR-043 / §16 AI Interaction Compliance Check ==="
echo ""

uv run python scripts/checks/check_ai_interaction_compliance.py "$@"
exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo "=== All §16 compliance checks passed ==="
else
    echo ""
    echo "=== §16 compliance violations found — fix before merging ==="
    echo "Run: uv run python scripts/checks/check_ai_interaction_compliance.py"
    echo "For details, see: docs/architecture/decisions/043-ai-interaction-primitives.md"
fi

exit $exit_code
