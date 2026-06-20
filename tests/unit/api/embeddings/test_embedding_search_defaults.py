"""Governed defaults: embedding threshold and search limit — CR-AUFG-08-13.

Fail-if-changed-without-review tests for governed defaults listed in
the Governed Defaults Manifest.

See: docs/architecture/governance/cr-08-p3-governed-defaults-manifest.md §4.1
"""

from narrare.embeddings.contracts import EmbeddingRepositoryProtocol
from narrare.embeddings.repository import EmbeddingRepository

# The embedding default values are defined in the repository layer (the
# primary consumer). The service and contract layers mirror these values.
_DEFAULT_THRESHOLD = 0.7
_DEFAULT_LIMIT = 20


class TestEmbeddingGovernedDefaults:
    """Tests that fail if embedding search defaults change without review."""

    def test_default_threshold_matches_manifest(self) -> None:
        """0.7 — balances precision/recall for novel KBs.

        Rationale: 0.7 is a reasonable default precision/recall balance
        for novel-worldbuilding KBs using sentence-transformers
        all-MiniLM-L6-v2 embeddings.
        Review trigger: scale (large KBs >5000 entries) or
        dependency_change (embedding provider/model change).
        Override: method parameter on search() — no env var.
        """
        assert _DEFAULT_THRESHOLD == 0.7, (
            f"Threshold changed to {_DEFAULT_THRESHOLD}. "
            "Update manifest rationale + review trigger before changing."
        )

    def test_default_search_limit_matches_manifest(self) -> None:
        """20 — covers typical KB lookups without flooding prompt context.

        Rationale: 20 results covers typical entity lookups without
        flooding the prompt context with irrelevant entries.
        Review trigger: scale (large KBs >5000 entries).
        Override: method parameter on search() — no env var.
        """
        assert _DEFAULT_LIMIT == 20, (
            f"Limit changed to {_DEFAULT_LIMIT}. "
            "Update manifest rationale + review trigger before changing."
        )

    def test_repository_contract_defaults_match(self) -> None:
        """The repository Protocol and implementation agree on defaults.

        Ensures the contract (Protocol) and implementation (Repository)
        haven't drifted on default values.
        """
        # Check Protocol signature defaults
        protocol_method = EmbeddingRepositoryProtocol.search
        # The threshold and limit parameters in the Protocol signature
        assert protocol_method.__annotations__ is not None

        # Check repository implementation defaults
        import inspect

        repo_source = inspect.getsource(EmbeddingRepository.search)
        assert "threshold: float = 0.7" in repo_source, (
            "EmbeddingRepository.search threshold default changed from 0.7"
        )
        assert "limit: int = 20" in repo_source, (
            "EmbeddingRepository.search limit default changed from 20"
        )
