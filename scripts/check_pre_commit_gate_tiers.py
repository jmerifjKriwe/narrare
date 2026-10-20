#!/usr/bin/env python3
"""Pin the pre-commit hook tiering (throughput T8 decisions, T9 ratchet).

``.pre-commit-config.yaml`` expresses three hook tiers in prose plus stage
declarations: whole-project hooks that belong at ``pre-push``, score/adoption
hooks that only run on demand (``manual``), and the commit-message validator
(``commit-msg``). Nothing stopped a later edit from moving a slow hook back
into the commit path or parking a fast one where it never runs.

This gate machine-pins that tiering. It parses the config text (no I/O, no git)
and reports one line per violation:

* every hook id in ``PUSH_ONLY`` must declare exactly ``stages: [pre-push]``;
* every hook id in ``MANUAL_ONLY`` must declare exactly ``stages: [manual]``;
* every hook id in ``COMMIT_MSG_ONLY`` must declare exactly ``stages: [commit-msg]``;
* no other hook may declare ``pre-push`` (that is how a new hook would
  silently join the push tier);
* a hook id may appear only once — a duplicate could carry two stage
  declarations and satisfy every rule above while one copy still runs at commit;
* a hook in any tier set must exist — deleting a slow hook must not satisfy the
  ratchet.

Usage:
    python scripts/check_pre_commit_gate_tiers.py [path/to/config]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, cast

import yaml

PUSH_ONLY: frozenset[str] = frozenset(
    {"pyright", "pyright-tests", "bandit", "openapi-regenerate", "typecheck-frontend"}
)
MANUAL_ONLY: frozenset[str] = frozenset({"adoption-score"})
COMMIT_MSG_ONLY: frozenset[str] = frozenset({"conventional-commits"})

DEFAULT_CONFIG_PATH = ".pre-commit-config.yaml"

# stage -> the exact hook ids that must run at that stage (and only there)
_STAGE_TIERS: tuple[tuple[str, frozenset[str]], ...] = (
    ("pre-push", PUSH_ONLY),
    ("manual", MANUAL_ONLY),
    ("commit-msg", COMMIT_MSG_ONLY),
)


def _hooks_by_id(config_text: str) -> dict[str, list[dict[str, Any]]]:
    """Index every hook of every repo in the config by its id."""
    config = cast("dict[str, Any]", yaml.safe_load(config_text) or {})
    hooks: dict[str, list[dict[str, Any]]] = {}
    for repo in cast("list[Any]", config.get("repos") or []):
        for hook in cast("list[Any]", cast("dict[str, Any]", repo).get("hooks") or []):
            hook_id = str(cast("dict[str, Any]", hook).get("id", ""))
            hooks.setdefault(hook_id, []).append(cast("dict[str, Any]", hook))
    return hooks


def _declared_stages(hook: dict[str, Any]) -> set[str]:
    """Return the stages a hook declares; an absent key means pre-commit default."""
    stages: Any = hook.get("stages")
    if not stages:
        return set()
    if isinstance(stages, str):
        return {stages}
    if isinstance(stages, list):
        return {str(stage) for stage in cast("list[Any]", stages)}
    return set()


def _format_stages(stages: set[str]) -> str:
    return "[" + ", ".join(sorted(stages)) + "]" if stages else "no stages key"


def find_tier_violations(config_text: str) -> list[str]:
    """Return one human-readable line per hook-tiering violation."""
    hooks = _hooks_by_id(config_text)
    violations: list[str] = []

    for hook_id, occurrences in sorted(hooks.items()):
        if len(occurrences) > 1:
            violations.append(
                f"duplicate hook id '{hook_id}': declared {len(occurrences)} times — "
                "a duplicate could carry two stage declarations"
            )

    for stage, tier in _STAGE_TIERS:
        for hook_id in sorted(tier):
            occurrences = hooks.get(hook_id)
            if not occurrences:
                violations.append(
                    f"missing hook '{hook_id}': the {stage} tier requires it to exist"
                )
                continue
            declared = _declared_stages(occurrences[0])
            if declared != {stage}:
                violations.append(
                    f"'{hook_id}': declares {_format_stages(declared)}, "
                    f"the {stage} tier requires [{stage}]"
                )

    pinned: set[str] = {hook_id for _, tier in _STAGE_TIERS for hook_id in tier}
    for hook_id, occurrences in sorted(hooks.items()):
        if hook_id not in pinned and "pre-push" in _declared_stages(occurrences[0]):
            violations.append(
                f"'{hook_id}': declares pre-push but is not in the push tier — "
                "a new whole-project hook must be a conscious tier change"
            )

    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "config",
        nargs="?",
        default=DEFAULT_CONFIG_PATH,
        help=f"pre-commit config to check (default: {DEFAULT_CONFIG_PATH})",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    try:
        config_text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"::error:: cannot read {config_path}: {exc}", file=sys.stderr)
        return 1
    try:
        violations = find_tier_violations(config_text)
    except yaml.YAMLError as exc:
        print(f"::error:: {config_path} is not valid YAML: {exc}", file=sys.stderr)
        return 1

    if violations:
        print(f"❌ pre-commit hook tiering: {len(violations)} violation(s) in {config_path}")
        for violation in violations:
            print(f"  - {violation}")
        return 1
    print(f"✅ pre-commit hook tiering matches the pinned tiers ({config_path})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
