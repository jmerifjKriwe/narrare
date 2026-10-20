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
    # Every command uses `uv run --all-packages`: the repo root is a virtual
    # uv workspace, so a plain `uv run` only syncs the root dev-group closure
    # and can leave workspace-member deps stale (see justfile gate note). The
    # exception is the Architecture step, which runs the `just check-architecture`
    # recipe; that recipe passes the same flag on every one of its lines.
    steps: list[Step] = [
        Step(
            "Architecture",
            [
                # Single source of the architecture surface: the canonical
                # `just check-architecture` recipe (its own entry point, also
                # what `just verify`'s `check` step reaches). This step used to
                # restate the same scripts and the two lists drifted apart —
                # the recipe and CI gained `generate_provider_catalog.py
                # --check` (throughput T7) while this step did not, so the
                # documented local gate stayed green on a stale provider
                # catalog (T8b review F2). Running the recipe means a future
                # architecture check is added in exactly one place. `just` is
                # the documented entry point for this gate (`just check` is
                # `uv run --all-packages python scripts/run_checks.py`), so the
                # binary is present whenever the runner is used as documented.
                (["just", "check-architecture"], None),
            ],
        ),
        Step(
            "Lint & Format",
            [
                (
                    [
                        "uv",
                        "run",
                        "--all-packages",
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
                        "--all-packages",
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
                (["uv", "run", "--all-packages", "pyright"], None),
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
                    [
                        "uv",
                        "run",
                        "--all-packages",
                        "pyright",
                        "--project",
                        "tests/pyrightconfig.json",
                    ],
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
                        "--all-packages",
                        "bandit",
                        "-c",
                        "pyproject.toml",
                        "-r",
                        "apps/api/narrare",
                        "packages/core/narrare_core",
                    ],
                    None,
                ),
                (["uv", "run", "--all-packages", "pip-audit"], None),
            ],
        ),
        Step(
            "Model Registry",
            [
                (
                    [
                        "uv",
                        "run",
                        "--all-packages",
                        "python",
                        "scripts/check_model_registry.py",
                    ],
                    None,
                ),
            ],
        ),
        Step(
            "Prompts",
            [
                (
                    [
                        "uv",
                        "run",
                        "--all-packages",
                        "python",
                        "scripts/check_prompt_structure.py",
                    ],
                    None,
                ),
                # ADR-056 — runtime-evidence-aware adoption gate (matches
                # `just check-adoption` and CI). Reads committed .evidence markers.
                (
                    [
                        "uv",
                        "run",
                        "--all-packages",
                        "python",
                        "scripts/check_adoption.py",
                        "--evidence-dir",
                        ".evidence",
                    ],
                    None,
                ),
                (
                    [
                        "uv",
                        "run",
                        "--all-packages",
                        "python",
                        "scripts/check_streaming_compliance.py",
                    ],
                    None,
                ),
            ],
        ),
    ]

    if web.is_dir() and (web / "package.json").exists():
        steps.extend(
            [
                # RULE-04 TS/TSX file-size gate — same script + invocation as
                # `just check-architecture`, the pre-commit hook and the CI
                # frontend job. Own step (before lint, mirroring CI order) so
                # size drift is reported as size, not mislabeled as lint.
                # It also runs inside the delegated Architecture step above
                # (the recipe owns the script); the own step is kept so drift
                # still gets its labeled summary line, at the cost of one extra
                # run of that script per gate.
                Step(
                    "Frontend Size",
                    [
                        (
                            [
                                "uv",
                                "run",
                                "--all-packages",
                                "python",
                                "scripts/check_frontend_file_size.py",
                            ],
                            None,
                        ),
                    ],
                ),
                Step(
                    "Frontend Lint",
                    [
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
