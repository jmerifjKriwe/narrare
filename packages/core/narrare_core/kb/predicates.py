"""Canonical predicate vocabulary for KB extraction metadata and relationships.

Canonical vocabulary for extraction metadata keys and relationship types.
The extraction prompt offers these; the benchmark matcher normalizes to
these.

Registry slices:

- ``REFERENCE_FACT_PREDICATES`` — the ``predicate:`` values of the
  benchmark reference corpus (``benchmark/corpus/reference/entities.yaml``):
  metadata/fact keys the build-quality fact matcher licenses.
- ``REFERENCE_RELATION_PREDICATES`` — the ``predicate:`` values of
  ``benchmark/corpus/reference/relations.yaml``: relationship types the
  relation matcher licenses.
- ``COMMON_EDGE_PREDICATES`` — interpersonal generic relationship
  patterns the reference corpus does not use, aligned with the
  suggestions in ``narrare_core.kb.relationships``. The extraction
  prompt teaches these as relationship edges.
- ``COMMON_METADATA_PREDICATES`` — spatial/ownership/workplace
  patterns plus generic metadata keys. These are facts, never
  relationship edges (interpersonal-only ruling, extraction prompt
  v1.9.0+), so the extraction prompt does not teach them.
- ``COMMON_EXTRACTION_PREDICATES`` — the union of the two common
  slices. Chosen so no pattern differs from a reference predicate
  only by the ``_of`` suffix (the offered vocabulary stays
  unambiguous).
- ``EDGE_PROMPT_PREDICATES`` — the predicates the extraction prompt
  teaches as relationship edges: the reference relation slice plus
  the interpersonal common edge slice.

``CANONICAL_PREDICATES`` is the union of the reference and common
slices. The benchmark runner intentionally does NOT import this module
(co-evolution boundary, see ``benchmark/__init__.py``); its matchers
mirror the reference slices by folding surface variants onto these
canonical forms.
"""

from __future__ import annotations

REFERENCE_FACT_PREDICATES: frozenset[str] = frozenset(
    {
        # Persons: temporally scoped attributes
        "age_stated",
        "age_at_death",
        "birth_date",
        "birth_year",
        "profession",
        "residence",
        "district",
        "student_at",
        "widowed_since",
        "given_up_for_adoption",
        "relation_to_ilse",
        # Persons → places/objects (entity-valued facts)
        "residence_of",
        "workplace_of",
        "owner",
        "owner_of",
        "located_at",
        "allotment_of",
        "discovered_in_drawer_of",
        "promised_to",
        # Places/objects
        "exists_from",
        "covers_period",
        "in_daily_use",
        "second_bundle_revealed",
    }
)

REFERENCE_RELATION_PREDICATES: frozenset[str] = frozenset(
    {
        # Kinship
        "mother_of",
        "father_of",
        "son_of",
        "sibling_of",
        "half_sibling_of",
        "grandmother_of",
        "first_grandchild_of",
        "spouse_of",
        "engaged_to",
        "not_related_to",
        "unrelated_to_family_of",
        # Social roles
        "colleague_of",
        "business_partner_of",
        "neighbor_of",
        "babysitter_of",
        "keeper_of",
        "property_manager_of",
        "met_on_jury_with",
        "confused_in_mail_with",
        "sits_within_earshot_of",
    }
)

COMMON_EDGE_PREDICATES: frozenset[str] = frozenset(
    {
        # Interpersonal generics (kb.relationships suggestions) —
        # relationship edges per the interpersonal-only ruling.
        "ally",
        "rival",
        "enemy_of",
        "family_of",
        "mentor_of",
        "mentee_of",
    }
)
"""Interpersonal generic relationship patterns, taught as edges."""

COMMON_METADATA_PREDICATES: frozenset[str] = frozenset(
    {
        # Spatial / ownership / workplace patterns
        "member_of",
        "leader_of",
        "located_in",
        "born_in",
        "lives_in",
        "owns",
        "created",
        # Generic metadata keys
        "description",
        "status",
        "death_date",
    }
)
"""Fact-style common patterns; never relationship edges."""

COMMON_EXTRACTION_PREDICATES: frozenset[str] = COMMON_EDGE_PREDICATES | COMMON_METADATA_PREDICATES
"""All common extraction patterns (edge + metadata slices)."""

EDGE_PROMPT_PREDICATES: frozenset[str] = REFERENCE_RELATION_PREDICATES | COMMON_EDGE_PREDICATES
"""Predicates the extraction prompt teaches as relationship edges.

Scope of the interpersonal-only ruling (extraction prompt v1.9.0+,
ADR-085-adjacent design decision): spatial location, ownership, and
workplace affiliation predicates are metadata facts — they live in
``COMMON_METADATA_PREDICATES`` and are absent from the prompt's edge
lists.
"""

CANONICAL_PREDICATES: frozenset[str] = (
    REFERENCE_FACT_PREDICATES | REFERENCE_RELATION_PREDICATES | COMMON_EXTRACTION_PREDICATES
)
"""Union of the reference registries and the common extraction patterns."""
