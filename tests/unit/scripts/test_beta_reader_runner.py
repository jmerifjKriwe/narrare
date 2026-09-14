"""Unit tests for the beta-reader eval invocation runner (spec §9 Slice 2).

Scope per spec §4 (D2): deps faithfulness (chain step 2), composer
fallback-mode system prompts for both modes (step 3), budgeted user prompt
via the real builder + assembler (step 4), the ``_prepare_model`` replica
config shape (step 5), phase-1/2 execution over the real ``run_phase1`` /
``run_phase2`` helpers (steps 6-7), and the dry-run path with zero model
calls (spec §6/D8). TestModel seam only — no LLM (RULE-01b).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.models.test import TestModel
from scripts.evals.beta_reader_runner import (
    DEFAULT_MAX_TOKENS,
    ZAI_CODING_BASE_URL,
    BetaReaderEvalRunner,
    EvalLlmConfig,
    ModelRegistry,
    build_case_deps,
    load_llm_config,
    resolve_base_url,
    with_temperature,
)
from scripts.evals.corpus_source import load_eval_corpus

from tests.unit.scripts.test_beta_reader_scoring import (
    make_phase1_args,
    make_phase2_args,
)

if TYPE_CHECKING:
    from pathlib import Path

MANIFEST = """\
name: runner-test-corpus
version: 1
language: de
genre: Literary Fiction
chapters: [ch-01]
"""

CHAPTER_TEXT = "# Kapitel Eins\n\nDer Wald lag still im ersten Licht.\n"

LLM_YAML = """\
stack:
  project_name: narrare-benchmark

llm:
  provider: zai
  api_key: secret-key
  model: glm-5.3-flash
  zai_endpoint: general
