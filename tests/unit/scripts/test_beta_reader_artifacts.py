"""Unit tests for beta-reader eval run artifacts (spec 2026-09-14 §9 Slice 3).

Scope per spec §6 (D4): run-id format ``YYYY-MM-DD-<git-short>-<n>`` with a
deterministic counter, the secret sweep (planted key / ``Bearer`` / provider
key shapes), in-memory render with NO partial tree on error, atomic writes
(tmp + ``os.replace``, no leftovers), loud run-dir collision, a manifest that
never carries secrets, summary/rating content, and ``--diff`` report munging
(prompt byte deltas, Layer-1 table, metric deltas) — zero LLM calls.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from scripts.evals.beta_reader_artifacts import (
    KNOWN_GAPS,
    ArtifactError,
    CorpusView,
    FingerprintView,
    ManifestDocument,
    ModelView,
    RunRenderInput,
    config_fingerprint,
    next_eval_run_id,
    prompt_versions,
    render_run_payload,
    secret_sweep,
    write_run,
)
from scripts.evals.beta_reader_diff import render_diff_report
from scripts.evals.beta_reader_runner import EvalCaseResult, EvalLlmConfig
from scripts.evals.beta_reader_scoring import check_phase1, check_phase2
from scripts.evals.corpus_source import EvalCorpusManifest, load_eval_corpus

from tests.unit.scripts.test_beta_reader_scoring import (
    build_phase1,
    build_phase2,
    make_phase1_args,
    make_phase2_args,
)

if TYPE_CHECKING:
    from pathlib import Path

MANIFEST = """\
name: artifacts-test-corpus
version: 1
language: de
genre: Literary Fiction
chapters: [ch-01, ch-02]
"""

CHAPTER_TEXT = "# Kapitel Eins\n\nDer Wald lag still im ersten Licht.\n"

GROUNDED_EXCERPT = "Der Wald lag still im ersten Licht."


def _strength() -> dict[str, str | None]:
    return {
        "category": "prose",
        "title": "Controlled cadence",
        "description": "The sentences carry the scene.",
        "text_excerpt": GROUNDED_EXCERPT,
    }


def _feedback() -> dict[str, str | None]:
    return {
        "category": "pacing",
        "severity": "moderate",
        "title": "Dragging middle section",
        "description": "The middle repeats its beats.",
        "text_excerpt": GROUNDED_EXCERPT,
    }


def _write_corpus(root: Path) -> Path:
    (root / "clean" / "chapters").mkdir(parents=True)
    (root / "corpus.yaml").write_text(MANIFEST, encoding="utf-8")
    for stem in ("ch-01", "ch-02"):
        (root / "clean" / "chapters" / f"{stem}.md").write_text(CHAPTER_TEXT, encoding="utf-8")
    return root


def make_case(
    stem: str = "ch-01",
    *,
    dry_run: bool = False,
    feedback_count: int = 5,
    strength_count: int = 3,
    system_prompt: str = "SYSTEM ONE",
) -> EvalCaseResult:
    args = make_phase1_args(
        strengths=[_strength() for _ in range(strength_count)],
        feedback=[_feedback() for _ in range(feedback_count)],
    )
    phase1 = build_phase1(args)
    phase2 = build_phase2(make_phase2_args())
    return EvalCaseResult(
        stem=stem,
        system_prompt=system_prompt,
        user_prompt="USER ONE",
        deepdive_system_prompt="SYSTEM TWO",
        deepdive_user_prompt="USER TWO",
        deepdive_category="plot",
        dry_run=dry_run,
        call_count=0 if dry_run else 2,
        phase1=None if dry_run else phase1,
        phase2=None if dry_run else phase2,
        layer1_phase1=None if dry_run else check_phase1(phase1, CHAPTER_TEXT),
        layer1_phase2=None if dry_run else check_phase2(phase2, CHAPTER_TEXT),
    )


def make_document(
    cases: list[EvalCaseResult], *, run_id: str = "2026-09-14-cafe123-1"
) -> ManifestDocument:
    return ManifestDocument(
        run_id=run_id,
        created_at="2026-09-14T12:00:00+00:00",
        git_commit="cafe1234",
        dry_run=all(case.dry_run for case in cases),
        corpus=CorpusView(
            name="artifacts-test-corpus",
            version=1,
            language="de",
            genre="Literary Fiction",
            chapters=[case.stem for case in cases],
        ),
        prompt_versions={"beta_reader": "1.1.0", "beta_reader_deepdive": "1.1.0"},
        model=ModelView(provider="zai", model_id="glm-5.3-flash", temperature=0.0, max_tokens=4096),
        config_fingerprint=FingerprintView(
            provider="zai", model="glm-5.3-flash", config_hash="sha256:" + "0" * 64
        ),
        cli_args={"chapter": "ch-01", "all": False},
        call_count=sum(case.call_count for case in cases),
        known_gaps=list(KNOWN_GAPS),
    )


def make_render_input(cases: list[EvalCaseResult], manifest: EvalCorpusManifest) -> RunRenderInput:
    return RunRenderInput(manifest=manifest, cases=cases, document=make_document(cases))


@pytest.fixture
def manifest(tmp_path: Path) -> EvalCorpusManifest:
    return load_eval_corpus(_write_corpus(tmp_path / "corpus"))


class TestNextEvalRunId:
    def test_format_day_git_short_counter(self) -> None:
        assert next_eval_run_id([], "2026-09-14", "cafe123") == "2026-09-14-cafe123-1"

    def test_counter_scoped_to_day_and_commit(self) -> None:
        existing = [
            "2026-09-14-cafe123-1",
            "2026-09-13-cafe123-4",
            "2026-09-14-dead000-3",
            "summary-notes",
        ]

        run_id = next_eval_run_id(existing, "2026-09-14", "cafe123")

        assert run_id == "2026-09-14-cafe123-2"


class TestSecretSweep:
    def test_literal_api_key_blocks_before_write(self) -> None:
        files = {"ch-01__beta_reader/user_prompt.txt": "context api_key=supersecret99 more"}

        with pytest.raises(ArtifactError, match=r"user_prompt\.txt"):
            secret_sweep(files, secrets=["supersecret99"])

    def test_bearer_token_blocks(self) -> None:
        files = {"a.txt": "Authorization: Bearer abcdef123456"}

        with pytest.raises(ArtifactError, match="Bearer"):
            secret_sweep(files)

    def test_provider_key_shape_blocks(self) -> None:
        files = {"a.txt": "context sk-abcdefghijklmnop12"}

        with pytest.raises(ArtifactError, match="sk-"):
            secret_sweep(files)

    def test_clean_artifacts_pass(self) -> None:
        files = {
            "manifest.json": '{"model": {"provider": "zai"}, "call_count": 2}',
            "summary.md": "# Summary\n\n| counts | strengths=3 |",
        }

        secret_sweep(files, secrets=["supersecret99"])  # must not raise


class TestConfigFingerprint:
    def test_excludes_api_key(self) -> None:
        base = EvalLlmConfig.model_validate(
            {"provider": "zai", "api_key": "key-one", "model": "glm", "zai_endpoint": "general"}
        )
        other = EvalLlmConfig.model_validate(
            {"provider": "zai", "api_key": "key-two", "model": "glm", "zai_endpoint": "general"}
        )

        assert config_fingerprint(base) == config_fingerprint(other)

    def test_differs_per_model_and_is_sha256(self) -> None:
        base = EvalLlmConfig.model_validate(
            {"provider": "zai", "api_key": "key-one", "model": "glm", "zai_endpoint": "general"}
        )
        other = EvalLlmConfig.model_validate(
            {"provider": "zai", "api_key": "key-one", "model": "other", "zai_endpoint": "general"}
        )

        first = config_fingerprint(base)
        assert first.config_hash.startswith("sha256:")
        assert len(first.config_hash) == len("sha256:") + 64
        assert first.config_hash != config_fingerprint(other).config_hash


class TestRenderRunPayload:
    def test_full_run_tree_with_four_files_per_phase(self, manifest: EvalCorpusManifest) -> None:
        files = render_run_payload(make_render_input([make_case()], manifest))

        for name in (
            "manifest.json",
            "summary.md",
            "rating.md",
            "ch-01__beta_reader/system_prompt.txt",
            "ch-01__beta_reader/user_prompt.txt",
            "ch-01__beta_reader/response.json",
            "ch-01__beta_reader/layer1.json",
            "ch-01__beta_reader_deepdive/system_prompt.txt",
            "ch-01__beta_reader_deepdive/user_prompt.txt",
            "ch-01__beta_reader_deepdive/response.json",
            "ch-01__beta_reader_deepdive/layer1.json",
        ):
            assert name in files, f"missing artifact {name}"

    def test_dry_run_writes_prompts_only(self, manifest: EvalCorpusManifest) -> None:
        files = render_run_payload(make_render_input([make_case(dry_run=True)], manifest))

        assert "ch-01__beta_reader/system_prompt.txt" in files
        assert "ch-01__beta_reader_deepdive/user_prompt.txt" in files
        assert not any(name.endswith("response.json") for name in files)
        assert not any(name.endswith("layer1.json") for name in files)

    def test_manifest_is_secret_free(self, manifest: EvalCorpusManifest) -> None:
        files = render_run_payload(make_render_input([make_case()], manifest))

        document = json.loads(files["manifest.json"])
        assert document["run_id"] == "2026-09-14-cafe123-1"
        assert document["dry_run"] is False
        assert document["call_count"] == 2
        assert document["corpus"]["genre"] == "Literary Fiction"
        assert document["known_gaps"] == list(KNOWN_GAPS)
        assert "api_key" not in files["manifest.json"]
        assert all("supersecret99" not in content for content in files.values())

    def test_prompt_files_are_verbatim(self, manifest: EvalCorpusManifest) -> None:
        files = render_run_payload(make_render_input([make_case()], manifest))

        assert files["ch-01__beta_reader/system_prompt.txt"] == "SYSTEM ONE"
        assert files["ch-01__beta_reader_deepdive/user_prompt.txt"] == "USER TWO"

    def test_missing_phase_output_is_loud(self, manifest: EvalCorpusManifest) -> None:
        case = make_case().model_copy(update={"dry_run": False, "phase1": None})

        with pytest.raises(ArtifactError, match="phase1"):
            render_run_payload(make_render_input([case], manifest))

    def test_duplicate_stems_raise_before_any_write(self, manifest: EvalCorpusManifest) -> None:
        """Render is pure in-memory — a failure cannot leave a partial tree."""
        cases = [make_case("ch-01"), make_case("ch-01")]

        with pytest.raises(ArtifactError, match="ch-01"):
            render_run_payload(make_render_input(cases, manifest))

    def test_summary_and_rating_cover_each_case(self, manifest: EvalCorpusManifest) -> None:
        files = render_run_payload(
            make_render_input([make_case(), make_case("ch-02", dry_run=True)], manifest)
        )

        assert files["summary.md"].count("ch-01 x") == 2
        assert "ch-02 x" in files["summary.md"]
        assert "dry run" in files["summary.md"].lower()
        for dimension in (
            "Genre calibration",
            "Severity discipline",
            "False-positive impression",
            "Craft-actionability",
        ):
            assert dimension in files["rating.md"]
        assert "regression | improvement | parity | inconclusive" in files["rating.md"]
        assert "grounding" in files["rating.md"].lower()


class TestWriteRun:
    def test_atomic_tree_without_leftovers(self, tmp_path: Path) -> None:
        out = tmp_path / "runs"

        run_dir = write_run(
            out,
            "2026-09-14-cafe123-1",
            {
                "manifest.json": "{}",
                "ch-01__beta_reader/system_prompt.txt": "S",
            },
        )

        written = sorted(
            p.relative_to(run_dir).as_posix() for p in run_dir.rglob("*") if p.is_file()
        )
        assert written == ["ch-01__beta_reader/system_prompt.txt", "manifest.json"]
        assert not any(p.name.startswith(".") for p in run_dir.rglob("*"))

    def test_run_dir_collision_fails_loudly(self, tmp_path: Path) -> None:
        write_run(tmp_path, "run-1", {"a.txt": "x"})

        with pytest.raises(FileExistsError):
            write_run(tmp_path, "run-1", {"a.txt": "y"})


class TestPromptVersions:
    def test_reads_bundled_template_frontmatter(self) -> None:
        versions = prompt_versions(("beta_reader", "beta_reader_deepdive"))

        assert versions == {"beta_reader": "1.1.0", "beta_reader_deepdive": "1.1.0"}


def _write_rendered_run(
    tmp_path: Path,
    run_id: str,
    manifest: EvalCorpusManifest,
    case: EvalCaseResult,
) -> None:
    files = render_run_payload(make_render_input([case], manifest))
    document = make_document([case], run_id=run_id)
    files["manifest.json"] = render_run_payload(
        RunRenderInput(manifest=manifest, cases=[case], document=document)
    )["manifest.json"]
    write_run(tmp_path, run_id, files)


class TestDiffReport:
    def test_byte_delta_violations_and_metrics(
        self, tmp_path: Path, manifest: EvalCorpusManifest
    ) -> None:
        _write_rendered_run(tmp_path, "run-a", manifest, make_case(feedback_count=5))
        _write_rendered_run(
            tmp_path,
            "run-b",
            manifest,
            make_case(feedback_count=6, strength_count=2, system_prompt="SYSTEM ONE LONGER"),
        )

        report = render_diff_report(tmp_path, "run-a", "run-b")

        assert "run-a" in report and "run-b" in report
        assert "| system | 10 | 17 | +7 |" in report
        assert "| feedback | 5 | 6 | +1 |" in report
        assert "L1-P1-count-strengths" in report
        assert "run-a/ch-01__beta_reader" in report
        assert "run-b/ch-01__beta_reader" in report

    def test_case_missing_in_one_run_is_flagged(
        self, tmp_path: Path, manifest: EvalCorpusManifest
    ) -> None:
        _write_rendered_run(tmp_path, "run-a", manifest, make_case())
        _write_rendered_run(tmp_path, "run-b", manifest, make_case(stem="ch-02"))

        report = render_diff_report(tmp_path, "run-a", "run-b")

        assert "missing in run-b" in report
        assert "missing in run-a" in report

    def test_unknown_run_fails_loudly(self, tmp_path: Path) -> None:
        with pytest.raises(ArtifactError, match="run-x"):
            render_diff_report(tmp_path, "run-x", "run-y")
