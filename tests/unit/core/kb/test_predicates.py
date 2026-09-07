"""Unit tests for the canonical predicate vocabulary (Task 2, scoring fixes).

Tests cover:
- ``CANONICAL_PREDICATES`` is a frozenset of snake_case strings
- The registry slices carry the reference counts (23 fact + 20 relation)
- Every reference predicate is a member of the canonical set
- The common slices split along the interpersonal-only ruling
  (edge generics vs. metadata-only patterns)
- Common extraction patterns do not morphologically collide with the
  reference registry (no bare-form/``_of``-form ambiguity)
- The bundled extraction prompt lists every edge prompt predicate,
  states the snake_case fallback rule and the interpersonal-only rule,
  and keeps the spatial/ownership/workplace predicates out of its
  relationship-edge rules (prompt/vocabulary alignment guard)
"""

from __future__ import annotations

import re
from pathlib import Path

import narrare_core
from narrare_core.kb.predicates import (
    CANONICAL_PREDICATES,
    COMMON_EDGE_PREDICATES,
    COMMON_EXTRACTION_PREDICATES,
    COMMON_METADATA_PREDICATES,
    EDGE_PROMPT_PREDICATES,
    REFERENCE_FACT_PREDICATES,
    REFERENCE_RELATION_PREDICATES,
)

PROMPT_PATH = (
    Path(narrare_core.__file__).resolve().parent
    / "prompts"
    / "_bundled"
    / "kb"
    / "en"
    / "extract"
    / "system.md"
)

SNAKE_CASE = re.compile(r"^[a-z][a-z0-9_]*$")

REFERENCE_FACT_PREDICATES_EXPECTED = frozenset(
    {
        "age_at_death",
        "age_stated",
        "allotment_of",
        "birth_date",
        "birth_year",
        "covers_period",
        "discovered_in_drawer_of",
        "district",
        "exists_from",
        "given_up_for_adoption",
        "in_daily_use",
        "located_at",
        "owner",
        "owner_of",
        "profession",
        "promised_to",
        "relation_to_ilse",
        "residence",
        "residence_of",
        "second_bundle_revealed",
        "student_at",
        "widowed_since",
        "workplace_of",
    }
)

REFERENCE_RELATION_PREDICATES_EXPECTED = frozenset(
    {
        "babysitter_of",
        "business_partner_of",
        "colleague_of",
        "confused_in_mail_with",
        "engaged_to",
        "father_of",
        "first_grandchild_of",
        "grandmother_of",
        "half_sibling_of",
        "keeper_of",
        "met_on_jury_with",
        "mother_of",
        "neighbor_of",
        "not_related_to",
        "property_manager_of",
        "sibling_of",
        "sits_within_earshot_of",
        "son_of",
        "spouse_of",
        "unrelated_to_family_of",
    }
)

COMMON_EDGE_PREDICATES_EXPECTED = frozenset(
    {
        "ally",
        "enemy_of",
        "family_of",
        "mentor_of",
        "mentee_of",
        "rival",
    }
)

COMMON_METADATA_PREDICATES_EXPECTED = frozenset(
    {
        "born_in",
        "created",
        "death_date",
        "description",
        "leader_of",
        "lives_in",
        "located_in",
        "member_of",
        "owns",
        "status",
    }
)

# Spatial/ownership/workplace slice of the common metadata patterns.
# The extraction prompt (v1.9.0+, interpersonal-only ruling) deliberately
# does not teach these as relationship edges; the generic metadata keys
# (death_date, description, status) remain in the prompt's Metadata Keys
# section, so only this subset must stay out of the edge rules.
SPATIAL_OWNERSHIP_WORKPLACE_PREDICATES = COMMON_METADATA_PREDICATES - frozenset(
    {
        "death_date",
        "description",
        "status",
    }
)


