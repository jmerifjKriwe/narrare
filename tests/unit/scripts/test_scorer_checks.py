"""Tests for scripts/adoption/scorer_checks.py — infrastructure checks.

Validates the ``unverified`` flag for fallback-branch infrastructure
(``token_budget``, ``injection_defense``) vs. verified branches (variable
evidence, ``prompt_composer``, ``i18n``).

The fallback branch assumes adoption from bundled-prompt file presence only —
a structurally invalid proxy for code-level infrastructure usage.  The
``unverified`` flag makes this assumption visible without changing the score
(ratchet discipline).
"""

from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
_SCRIPTS = str(Path(__file__).resolve().parent.parent.parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

from adoption.scorer_checks import check_infrastructure  # noqa: E402

# ── Fallback branch: unverified infrastructure ─────────────────────


class TestUnverifiedFallback:
    def test_token_budget_with_prompts_is_unverified(self) -> None:
        """token_budget assumed from file-presence only → unverified=True."""
        detail = check_infrastructure("token_budget", "required", set(), True, 1.0)
        assert detail.adopted == 1.0  # score contribution unchanged (ratchet)
        assert detail.unverified is True

    def test_injection_defense_with_prompts_is_unverified(self) -> None:
        """injection_defense assumed from file-presence only → unverified=True."""
        detail = check_infrastructure("injection_defense", "required", set(), True, 1.0)
        assert detail.adopted == 1.0
        assert detail.unverified is True

    def test_token_budget_without_prompts_not_unverified(self) -> None:
        """No prompts → adopted=0.0; nothing assumed → unverified=False."""
        detail = check_infrastructure("token_budget", "required", set(), False, 1.0)
        assert detail.adopted == 0.0
        assert detail.unverified is False

    def test_note_mentions_no_code_level_evidence(self) -> None:
        """The note honestly labels the assumption."""
        detail = check_infrastructure("token_budget", "required", set(), True, 1.0)
        assert "unverified" in detail.note
        assert "no code-level evidence" in detail.note

    def test_note_without_prompts(self) -> None:
        detail = check_infrastructure("token_budget", "required", set(), False, 1.0)
        assert detail.note == "no prompts to validate"

    def test_unknown_fallback_infra_also_unverified(self) -> None:
        """Any infra hitting the final fallback is unverified, not just the two known."""
        detail = check_infrastructure("some_future_infra", "required", set(), True, 1.0)
        assert detail.unverified is True

    def test_partial_level_fallback_unverified(self) -> None:
        """token_budget at 'partial' level with prompts is still unverified=True."""
        detail = check_infrastructure("token_budget", "partial", set(), True, 1.0)
        assert detail.adopted == 1.0
        assert detail.unverified is True


# ── Verified branches: unverified must be False ────────────────────


class TestVerifiedBranches:
    def test_kb_entities_with_vars_not_unverified(self) -> None:
        """Variable-evidence infra is verified."""
        detail = check_infrastructure(
            "kb_entities", "required", {"kb_characters", "kb_locations"}, True, 1.0
        )
        assert detail.adopted == 1.0
        assert detail.unverified is False

    def test_kb_entities_without_vars_not_unverified(self) -> None:
        """Even when vars are missing, the check is verified (just adopted=0.0)."""
        detail = check_infrastructure("kb_entities", "required", set(), True, 1.0)
        assert detail.adopted == 0.0
        assert detail.unverified is False

    def test_mem0_preferences_not_unverified(self) -> None:
        detail = check_infrastructure(
            "mem0_preferences", "required", {"user_preferences"}, True, 1.0
        )
        assert detail.unverified is False

    def test_prompt_composer_not_unverified(self) -> None:
        """prompt_composer has its own established branch — not unverified."""
        detail = check_infrastructure("prompt_composer", "required", set(), True, 1.0)
        assert detail.adopted == 1.0
        assert detail.unverified is False

    def test_meta_prompt_not_unverified(self) -> None:
        detail = check_infrastructure("meta_prompt", "required", set(), True, 1.0)
        assert detail.unverified is False

    def test_i18n_not_unverified(self) -> None:
        """i18n has its own proportional branch — not unverified."""
        detail = check_infrastructure("i18n", "partial", set(), True, 0.5)
        assert detail.adopted == 0.5
        assert detail.unverified is False
