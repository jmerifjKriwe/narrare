#!/usr/bin/env python3
"""Beta-reader mini-eval CLI — manual, cost-bounded instrument driver.

Spec: ``docs/superpowers/specs/2026-09-14-beta-reader-eval-design.md`` —
§6 (D8), §8, §9 Slice 3.

Usage (spec §8):

    uv run python -m scripts.evals.beta_reader_eval \
        [--chapter ch-01] [--all] \
        [--category plot] \
        [--temperature 0.0] \
        [--dry-run] \
        [--out scripts/evals/runs/beta-reader] \
        [--diff RUN_A RUN_B]

Cost guard: the default run is 1 chapter x 2 phases = 2 LLM calls; ``--all``
opts into the full corpus (24 calls — the estimate is printed before any
execution); ``--dry-run`` composes prompts and writes artifacts with ZERO
LLM calls (free prompt-regression capture). Never pytest-driven (spec §8):
unit tests use the injectable ``model_factory`` seam only; real runs are
manual CLI acts.

Exit codes (spec §5 semantics): ``0`` run completed (Layer-1 violations may
exist — they are measurements, not crashes); ``1`` harness failure
(corpus/config/compose/invocation/artifact — RULE-11, never silent); ``2``
CLI misuse.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

# Ensure project root is on sys.path so `scripts.evals` resolves (probes
# style, spec §8: direct script invocation, no `just` recipe in v1).
_project_root = str(Path(__file__).resolve().parents[2])
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import structlog  # noqa: E402
from scripts.evals.beta_reader_artifacts import (  # noqa: E402
    DEFAULT_OUT_ROOT,
    KNOWN_GAPS,
    ArtifactError,
    CorpusView,
    ManifestDocument,
    ModelView,
    RunRenderInput,
    config_fingerprint,
    current_git_short,
    next_eval_run_id,
    prompt_versions,
    render_run_payload,
    secret_sweep,
    write_run,
)
from scripts.evals.beta_reader_diff import render_and_write_diff  # noqa: E402
from scripts.evals.beta_reader_runner import (  # noqa: E402
    DEFAULT_DEEPDIVE_CATEGORY,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    MODEL_FACTORY,
    PHASE1_MODE,
    PHASE2_MODE,
    BetaReaderEvalRunner,
    EvalConfigError,
    EvalLlmConfig,
    load_llm_config,
)
from scripts.evals.beta_reader_scoring import CATEGORIES  # noqa: E402
from scripts.evals.corpus_source import (  # noqa: E402
    CorpusSourceError,
    EvalCorpusManifest,
    load_eval_corpus,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

    from scripts.evals.beta_reader_runner import EvalCaseResult
    from scripts.evals.corpus_source import EvalChapter

__all__ = ["DEFAULT_CHAPTER", "build_parser", "main"]

logger = structlog.get_logger(__name__)

DEFAULT_CHAPTER: str = "ch-01"


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface (spec §8 flags; exit 2 on misuse via argparse)."""
    parser = argparse.ArgumentParser(
        prog="scripts.evals.beta_reader_eval",
        description="Beta-reader mini-eval — manual instrument (spec 2026-09-14).",
    )
    parser.add_argument(
        "--chapter", default=None, help=f"corpus chapter stem (default: {DEFAULT_CHAPTER})"
    )
    parser.add_argument("--all", action="store_true", help="run the full corpus (24 LLM calls)")
    parser.add_argument(
        "--temperature", type=float, default=DEFAULT_TEMPERATURE, help="pinned temperature"
    )
    parser.add_argument(
        "--category",
        default=DEFAULT_DEEPDIVE_CATEGORY,
        help=f"phase-2 deep-dive category (default: {DEFAULT_DEEPDIVE_CATEGORY})",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="compose + artifacts with zero LLM calls"
    )
    parser.add_argument("--out", default=str(DEFAULT_OUT_ROOT), help="runs root directory")
    parser.add_argument("--diff", nargs=2, metavar=("RUN_A", "RUN_B"), help="render diff report")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    model_factory: MODEL_FACTORY | None = None,
    git_short_provider: Callable[[], str] | None = None,
    clock: Callable[[], datetime] | None = None,
) -> int:
    """CLI entry point. Injectable seams exist for unit tests only."""
    args = build_parser().parse_args(argv)
    if args.category not in CATEGORIES:
        print(
            f"error: unknown deep-dive category {args.category!r} (allowed: {sorted(CATEGORIES)})",
            file=sys.stderr,
        )
        return 2
    if args.all and args.chapter is not None:
        print("error: --all and --chapter are mutually exclusive", file=sys.stderr)
        return 2
    if args.diff is not None:
        return _run_diff(Path(args.out), args.diff[0], args.diff[1])
    return _run_eval(
        args,
        model_factory=model_factory,
        git_short_provider=git_short_provider or current_git_short,
        clock=clock or _default_clock,
    )


def _run_diff(out_root: Path, run_a: str, run_b: str) -> int:
    """``--diff`` mode: pure local munging of two prior run trees."""
    try:
        target = render_and_write_diff(out_root, run_a, run_b)
    except ArtifactError as exc:
        logger.error("eval_diff_failed", error=str(exc))
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"diff report: {target}")
    return 0


