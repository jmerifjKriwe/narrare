"""Tests for the kb category declaring ``kb_relationships`` infrastructure.

Mapping-audit F3: the kb category genuinely adopts relationships
(``{{existing_relationships}}`` in worldbuilding phase1/phase2/improve,
runtime-real) but previously declared no ``kb_relationships`` infra, leaving
its relationship adoption invisible to the gate (false negative, analogous to
the earlier kb_entities consumer-bias). The owner evidence cell
``(kb, kb_relationships) = {existing_relationships}`` now scores it adopted.

These are report-level (``compute_adoption_report``) tests; the per-cell
behaviour is covered by ``test_scorer_checks.py``. Split into its own module
to keep ``test_check_adoption.py`` under the RULE-04 test hard limit.
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

from adoption.scorer import compute_adoption_report  # noqa: E402
from prompt_checks import PromptFile  # noqa: E402

# ── Helpers ────────────────────────────────────────────────────────


def _make_prompt(
    category: str = "writing",
    locale: str = "en",
    mode: str = "",
    variables: set[str] | None = None,
) -> PromptFile:
    """Create a minimal PromptFile for testing."""
    return PromptFile(
        path=Path(f"_bundled/{category}/{locale}/{mode}/system.md"),
        rel_path=f"{category}/{locale}/{mode}/system.md",
        variables=variables or set(),
        category=category,
        locale=locale,
        mode=mode,
    )


# ── Mapping-audit F3: kb declares kb_relationships infrastructure ────


class TestKbRelationshipsInfraDeclared:
    """kb now declares ``kb_relationships`` (required); the owner evidence cell
    scores it adopted via the ``existing_relationships`` owner var.

    Adding the dimension is ratio-preserving because the owner var is present
    in the kb prompt union (kb stays 1.00 in the real registry).
    """

    @staticmethod
    def _kb_registry() -> dict[str, object]:
        return {
            "features": {
                "kb": {
                    "modes": {"consistency": {}},
                    "required_infrastructure": {
                        "kb_entities": "required",
                        "kb_relationships": "required",
                    },
                    "context_variables": {"must": [], "should": []},
                }
            },
            "inline_fallbacks": [],
        }

    def test_kb_relationships_detail_present_and_adopted(self) -> None:
        """With {{existing_relationships}} in the kb union the new dim is adopted
        and the category score is unchanged at 1.0 (ratio preserved)."""
        registry = self._kb_registry()
        prompts = [
            _make_prompt(
                "kb",
                "en",
                "consistency",
                {"existing_entity_names", "existing_relationships"},
            ),
        ]
        report = compute_adoption_report(registry, prompts)
        kb = report.categories[0]
        detail = next(
            (d for d in kb.details if d.name == "kb_relationships"),
            None,
        )
        assert detail is not None
        assert detail.adopted == 1.0
        assert detail.unverified is False
        # Both required dims adopted → ratio 1.00 (F3 is score-neutral here).
        assert kb.score == 1.0

    def test_kb_relationships_scores_zero_without_owner_var(self) -> None:
        """Without {{existing_relationships}} the new required dim scores 0.0 —
        proving the dimension is now actively scored, not silently ignored."""
        registry = self._kb_registry()
        prompts = [
            _make_prompt("kb", "en", "consistency", {"existing_entity_names"}),
        ]
        report = compute_adoption_report(registry, prompts)
        kb = report.categories[0]
        detail = next(
            (d for d in kb.details if d.name == "kb_relationships"),
            None,
        )
        assert detail is not None
        assert detail.adopted == 0.0
        # kb_entities adopted (1.0) + kb_relationships not (0.0) → 0.5.
        assert kb.score == 0.5
