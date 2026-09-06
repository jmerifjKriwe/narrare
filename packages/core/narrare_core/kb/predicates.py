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
- ``COMMON_EXTRACTION_PREDICATES`` — frequent extraction patterns the
  reference corpus does not use, aligned with the suggestions in
  ``narrare_core.kb.relationships``. Chosen so no pattern differs from a
  reference predicate only by the ``_of`` suffix (the offered vocabulary
  stays unambiguous).

``CANONICAL_PREDICATES`` is the union of all three slices. The benchmark
runner intentionally does NOT import this module (co-evolution boundary,
see ``benchmark/__init__.py``); its matchers mirror the reference slices
by folding surface variants onto these canonical forms.
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

COMMON_EXTRACTION_PREDICATES: frozenset[str] = frozenset(
    {
        # Generic relationship patterns (kb.relationships suggestions)
        "ally",
        "rival",
        "enemy_of",
        "family_of",
        "mentor_of",
        "mentee_of",
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

CANONICAL_PREDICATES: frozenset[str] = (
    REFERENCE_FACT_PREDICATES | REFERENCE_RELATION_PREDICATES | COMMON_EXTRACTION_PREDICATES
)
"""Union of the reference registries and the common extraction patterns."""
