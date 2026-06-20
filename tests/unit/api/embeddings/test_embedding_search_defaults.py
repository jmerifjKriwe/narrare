"""Governed defaults: embedding threshold and search limit — CR-AUFG-08-13.

Fail-if-changed-without-review tests for governed defaults listed in
the Governed Defaults Manifest §4.1.

REAL CONTROL: These tests IMPORT the governed defaults from their source
module (``narrare.embeddings.contracts``) and assert that (1) the source
value matches the manifest, and (2) every consumer (repository, service)
actually wires the constant — not a coincidentally-equal bare literal.

The constants are NOT redefined locally. Changing a source constant value
breaks the value-layer tests; unwiring a consumer (hardcoding the literal)
breaks the wiring test — so the suite enforces the real behaviour, not a
self-comparison.

See: docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md §4.1
"""

import inspect

from narrare.embeddings.contracts import (
    DEFAULT_EMBEDDING_SEARCH_LIMIT,
    DEFAULT_EMBEDDING_SEARCH_THRESHOLD,
    EmbeddingRepositoryProtocol,
)
from narrare.embeddings.repository import EmbeddingRepository
from narrare.embeddings.search_queries import build_search_query
from narrare.embeddings.service import EmbeddingService


class TestEmbeddingGovernedDefaults:
    """Tests that fail if embedding search defaults change without review."""

    def test_default_threshold_matches_manifest(self) -> None:
        """0.7 — balances precision/recall for novel KBs.

        Value layer: the IMPORTED source constant equals the manifest value.
        If someone changes ``DEFAULT_EMBEDDING_SEARCH_THRESHOLD`` in
        contracts.py, this assertion fails until the manifest rationale and
        review trigger are updated here.

        Rationale: 0.7 is a reasonable default precision/recall balance
        for novel-worldbuilding KBs using sentence-transformers
        all-MiniLM-L6-v2 embeddings.
        Review trigger: scale (large KBs >5000 entries) or
        dependency_change (embedding provider/model change).
        Override: method parameter on search() — no env var.
        """
        assert DEFAULT_EMBEDDING_SEARCH_THRESHOLD == 0.7, (
            f"DEFAULT_EMBEDDING_SEARCH_THRESHOLD changed to "
            f"{DEFAULT_EMBEDDING_SEARCH_THRESHOLD}. "
            "Update manifest rationale + review trigger before changing."
        )

    def test_default_search_limit_matches_manifest(self) -> None:
        """20 — covers typical KB lookups without flooding prompt context.

        Value layer: the IMPORTED source constant equals the manifest value.
        If someone changes ``DEFAULT_EMBEDDING_SEARCH_LIMIT`` in contracts.py,
        this assertion fails until the manifest rationale and review trigger
        are updated here.

        Rationale: 20 results covers typical entity lookups without
        flooding the prompt context with irrelevant entries.
        Review trigger: scale (large KBs >5000 entries).
        Override: method parameter on search() — no env var.
        """
        assert DEFAULT_EMBEDDING_SEARCH_LIMIT == 20, (
            f"DEFAULT_EMBEDDING_SEARCH_LIMIT changed to "
            f"{DEFAULT_EMBEDDING_SEARCH_LIMIT}. "
            "Update manifest rationale + review trigger before changing."
        )

    def test_consumers_wire_the_governed_constants(self) -> None:
        """Repository, service, and query builder reference the constants.

        Usage layer: with one definition site (contracts.py), drift between
        the contract, repository, service, and query builder is structurally
        impossible. This test proves the wiring — each consumer's ``search``
        signature references the constant BY NAME rather than hardcoding a
        bare literal. If a consumer is unwired (e.g. someone replaces
        ``threshold: float = DEFAULT_EMBEDDING_SEARCH_THRESHOLD`` with
        ``threshold: float = 0.7``), this test fails even though the
        effective value would still be correct.

        We also assert the resolved signature default equals the constant
        value, so a consumer that hardcodes a *different* literal is caught
        as well.
        """
        for consumer in (EmbeddingRepository, EmbeddingService):
            search_src = inspect.getsource(consumer.search)
            assert "DEFAULT_EMBEDDING_SEARCH_THRESHOLD" in search_src, (
                f"{consumer.__name__}.search no longer references "
                "DEFAULT_EMBEDDING_SEARCH_THRESHOLD — do not hardcode the "
                "threshold; import it from narrare.embeddings.contracts."
            )
            assert "DEFAULT_EMBEDDING_SEARCH_LIMIT" in search_src, (
                f"{consumer.__name__}.search no longer references "
                "DEFAULT_EMBEDDING_SEARCH_LIMIT — do not hardcode the limit; "
                "import it from narrare.embeddings.contracts."
            )

            # Resolved signature defaults must equal the governed constants.
            sig = inspect.signature(consumer.search)
            assert sig.parameters["threshold"].default == (DEFAULT_EMBEDDING_SEARCH_THRESHOLD), (
                f"{consumer.__name__}.search threshold default drifted from the constant"
            )
            assert sig.parameters["limit"].default == (DEFAULT_EMBEDDING_SEARCH_LIMIT), (
                f"{consumer.__name__}.search limit default drifted from the constant"
            )

        # The low-level query builder must also wire the constants — otherwise
        # a bare literal survives in build_search_query and there is no longer
        # a single definition site (RULE-06).
        builder_src = inspect.getsource(build_search_query)
        assert "DEFAULT_EMBEDDING_SEARCH_THRESHOLD" in builder_src, (
            "build_search_query no longer references "
            "DEFAULT_EMBEDDING_SEARCH_THRESHOLD — do not hardcode the threshold."
        )
        assert "DEFAULT_EMBEDDING_SEARCH_LIMIT" in builder_src, (
            "build_search_query no longer references "
            "DEFAULT_EMBEDDING_SEARCH_LIMIT — do not hardcode the limit."
        )

        # The Protocol is the single definition site — it must also wire the
        # constants (not a bare literal), otherwise there are two sources of
        # truth for the value.
        protocol_src = inspect.getsource(EmbeddingRepositoryProtocol.search)
        assert "DEFAULT_EMBEDDING_SEARCH_THRESHOLD" in protocol_src, (
            "EmbeddingRepositoryProtocol.search must define the threshold "
            "default via DEFAULT_EMBEDDING_SEARCH_THRESHOLD (one definition site)."
        )
        assert "DEFAULT_EMBEDDING_SEARCH_LIMIT" in protocol_src, (
            "EmbeddingRepositoryProtocol.search must define the limit default "
            "via DEFAULT_EMBEDDING_SEARCH_LIMIT (one definition site)."
        )
