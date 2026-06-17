#!/usr/bin/env python3
"""ADR-046 D.5 — Prompt-Path-Compliance adoption metric.

Reads the ``prompt_path_compliance`` section of ``adoption-registry.yaml`` and
verifies that every feature mode declares ``prompt_path_compliant: true``.

This closes root cause C.2 (Adoption Metric Gap): the adoption score previously
tracked infrastructure-wiring (probes, evidence-sinks) but not architectural
pattern conformance. ``prompt_path_compliant`` makes RULE-02b conformance a
first-class, per-intent adoption criterion.

Verification model (ADR-046 D.5):
    A mode is ``prompt_path_compliant: true`` when BOTH hold:
      1. D.1 — a ``*_prompt_path_compliance.py`` test exists for the resolving
         service (enforced by ``tests/unit/core/prompts/test_prompt_path_compliance.py``).
      2. D.2 — ``check_architecture.py`` reports 0 RULE-02b violations for the
         service module (enforced by the prompt_path / prompts / prompt_channel
         checkers).

This module enforces the *declaration*: every feature mode must be present in
``prompt_path_compliance`` and set to ``true``. The D.1/D.2 gates enforce the
*truth* of that declaration independently (defence in depth).

See:
    - ``docs/architecture/decisions/ADR-046-prompt-path-compliance.md`` § D.5
    - ``docs/_shared/CONSTRAINTS.md`` RULE-02b
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator


@dataclass(frozen=True)
class PromptPathFinding:
    """A single prompt-path-compliance adoption finding."""

    mode_key: str  # "{category}/{mode}"
    severity: str  # "critical" | "warning"
    message: str


def _iter_feature_modes(
    registry: dict[str, Any],
) -> Iterator[tuple[str, str]]:
    """Yield ``(category, mode)`` for every feature mode in the registry.

    Skips modeless categories (``modes: []``).
    """
    features: dict[str, Any] = registry.get("features", {}) or {}
    for category, cfg in features.items():
        modes: Any = cfg.get("modes", {}) or {}
        # modeless categories use an empty list
        if isinstance(modes, list):
            continue
        for mode in modes:  # type: ignore[union-attr]
            yield category, str(mode)


def check_prompt_path_adoption(
    registry: dict[str, Any],
) -> list[PromptPathFinding]:
    """Verify every feature mode declares ``prompt_path_compliant: true``.

    Returns a finding per mode that is:
    - **missing** from ``prompt_path_compliance`` (critical), or
    - declared **false** (critical), or
    - declared with a **non-boolean** value (critical).

    Also warns about entries in ``prompt_path_compliance`` that do not
    correspond to any feature mode (registry drift).
    """
    compliance: dict[str, Any] = registry.get("prompt_path_compliance", {}) or {}

    findings: list[PromptPathFinding] = []
    declared_keys: set[str] = set()

    for category, mode in _iter_feature_modes(registry):
        mode_key = f"{category}/{mode}"
        declared_keys.add(mode_key)
        if mode_key not in compliance:
            findings.append(
                PromptPathFinding(
                    mode_key=mode_key,
                    severity="critical",
                    message=(
                        "missing prompt_path_compliant declaration — "
                        "add to adoption-registry.yaml prompt_path_compliance "
                        "(set true once D.1 test + D.2 checker pass)"
                    ),
                )
            )
            continue
        value = compliance[mode_key]
        if not isinstance(value, bool):
            findings.append(
                PromptPathFinding(
                    mode_key=mode_key,
                    severity="critical",
                    message=(
                        f"prompt_path_compliant must be a boolean, got {type(value).__name__}"
                    ),
                )
            )
        elif value is not True:
            findings.append(
                PromptPathFinding(
                    mode_key=mode_key,
                    severity="critical",
                    message=(
                        "prompt_path_compliant is false — RULE-02b violation "
                        "(resolve via PromptComposer; add D.1 compliance test)"
                    ),
                )
            )

    # Drift: entries that don't map to any feature mode.
    for extra_key in sorted(set(compliance) - declared_keys):
        findings.append(
            PromptPathFinding(
                mode_key=extra_key,
                severity="warning",
                message=(
                    "prompt_path_compliance entry has no matching feature mode "
                    "(remove or add the mode to features)"
                ),
            )
        )

    return findings