"""


def _write_corpus(root: Path) -> Path:
    (root / "clean" / "chapters").mkdir(parents=True)
    (root / "corpus.yaml").write_text(MANIFEST, encoding="utf-8")
    (root / "clean" / "chapters" / "ch-01.md").write_text(CHAPTER_TEXT, encoding="utf-8")
    return root


@pytest.fixture
def manifest(tmp_path: Path):
    return load_eval_corpus(_write_corpus(tmp_path / "corpus"))


def make_llm_config(**overrides: Any) -> EvalLlmConfig:
    values: dict[str, Any] = {
        "provider": "zai",
        "api_key": "secret-key",
        "model": "glm-5.3-flash",
        "zai_endpoint": "general",
    }
    values.update(overrides)
    return EvalLlmConfig.model_validate(values)


class RecordingFactory:
    """Model seam: records configs, serves queued prepared TestModel calls."""

    def __init__(self, prepared: list[Any]) -> None:
        self._prepared = list(prepared)
        self.configs: list[Any] = []

    async def __call__(self, config: Any) -> Any:
        self.configs.append(config)
        return self._prepared.pop(0)


def make_prepared(args: dict[str, Any]) -> Any:
    from narrare_core.llm._prepared_call import PreparedModelCall

    return PreparedModelCall(
        model=TestModel(custom_output_args=args),
        model_settings={"temperature": 0.7, "max_tokens": 123},
        usage_limits=None,
    )


def make_runner(
    manifest: Any,
    *,
    prepared: list[Any] | None = None,
    **overrides: Any,
) -> tuple[BetaReaderEvalRunner, RecordingFactory]:
    factory = RecordingFactory(prepared or [])
    runner = BetaReaderEvalRunner(
        manifest=manifest,
        llm_config=make_llm_config(**overrides.pop("llm_overrides", {})),
        model_factory=factory,
        **overrides,
    )
    return runner, factory


class TestBuildCaseDeps:
    def test_deps_are_faithful_to_spec_chain_step_2(self, manifest: Any) -> None:
        chapter = manifest.chapters[0]

        deps = build_case_deps(manifest, chapter)

        assert deps.chapter_text == CHAPTER_TEXT
        assert deps.chapter_titles == ["Kapitel Eins"]
        assert deps.word_count == len(CHAPTER_TEXT.split())
        assert deps.genre == "Literary Fiction"
        assert deps.language == "de"
        assert deps.kb_characters == ""
        assert deps.kb_locations == ""
        assert deps.previous_chapter_summaries == []
        assert deps.focus_categories is None

    def test_untitled_chapter_falls_back_to_stem(self, manifest: Any) -> None:
        chapter = manifest.chapters[0].model_copy(update={"title": None})

        deps = build_case_deps(manifest, chapter)

        assert deps.chapter_titles == ["ch-01"]


class TestRunCase:
    @pytest.mark.asyncio
    async def test_executes_both_phases_through_seam(self, manifest: Any) -> None:
        runner, factory = make_runner(
            manifest,
            prepared=[make_prepared(make_phase1_args()), make_prepared(make_phase2_args())],
        )
        chapter = manifest.chapters[0]

        result = await runner.run_case(chapter)

        assert result.stem == "ch-01"
        assert result.dry_run is False
        assert result.call_count == 2
        assert result.phase1 is not None
        assert result.phase1.strengths[0].title == "Controlled cadence"
        assert result.phase2 is not None
        assert result.phase2.category_score == 7
        assert result.layer1_phase1 is not None
        assert result.layer1_phase1.phase == "phase1"
        assert result.layer1_phase2 is not None
        assert result.layer1_phase2.phase == "phase2"
        # Faithful to the service: one prepare per phase.
        assert len(factory.configs) == 2

    @pytest.mark.asyncio
    async def test_user_prompts_carry_corpus_channel(self, manifest: Any) -> None:
        runner, _ = make_runner(
            manifest,
            prepared=[make_prepared(make_phase1_args()), make_prepared(make_phase2_args())],
        )

        result = await runner.run_case(manifest.chapters[0])

        assert "Genre: Literary Fiction" in result.user_prompt
        assert "Kapitel Eins" in result.user_prompt
        assert "Der Wald lag still im ersten Licht." in result.user_prompt
        assert result.deepdive_user_prompt.startswith("Deep-dive analysis on: plot")
        # Phase-1 result titles feed the deep-dive prompt (spec §4 step 7).
        assert "Phase 1 strengths: Controlled cadence" in result.deepdive_user_prompt

    @pytest.mark.asyncio
    async def test_composes_production_system_prompts_for_both_modes(self, manifest: Any) -> None:
        runner, _ = make_runner(
            manifest,
            prepared=[make_prepared(make_phase1_args()), make_prepared(make_phase2_args())],
        )

        result = await runner.run_case(manifest.chapters[0])

        # de manifest language → registry template fallback de→EN (PO ruling 3).
        assert "You are an experienced beta reader" in result.system_prompt
        assert "focused deep-dive analysis" in result.deepdive_system_prompt

    @pytest.mark.asyncio
    async def test_seam_receives_pinned_model_config(self, manifest: Any) -> None:
        runner, factory = make_runner(
            manifest,
            prepared=[make_prepared(make_phase1_args()), make_prepared(make_phase2_args())],
        )

        await runner.run_case(manifest.chapters[0])

        for config in factory.configs:
            assert config.provider_name == "zai"
            assert config.model_id == "glm-5.3-flash"
            assert config.temperature == 0.0
            assert config.max_tokens == DEFAULT_MAX_TOKENS
            assert config.streams is False

    @pytest.mark.asyncio
    async def test_dry_run_makes_zero_model_calls(self, manifest: Any) -> None:
        runner, factory = make_runner(manifest)

        result = await runner.run_case(manifest.chapters[0], dry_run=True)

        assert factory.configs == []
        assert result.dry_run is True
        assert result.call_count == 0
        assert result.phase1 is None
        assert result.phase2 is None
        assert result.layer1_phase1 is None
        assert result.layer1_phase2 is None
        assert result.system_prompt
        assert result.user_prompt
        assert result.deepdive_system_prompt
        # No Phase-1 result exists — the prompt shape omits the summary lines.
        assert result.deepdive_user_prompt.startswith("Deep-dive analysis on: plot")
        assert "Phase 1 strengths" not in result.deepdive_user_prompt

    @pytest.mark.asyncio
    async def test_custom_deepdive_category_flows_through(self, manifest: Any) -> None:
        runner, factory = make_runner(
            manifest,
            prepared=[make_prepared(make_phase1_args()), make_prepared(make_phase2_args())],
            deepdive_category="prose",
        )

        result = await runner.run_case(manifest.chapters[0])

        assert result.deepdive_category == "prose"
        assert "Deep-dive analysis on: prose" in result.deepdive_user_prompt
        assert factory.configs


class TestTemperatureMerge:
    def test_with_temperature_merges_over_prepared_settings(self) -> None:
        merged = with_temperature({"max_tokens": 100, "temperature": 0.9}, 0.0)

        assert merged == {"max_tokens": 100, "temperature": 0.0}

    def test_with_temperature_on_none_creates_settings(self) -> None:
        assert with_temperature(None, 0.5) == {"temperature": 0.5}


class TestEvalLlmConfig:
    def test_zai_with_coding_endpoint_accepted(self) -> None:
        # PO ruling 2026-09-14: any endpoint accepted (spec §11-1).
        config = make_llm_config(zai_endpoint="coding")

        assert config.zai_endpoint == "coding"

    def test_zai_with_general_endpoint_accepted(self) -> None:
        config = make_llm_config(zai_endpoint="general")

        assert config.zai_endpoint == "general"

    def test_zai_with_missing_endpoint_accepted(self) -> None:
        config = make_llm_config(zai_endpoint=None)

        assert config.zai_endpoint is None


class TestLoadLlmConfig:
    def test_reads_llm_section_only(self, tmp_path: Path) -> None:
        path = tmp_path / "config.local.yaml"
        path.write_text(LLM_YAML, encoding="utf-8")

        config = load_llm_config(path)

        assert config.provider == "zai"
        assert config.model == "glm-5.3-flash"
        assert config.zai_endpoint == "general"

    def test_loads_coding_endpoint_config(self, tmp_path: Path) -> None:
        path = tmp_path / "config.local.yaml"
        path.write_text(LLM_YAML.replace("general", "coding"), encoding="utf-8")

        config = load_llm_config(path)

        assert config.zai_endpoint == "coding"

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match=r"unreadable|missing"):
            load_llm_config(tmp_path / "nope.yaml")

    def test_missing_llm_section_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "config.local.yaml"
        path.write_text("stack:\n  project_name: x\n", encoding="utf-8")

        with pytest.raises(ValueError, match="llm"):
            load_llm_config(path)


class TestEndpointAtConstruction:
    def test_runner_construction_accepts_coding_endpoint(self, manifest: Any) -> None:
        # PO ruling 2026-09-14: any zai_endpoint accepted (spec §11-1).
        runner, _ = make_runner(manifest, llm_overrides={"zai_endpoint": "coding"})

        assert runner is not None


class TestResolveBaseUrl:
    def test_coding_endpoint_maps_to_production_coding_url(self) -> None:
        # The literal production stores (apps/api/narrare/setup/service.py).
        assert resolve_base_url("coding") == "https://api.z.ai/api/coding/paas/v4"

    def test_general_and_missing_endpoint_use_provider_default(self) -> None:
        assert resolve_base_url("general") is None
        assert resolve_base_url(None) is None

    @pytest.mark.asyncio
    async def test_default_factory_routes_coding_endpoint(
        self, manifest: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: list[dict[str, Any]] = []
        prepared_queue = [make_prepared(make_phase1_args()), make_prepared(make_phase2_args())]

        async def fake_prepare(self: Any, config: Any, **kwargs: Any) -> Any:
            captured.append(kwargs)
            return prepared_queue.pop(0)

        monkeypatch.setattr(ModelRegistry, "prepare", fake_prepare)
        runner = BetaReaderEvalRunner(
            manifest=manifest,
            llm_config=make_llm_config(zai_endpoint="coding"),
        )

        await runner.run_case(manifest.chapters[0])

        assert captured
        assert all(kw["base_url"] == ZAI_CODING_BASE_URL for kw in captured)


class TestE2eModeGuard:
    """Real runs must refuse e2e_test mode — the registry serves TestModel
    there, silently recording garbage as a measurement (observed 2026-09-14)."""

    @pytest.fixture
    def e2e_mode(self, monkeypatch: pytest.MonkeyPatch):
        from narrare_core.settings import get_core_settings

        monkeypatch.setenv("NARRARE_E2E_TEST", "1")
        get_core_settings.cache_clear()
        yield
        get_core_settings.cache_clear()

    @pytest.mark.asyncio
    async def test_real_run_refuses_e2e_mode(self, manifest: Any, e2e_mode: None) -> None:
        runner, _ = make_runner(manifest)

        with pytest.raises(ValueError, match="NARRARE_E2E_TEST"):
            await runner.run_case(manifest.chapters[0])

    @pytest.mark.asyncio
    async def test_dry_run_stays_usable_in_e2e_mode(self, manifest: Any, e2e_mode: None) -> None:
        runner, factory = make_runner(manifest)

        result = await runner.run_case(manifest.chapters[0], dry_run=True)

        assert factory.configs == []
        assert result.dry_run is True


class TestDefaultMaxTokensFloor:
    """The eval pins a RAW output limit (``_model_config`` sets no
    ``token_limit_profile``), and pydantic-ai counts ``output_tokens_limit``
    cumulatively across validation-retry attempts — the same hazard that
    forced the extraction preset raises in ``token_profiles.py`` (see
    ``PROFILE_OUTPUT_LIMITS`` rationale). Production BETA_READ never hits it:
    the routing resolver seeds the ``long_texts`` intent-default profile
    (64000). The verbose deep-dive payload is ~4k tokens/response, so the
    previous 4096 pin suffocated on the first retry (observed 2026-09-14:
    run exit 1 with ``output_tokens=8000`` > limit 4096)."""

    def test_default_max_tokens_fits_verbose_payload_plus_retry_headroom(self) -> None:
        # 16384 ≈ 4 verbose responses (payload + >=2 retries across both
        # phases' worst case), mirroring the extraction-raise rationale.
        assert DEFAULT_MAX_TOKENS == 16384
