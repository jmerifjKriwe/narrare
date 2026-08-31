"""CLI entry point: ``python -m benchmark`` (plan Task 15).

Two subcommands:

- ``run`` — one full benchmark run (variant/mode selection, optional
  capability filter, artifact output root, keep-stack debug flag); the
  orchestration itself lives in ``benchmark.runner`` — this module only
  parses arguments, loads the config, and renders the outcome/errors;
- ``stack up|down|status`` — debug convenience to operate the compose
  stack WITHOUT a run (each command tears down/verifies like a run
  would; ``status`` reports whether the project's services run).

Exit codes: 0 success, 1 failure (message on stderr — the failure
artifacts of a failed run carry the details), 2 argparse usage errors.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from benchmark.config import load_config
from benchmark.config_schemas import CONFIG_PATH
from benchmark.runner import DEFAULT_OUT_DIR, RunnerDeps, RunRequest, run
from benchmark.stack import StackManager

if TYPE_CHECKING:
    from collections.abc import Sequence

    from benchmark.config_schemas import BenchmarkConfig

__all__ = ["build_parser", "main"]


def build_parser() -> argparse.ArgumentParser:
    """The CLI surface (English help, brief-pinned flags/defaults)."""
    parser = argparse.ArgumentParser(
        prog="benchmark",
        description=(
            "KB benchmark runner — spins up its own Narrare stack, ingests the "
            "corpus, drives the capability surface, scores, writes artifacts, "
            "and tears the stack down residue-free (manually-only area, ADR-083)."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    run_command = commands.add_parser(
        "run",
        help=(
            "Execute one benchmark run: stack → provision → ingest → "
            "drive → score → artifacts → teardown."
        ),
    )
    run_command.add_argument(
        "--variant",
        required=True,
        help=(
            "Corpus variant to run: 'clean' or a registry variant "
            "(see benchmark/corpus/corpus.yaml)."
        ),
    )
    run_command.add_argument(
        "--mode",
        choices=("incremental", "import"),
        default="incremental",
        help=(
            "Ingest pacing mode; import = same build path without "
            "inter-chapter waits (default: incremental)."
        ),
    )
    run_command.add_argument(
        "--keep-stack",
        action="store_true",
        help="Skip stack teardown after the run (debugging; leaves containers/volumes behind).",
    )
    run_command.add_argument(
        "--capabilities",
        default="",
        help="Comma-separated capability ids to drive (default: all 26 registry entries).",
    )
    run_command.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT_DIR,
        help=f"Directory for run artifacts (default: {DEFAULT_OUT_DIR}).",
    )
    run_command.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="Path to the local benchmark config YAML (gitignored).",
    )

    stack_command = commands.add_parser(
        "stack",
        help="Debug the compose stack without a run (up | down | status).",
    )
    stack_command.add_argument("action", choices=("up", "down", "status"))
    stack_command.add_argument(
        "--config",
        type=Path,
        default=CONFIG_PATH,
        help="Path to the local benchmark config YAML (gitignored).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI boundary: parse, load config, dispatch; errors → exit code 1."""
    args = build_parser().parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == "run":
            request = RunRequest(
                variant=args.variant,
                mode=args.mode,
                out_dir=args.out,
                config=config,
                keep_stack=args.keep_stack,
                capabilities=_parse_capabilities(args.capabilities),
            )
            paths = run(request, RunnerDeps())
            print(f"run complete: artifacts in {paths.run_dir}")
        else:
            _stack_command(args.action, config)
        return 0
    except Exception as error:
        print(f"benchmark: error: {error}", file=sys.stderr)
        return 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_capabilities(raw: str) -> tuple[str, ...]:
    """``"CAP-IN-01, CAP-OUT-01"`` → ids (empties dropped, order kept)."""
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _stack_command(action: str, config: BenchmarkConfig) -> None:
    """Debug stack operations — same lifecycle guarantees as a run."""
    stack = StackManager(config)
    if action == "up":
        print(f"stack up: {stack.up()}")
    elif action == "down":
        stack.teardown()
        print("stack down (residue verified)")
    else:
        print("stack is up" if stack.is_up() else "stack is down")


if __name__ == "__main__":
    raise SystemExit(main())
