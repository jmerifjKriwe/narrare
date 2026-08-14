#!/usr/bin/env python3
"""
Step definitions for the Narrare quality-check runner.

Pure declaration of *what* gets checked — the ``Step`` data model and the
``build_steps`` step list — separated from *how* steps are executed and
reported (which lives in :mod:`run_checks`). Extracted so that
``run_checks.py`` stays under the RULE-04 line limit (modularize, not
compress). ``run_checks.py`` imports :data:`ROOT`, :class:`Step` and
:func:`build_steps` from here; nothing in this module depends on the
runner, so the dependency direction is one-way (no import cycle).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Step:
    """One logical check step (may run multiple commands)."""

    label: str
    commands: list[tuple[list[str], Path | None]]  # (cmd, cwd)


# ── Step definitions ──────────────────────────────────────────


def build_steps() -> list[Step]:
    web = ROOT / "packages" / "web"
    steps: list[Step] = [
        Step(
            "Architecture",
            [
                (["uv", "run", "python", "scripts/check_architecture.py"], None),
                (["uv", "run", "python", "scripts/check_exception_baseline.py"], None),
                (["uv", "run", "python", "scripts/check_python_file_size.py"], None),
                (["uv", "run", "python", "scripts/check_prompt_surface_contract.py"], None),
                (["uv", "run", "python", "scripts/check_empty_kb_vars.py"], None),
                (["uv", "run", "python", "scripts/check_frontmatter_schema.py"], None),
                # Mutation-inert convention — prevents the MutMut sandbox crash
                # class documented in issue #146 (asset-reading tests reached
                # via parents[N] must carry @pytest.mark.mutation_inert).
                (
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/checks/check_mutation_inert_assets.py",
                    ],
                    None,
                ),
            ],
        ),
        Step(
            "Lint & Format",
            [
                (
                    [
                        "uv",
                        "run",
                        "ruff",
                        "check",
                        "apps/",
                        "packages/",
                        "scripts/",
                        "tests/",
                        "evals/",
                    ],
                    None,
                ),
                (
                    [
                        "uv",
                        "run",
                        "ruff",
                        "format",
                        "--check",
                        "apps/",
                        "packages/",
                        "scripts/",
                        "tests/",
                        "evals/",
                    ],
                    None,
                ),
            ],
        ),
        Step(
            "Typecheck",
            [
                (["uv", "run", "pyright"], None),
            ],
        ),
        Step(
            "Typecheck (Tests)",
            [
                # The main pyright config (pyproject.toml) excludes tests/ for
                # performance (~1k test files); test files are type-checked
                # separately by tests/pyrightconfig.json (basic mode). Surface
                # it in the `check` gate so test-file type errors are caught
                # before commit — not only by the pre-commit `pyright-tests`
                # hook (Q-015-Q-019 gate-coverage follow-up).
                (
                    ["uv", "run", "pyright", "--project", "tests/pyrightconfig.json"],
                    None,
                ),
            ],
        ),
        Step(
            "Security",
            [
                (
                    [
                        "uv",
                        "run",
                        "bandit",
                        "-c",
                        "pyproject.toml",
                        "-r",
                        "apps/api/narrare",
                        "packages/core/narrare_core",
                    ],
                    None,
                ),
                (["uv", "run", "pip-audit"], None),
            ],
        ),
        Step(
            "Model Registry",
            [
                (["uv", "run", "python", "scripts/check_model_registry.py"], None),
            ],
        ),
        Step(
            "Prompts",
            [
                (["uv", "run", "python", "scripts/check_prompt_structure.py"], None),
                # ADR-056 — runtime-evidence-aware adoption gate (matches
                # `just check-adoption` and CI). Reads committed .evidence markers.
                (
                    [
                        "uv",
                        "run",
                        "python",
                        "scripts/check_adoption.py",
                        "--evidence-dir",
                        ".evidence",
                    ],
                    None,
                ),
                (["uv", "run", "python", "scripts/check_streaming_compliance.py"], None),
            ],
        ),
    ]

    if web.is_dir() and (web / "package.json").exists():
        steps.extend(
            [
                Step(
                    "Frontend Lint",
                    [
                        (["uv", "run", "python", "scripts/check_frontend_file_size.py"], None),
                        (["pnpm", "lint:check"], web),
                    ],
                ),
                Step(
                    "i18n Validation",
                    [
                        (["npx", "tsx", "scripts/validate-i18n.ts"], None),
                    ],
                ),
                Step(
                    "Frontend Types",
                    [
                        (["pnpm", "type-check"], web),
                    ],
                ),
            ]
        )

    return steps
