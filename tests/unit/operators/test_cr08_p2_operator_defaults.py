"""Operator defaults governance — CR-AUFG-08-12.

Fail-if-changed-without-review tests for every operator default
centralized during CR-08 P2. Any value change MUST be accompanied by
a manifest update and rationale review.

See: docs/architecture/governance/configuration-adoption-matrix.yaml
     docs/architecture/governance/operator-defaults-manifest.md
"""

from narrare_core.llm.model_listing import CATALOG_TIMEOUT, OPENROUTER_MAX_MODELS
from narrare_core.llm.model_pricing import DEFAULT_RATES
from narrare_core.llm.models_dev_source import CACHE_TTL, FETCH_TIMEOUT


class TestOperatorDefaultsGovernance:
    """Operator defaults that must not change without review.

    Each test documents the rationale, review trigger, and override path.
    """

    def test_catalog_timeout_matches_manifest(self) -> None:
        """10.0s — operator default for provider catalog HTTP timeout.

        Rationale: 10 seconds allows local-network providers (Ollama,
        local OpenAI-compatible proxies) to respond while catching
        genuinely unresponsive endpoints.
        Review trigger: latency_target — re-evaluate if provider
        response-time SLAs change.
        Override: ModelCatalogClient constructor parameter.
        """
        assert CATALOG_TIMEOUT == 10.0, (
            f"CATALOG_TIMEOUT changed to {CATALOG_TIMEOUT}. "
            "Update operator-defaults manifest and review trigger before changing."
        )

    def test_openrouter_max_models_matches_manifest(self) -> None:
        """30 — operator default for OpenRouter model listing cap.

        Rationale: OpenRouter returns hundreds of models; 30 covers
        the most popular without overwhelming the UI.
        Review trigger: feature_redesign — re-evaluate if the model
        listing UI is redesigned to handle larger lists.
        Override: ModelCatalogClient constructor parameter.
        """
        assert OPENROUTER_MAX_MODELS == 30, (
            f"OPENROUTER_MAX_MODELS changed to {OPENROUTER_MAX_MODELS}. "
            "Update operator-defaults manifest and review trigger before changing."
        )

    def test_cache_ttl_matches_manifest(self) -> None:
        """86400s (24h) — operator default for models.dev cache TTL.

        Rationale: 24h is sufficient for pricing metadata that changes
        weekly. Shorter TTL increases network fetch frequency; longer
        TTL risks stale pricing data.
        Review trigger: dependency_change — re-evaluate if models.dev
        update cadence changes.
        Override: load_cache_snapshot() / _load_cache() parameter.
        """
        assert CACHE_TTL == 86400, (
            f"CACHE_TTL changed to {CACHE_TTL}. "
            "Update operator-defaults manifest and review trigger before changing."
        )

    def test_fetch_timeout_matches_manifest(self) -> None:
        """10.0s — operator default for models.dev fetch timeout.

        Rationale: 10 seconds allows the remote API to respond under
        normal network conditions. Models.dev is a community dataset,
        not an SLA-backed service.
        Review trigger: dependency_change — re-evaluate if models.dev
        hosting or response-time profile changes.
        Override: fetch_models() / _fetch_models() parameter.
        """
        assert FETCH_TIMEOUT == 10.0, (
            f"FETCH_TIMEOUT changed to {FETCH_TIMEOUT}. "
            "Update operator-defaults manifest and review trigger before changing."
        )

    def test_default_rates_contain_expected_providers(self) -> None:
        """Operator fallback — cost rates when models.dev unavailable.

        Rationale: Default rates provide graceful degradation when
        the models.dev cache is empty and the remote API is unreachable.
        Values are based on published pricing at time of writing.
        Review trigger: dependency_change — re-evaluate when provider
        pricing changes significantly.
        Override: Settings.cost_rates_json env-var override.
        """
        expected_providers = {
            "openai",
            "anthropic",
            "google",
            "groq",
            "ollama",
            "zai",
            "openrouter",
        }
        assert set(DEFAULT_RATES.keys()) == expected_providers, (
            f"DEFAULT_RATES providers changed to {set(DEFAULT_RATES.keys())}. "
            "Update operator-defaults manifest and review trigger before adding/removing providers."
        )