class TestCanonicalPredicatesRegistry:
    """Structural invariants of the canonical predicate registry."""

    def test_canonical_predicates_is_frozenset_of_snake_case_strings(self) -> None:
        assert isinstance(CANONICAL_PREDICATES, frozenset)
        assert all(isinstance(p, str) for p in CANONICAL_PREDICATES)
        assert all(SNAKE_CASE.match(p) for p in CANONICAL_PREDICATES)

    def test_registry_slices_carry_reference_counts(self) -> None:
        """Pin the reference corpus slices: 23 fact + 20 relation predicates."""
        assert len(REFERENCE_FACT_PREDICATES) == 23
        assert len(REFERENCE_RELATION_PREDICATES) == 20

    def test_canonical_predicates_cover_reference_registry(self) -> None:
        assert REFERENCE_FACT_PREDICATES == REFERENCE_FACT_PREDICATES_EXPECTED
        assert REFERENCE_RELATION_PREDICATES == REFERENCE_RELATION_PREDICATES_EXPECTED
        assert CANONICAL_PREDICATES == (
            REFERENCE_FACT_PREDICATES | REFERENCE_RELATION_PREDICATES | COMMON_EXTRACTION_PREDICATES
        )

    def test_common_slices_split_interpersonal_from_metadata_patterns(self) -> None:
        """Pin the semantic split of the common extraction patterns along
        the interpersonal-only ruling (edge generics vs. fact-style
        metadata patterns)."""
        assert COMMON_EDGE_PREDICATES == COMMON_EDGE_PREDICATES_EXPECTED
        assert COMMON_METADATA_PREDICATES == COMMON_METADATA_PREDICATES_EXPECTED
        assert COMMON_EXTRACTION_PREDICATES == (COMMON_EDGE_PREDICATES | COMMON_METADATA_PREDICATES)
        assert EDGE_PROMPT_PREDICATES == (REFERENCE_RELATION_PREDICATES | COMMON_EDGE_PREDICATES)

    def test_common_patterns_do_not_collide_with_reference_morphology(self) -> None:
        """A common pattern must never differ from a reference predicate
        only by the ``_of`` suffix — that would make the offered
        vocabulary ambiguous."""
        reference = REFERENCE_FACT_PREDICATES | REFERENCE_RELATION_PREDICATES
        for pattern in COMMON_EXTRACTION_PREDICATES:
            assert f"{pattern}_of" not in reference
            if pattern.endswith("_of"):
                assert pattern.removesuffix("_of") not in reference


class TestExtractionPromptAlignment:
    """The extraction prompt must teach the edge vocabulary and the
    interpersonal-only rule (metadata facts are never edges)."""

    def test_extract_prompt_lists_every_edge_prompt_predicate(self) -> None:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        missing = sorted(p for p in EDGE_PROMPT_PREDICATES if p not in prompt)
        assert missing == []

    def test_extract_prompt_states_interpersonal_only_rule(self) -> None:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        assert "Relationship edges are for INTERPERSONAL and social connections only" in prompt

    def test_extract_prompt_edge_rules_exclude_metadata_predicates(self) -> None:
        """The Quality Rules relationship block (MUST-list, NEVER
        sentence, further-predicates and General lists) must not teach
        any spatial/ownership/workplace predicate. Scoped to that block
        instead of the whole prompt because the English verb ``owns``
        legitimately occurs in Salience Rules prose; word boundaries
        avoid false positives such as ``owns`` inside ``ownership``."""
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        edge_rules = prompt.split("You MUST use these canonical relationship types:", 1)[1]
        edge_rules = edge_rules.split("- When updating an entity", 1)[0]
        present = sorted(
            p for p in SPATIAL_OWNERSHIP_WORKPLACE_PREDICATES if re.search(rf"\b{p}\b", edge_rules)
        )
        assert present == []

    def test_extract_prompt_states_snake_case_fallback_rule(self) -> None:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        assert "For facts not covered, use snake_case English keys." in prompt
