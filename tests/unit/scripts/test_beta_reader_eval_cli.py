"""Unit tests for the beta-reader eval CLI (spec 2026-09-14 §9 Slice 3).

Scope: parse-level defaults, exit-code-2 misuse guards (unknown chapter /
category, ``--chapter`` + ``--all``), the diff mode (pure munging, zero LLM
calls), and the dry-run end-to-end path with a TestModel-seam factory that
pins ZERO model calls while producing a complete, placeholder-free artifact
tree. No LLM (RULE-01b); real runs are manual CLI acts (spec §8).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import pytest
from scripts.evals.beta_reader_eval import build_parser, main
from scripts.evals.corpus_source import load_eval_corpus

if TYPE_CHECKING:
    from pathlib import Path

MANIFEST = """\
name: cli-test-corpus
version: 1
language: de
genre: Literary Fiction
chapters: [ch-01, ch-02]
"""

CHAPTER_TEXT = "# Kapitel Eins\n\nDer Wald lag still im ersten Licht.\n"

LLM_YAML = """\
llm:
  provider: zai
  api_key: supersecret99
  model: glm-5.3-flash
  zai_endpoint: general
"""


def _write_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    corpus = tmp_path / "corpus"
    (corpus / "clean" / "chapters").mkdir(parents=True)
    (corpus / "corpus.yaml").write_text(MANIFEST, encoding="utf-8")
    for stem in ("ch-01", "ch-02"):
        (corpus / "clean" / "chapters" / f"{stem}.md").write_text(CHAPTER_TEXT, encoding="utf-8")
    config = tmp_path / "config.local.yaml"
    config.write_text(LLM_YAML, encoding="utf-8")
    return corpus, config, tmp_path / "runs"


@pytest.fixture
def fixture_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path]:
    corpus, config, out = _write_fixture(tmp_path)
    monkeypatch.setattr("scripts.evals.corpus_source.DEFAULT_CORPUS_ROOT", corpus)
    monkeypatch.setattr("scripts.evals.beta_reader_runner.DEFAULT_LLM_CONFIG_PATH", config)
    return corpus, config, out


def never_called_factory() -> Any:
    """Model seam that fails the test if the dry-run path ever calls a model."""

    class ExplodingFactory:
        def __init__(self) -> None:
            self.configs: list[Any] = []

        async def __call__(self, config: Any) -> Any:
            self.configs.append(config)
            raise AssertionError("dry-run must not prepare any model")

    return ExplodingFactory()


def frozen_clock() -> datetime:
    return datetime(2026, 9, 14, 12, 0, 0, tzinfo=UTC)


class TestParseDefaults:
    def test_defaults_match_spec(self) -> None:
        args = build_parser().parse_args([])

        assert args.chapter is None
        assert args.all is False
        assert args.temperature == 0.0
        assert args.category == "plot"
        assert args.dry_run is False
        assert args.diff is None
        assert args.out.endswith("scripts/evals/runs/beta-reader")

    def test_flags_parse(self) -> None:
        args = build_parser().parse_args(
            ["--all", "--temperature", "0.3", "--category", "prose", "--dry-run"]
        )

        assert args.all is True
        assert args.temperature == 0.3
        assert args.category == "prose"
        assert args.dry_run is True

    def test_diff_consumes_two_run_ids(self) -> None:
        args = build_parser().parse_args(["--diff", "run-a", "run-b"])

        assert args.diff == ["run-a", "run-b"]


class TestCliMisuse:
    def test_unknown_category_exits_2(self) -> None:
        assert main(["--category", "tone"]) == 2

    def test_chapter_and_all_exits_2(self, fixture_paths: tuple[Path, Path, Path]) -> None:
        assert main(["--chapter", "ch-01", "--all"]) == 2

    def test_unknown_chapter_exits_2(self, fixture_paths: tuple[Path, Path, Path]) -> None:
        assert main(["--chapter", "ch-99"]) == 2


class TestDiffMode:
    def test_diff_mode_writes_report_with_zero_model_calls(
        self, fixture_paths: tuple[Path, Path, Path]
    ) -> None:
        _, _, out = fixture_paths
        self._seed_runs(out)

        code = main(["--diff", "2026-09-14-cafe123-1", "2026-09-14-cafe123-2", "--out", str(out)])

        assert code == 0
        report = out / "diff-2026-09-14-cafe123-1-vs-2026-09-14-cafe123-2" / "diff_report.md"
        assert report.is_file()
        assert "2026-09-14-cafe123-1" in report.read_text(encoding="utf-8")

    @staticmethod
    def _seed_runs(out: Path) -> None:
        from scripts.evals.beta_reader_artifacts import (
            RunRenderInput,
            render_run_payload,
            write_run,
        )
        from scripts.evals.corpus_source import EvalChapter, EvalCorpusManifest

        from tests.unit.scripts.test_beta_reader_artifacts import make_case, make_document

        chapter = EvalChapter(stem="ch-01", title="Kapitel Eins", text=CHAPTER_TEXT, word_count=9)
        manifest = EvalCorpusManifest(
            name="cli-test-corpus",
            version=1,
            language="de",
            genre="Literary Fiction",
            chapters=[chapter],
        )
        for n in (1, 2):
            case = make_case(feedback_count=4 + n)
            document = make_document([case], run_id=f"2026-09-14-cafe123-{n}")
            data = RunRenderInput(manifest=manifest, cases=[case], document=document)
            write_run(out, f"2026-09-14-cafe123-{n}", render_run_payload(data))


class TestDryRunEndToEnd:
    def test_zero_model_calls_and_complete_tree(
        self, fixture_paths: tuple[Path, Path, Path]
    ) -> None:
        _, _, out = fixture_paths
        factory = never_called_factory()

        code = main(
            [
                "--dry-run",
                "--chapter",
                "ch-01",
                "--out",
                str(out),
            ],
            model_factory=factory,
            git_short_provider=lambda: "cafe123",
            clock=frozen_clock,
        )

        assert code == 0
        assert factory.configs == []  # 0 model calls, pinned
        run_dir = out / "2026-09-14-cafe123-1"
        expected = [
            "manifest.json",
            "summary.md",
            "rating.md",
            "ch-01__beta_reader/system_prompt.txt",
            "ch-01__beta_reader/user_prompt.txt",
            "ch-01__beta_reader_deepdive/system_prompt.txt",
            "ch-01__beta_reader_deepdive/user_prompt.txt",
        ]
        for rel in expected:
            assert (run_dir / rel).is_file(), f"missing artifact {rel}"
        assert not list(run_dir.rglob("response.json"))
        assert not list(run_dir.rglob("layer1.json"))

    def test_manifest_records_dry_run_and_no_secret(
        self, fixture_paths: tuple[Path, Path, Path]
    ) -> None:
        _, _, out = fixture_paths

        main(
            ["--dry-run", "--out", str(out)],
            model_factory=never_called_factory(),
            git_short_provider=lambda: "cafe123",
            clock=frozen_clock,
        )

        document = json.loads(
            (out / "2026-09-14-cafe123-1" / "manifest.json").read_text(encoding="utf-8")
        )
        assert document["dry_run"] is True
        assert document["call_count"] == 0
        assert document["model"]["temperature"] == 0.0
        # Manifest records the corpus identity (spec §6) — not the selection.
        assert document["corpus"]["chapters"] == ["ch-01", "ch-02"]
        blob = "".join(p.read_text(encoding="utf-8") for p in out.rglob("*") if p.is_file())
        assert "supersecret99" not in blob
        assert "api_key" not in document

    def test_counter_increments_per_run(self, fixture_paths: tuple[Path, Path, Path]) -> None:
        _, _, out = fixture_paths
        kwargs: dict[str, Any] = {
            "model_factory": never_called_factory(),
            "git_short_provider": lambda: "cafe123",
            "clock": frozen_clock,
        }

        assert main(["--dry-run", "--out", str(out)], **kwargs) == 0
        assert main(["--dry-run", "--out", str(out), "--all"], **kwargs) == 0

        assert (out / "2026-09-14-cafe123-1").is_dir()
        assert (out / "2026-09-14-cafe123-2").is_dir()
        second = json.loads(
            (out / "2026-09-14-cafe123-2" / "manifest.json").read_text(encoding="utf-8")
        )
        assert second["corpus"]["chapters"] == ["ch-01", "ch-02"]

    def test_summary_reports_dry_run(self, fixture_paths: tuple[Path, Path, Path]) -> None:
        _, _, out = fixture_paths

        main(
            ["--dry-run", "--out", str(out)],
            model_factory=never_called_factory(),
            git_short_provider=lambda: "cafe123",
            clock=frozen_clock,
        )

        summary = (out / "2026-09-14-cafe123-1" / "summary.md").read_text(encoding="utf-8")
        assert "dry run" in summary.lower()
        assert "0" in summary  # llm calls total


class TestCorpusFixture:
    def test_fixture_corpus_loads(self, fixture_paths: tuple[Path, Path, Path]) -> None:
        corpus, _, _ = fixture_paths

        manifest = load_eval_corpus(corpus)

        assert [chapter.stem for chapter in manifest.chapters] == ["ch-01", "ch-02"]