def _run_eval(
    args: argparse.Namespace,
    *,
    model_factory: MODEL_FACTORY | None,
    git_short_provider: Callable[[], str],
    clock: Callable[[], datetime],
) -> int:
    """Corpus → chain → artifacts (spec §4 chain, §6 artifacts)."""
    try:
        manifest = load_eval_corpus()
    except CorpusSourceError as exc:
        return _fail("corpus load failed", exc)
    selected = _select_chapters(manifest, args)
    if selected is None:
        return 2
    try:
        llm_config = load_llm_config()
    except EvalConfigError as exc:
        return _fail("llm config load failed", exc)
    estimate = 0 if args.dry_run else 2 * len(selected)
    print(
        f"plan: {len(selected)} chapter(s) x 2 phases = {estimate} LLM calls "
        f"(dry_run={args.dry_run})"
    )
    try:
        runner = BetaReaderEvalRunner(
            manifest=manifest,
            llm_config=llm_config,
            temperature=args.temperature,
            deepdive_category=args.category,
            model_factory=model_factory,
        )
    except EvalConfigError as exc:
        return _fail("runner construction failed", exc)
    try:
        cases = asyncio.run(_execute(runner, selected, dry_run=args.dry_run))
    except Exception as exc:  # harness boundary: loud, never silent (RULE-11)
        logger.error("eval_run_failed", error=str(exc))
        print(f"error: eval run failed: {exc}", file=sys.stderr)
        return 1
    try:
        run_dir = _write_artifacts(args, manifest, cases, llm_config, git_short_provider, clock)
    except (ArtifactError, OSError) as exc:
        return _fail("artifact render/write failed", exc)
    _print_result(run_dir, cases, dry_run=args.dry_run)
    return 0


async def _execute(
    runner: BetaReaderEvalRunner,
    chapters: Sequence[EvalChapter],
    *,
    dry_run: bool,
) -> list[EvalCaseResult]:
    cases: list[EvalCaseResult] = []
    for chapter in chapters:
        cases.append(await runner.run_case(chapter, dry_run=dry_run))
    return cases


def _write_artifacts(
    args: argparse.Namespace,
    manifest: EvalCorpusManifest,
    cases: Sequence[EvalCaseResult],
    llm_config: EvalLlmConfig,
    git_short_provider: Callable[[], str],
    clock: Callable[[], datetime],
) -> Path:
    """Render in memory → secret sweep → atomic write (spec §6 ordering)."""
    now = clock()
    out_root = Path(args.out)
    existing = sorted(entry.name for entry in out_root.iterdir()) if out_root.is_dir() else []
    git_short = git_short_provider()
    run_id = next_eval_run_id(existing, now.date().isoformat(), git_short)
    document = ManifestDocument(
        run_id=run_id,
        created_at=now.isoformat(),
        git_commit=git_short,
        dry_run=args.dry_run,
        corpus=CorpusView(
            name=manifest.name,
            version=manifest.version,
            language=manifest.language,
            genre=manifest.genre,
            chapters=[chapter.stem for chapter in manifest.chapters],
        ),
        prompt_versions=prompt_versions((PHASE1_MODE, PHASE2_MODE)),
        model=ModelView(
            provider=llm_config.provider,
            model_id=llm_config.model,
            temperature=args.temperature,
            max_tokens=DEFAULT_MAX_TOKENS,
        ),
        config_fingerprint=config_fingerprint(llm_config),
        cli_args={
            "chapter": args.chapter,
            "all": args.all,
            "category": args.category,
            "temperature": args.temperature,
            "dry_run": args.dry_run,
            "out": str(args.out),
        },
        call_count=sum(case.call_count for case in cases),
        known_gaps=list(KNOWN_GAPS),
    )
    files = render_run_payload(
        RunRenderInput(manifest=manifest, cases=list(cases), document=document)
    )
    secret_sweep(files, secrets=[llm_config.api_key])
    return write_run(out_root, run_id, files)


def _print_result(run_dir: Path, cases: Sequence[EvalCaseResult], *, dry_run: bool) -> None:
    print(f"run complete: {run_dir}")
    for rel in sorted(
        path.relative_to(run_dir).as_posix() for path in run_dir.rglob("*") if path.is_file()
    ):
        print(f"  {rel}")
    if dry_run:
        print("dry run: 0 LLM calls — Layer-1 self-scores require a real run")
        return
    for case in cases:
        for label, report in (
            (PHASE1_MODE, case.layer1_phase1),
            (PHASE2_MODE, case.layer1_phase2),
        ):
            if report is None:
                continue
            grounding = report.grounding
            fraction = (
                "n/a"
                if grounding is None or grounding.fraction is None
                else f"{grounding.fraction:.2f}"
            )
            status = "PASS" if report.passed else f"{len(report.violations)} violations"
            print(f"L1 {case.stem} x {label}: {status} (grounding {fraction})")
            for violation in report.violations:
                print(f"  - {violation.check_id}: {violation.detail}")


def _select_chapters(
    manifest: EvalCorpusManifest, args: argparse.Namespace
) -> list[EvalChapter] | None:
    if args.all:
        return list(manifest.chapters)
    stem = args.chapter or DEFAULT_CHAPTER
    chapter = next((item for item in manifest.chapters if item.stem == stem), None)
    if chapter is None:
        print(
            f"error: unknown chapter {stem!r} "
            f"(corpus chapters: {[item.stem for item in manifest.chapters]})",
            file=sys.stderr,
        )
        return None
    return [chapter]


def _fail(message: str, exc: Exception) -> int:
    logger.error(message, error=str(exc))
    print(f"error: {message}: {exc}", file=sys.stderr)
    return 1


def _default_clock() -> datetime:
    return datetime.now(UTC)


if __name__ == "__main__":
    raise SystemExit(main())
