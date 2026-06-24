#!/usr/bin/env python3
"""ADR-048 Mode 2 declaration validation and placeholder evidence rejection.

Single responsibility (RULE-06): validate that:
1. Mode 2 (agent-internal) services have registered ManualInjectionDeclarations
   in the adoption registry.
2. Evidence records do not contain placeholder prompts (the deprecated
   ``safe_record_evidence()`` placeholder ``[analysis-kb-invocation]`` /
   ``[direct-agent-call]``).

This module reads the adoption registry YAML and evidence JSONL files
(RULE-07: platform reads files/reports, not runtime internals).

See:
    ADR-048 (Platform Specialist tasks),
    ADR-045 (Runtime Adoption Enforcement).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from pathlib import Path

#: Maximum number of Mode 2 declarations before an audit hint is triggered
#: (ADR-048 Q1 decision: Mode 2 is an exception, not a default).
_MODE2_AUDIT_THRESHOLD = 5

#: The known placeholder prompt from the deprecated ``safe_record_evidence()``.
_PLACEHOLDER_SYSTEM = "[analysis-kb-invocation]"
_PLACEHOLDER_USER = "[direct-agent-call]"

#: ADR-045 fingerprint domain separator (must match correlation.py).
_FINGERPRINT_DOMAIN = "narrare:adr045:v1"


def _compute_placeholder_fingerprint() -> str:
    """Compute the SHA-256 digest of the known placeholder prompt."""
    payload = {
        "domain": _FINGERPRINT_DOMAIN,
        "payload": {
            "system": _PLACEHOLDER_SYSTEM,
            "user": _PLACEHOLDER_USER,
            "first_message": None,
        },
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


#: Pre-computed SHA-256 digest of the placeholder prompt.
_PLACEHOLDER_FINGERPRINT = _compute_placeholder_fingerprint()


@dataclass(frozen=True)
class Mode2ValidationFinding:
    """A single finding from Mode 2 / placeholder evidence validation."""

    severity: str  # "critical" | "warning" | "info"
    code: str
    message: str
    detail: str = ""


@dataclass
class Mode2ValidationReport:
    """Aggregated Mode 2 validation report."""

    findings: list[Mode2ValidationFinding] = field(default_factory=list[Mode2ValidationFinding])

    @property
    def has_critical(self) -> bool:
        return any(f.severity == "critical" for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == "warning" for f in self.findings)

    @property
    def critical_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "critical")

    @property
    def warning_count(self) -> int:
        return sum(1 for f in self.findings if f.severity == "warning")


def validate_mode2_declarations(
    registry: dict[str, Any],
) -> list[Mode2ValidationFinding]:
    """Validate Mode 2 declarations in the adoption registry.

    Checks:
    - Each declaration has required fields (reason, variables, injection_mechanism).
    - ``reason`` is at least 10 characters.
    - ``variables`` is non-empty.
    - ``injection_mechanism`` is a known mechanism.
    - If >5 declarations exist, emit an audit hint (warning).

    Args:
        registry: Parsed adoption-registry.yaml as a dict.

    Returns:
        List of findings (critical for invalid declarations, warning for audit hint).
    """
    findings: list[Mode2ValidationFinding] = []
    declarations = cast("dict[str, Any]", registry.get("manual_injection_declarations", {}))

    if not declarations:
        return findings

    valid_mechanisms = {
        "agent_deps",
        "capability_dynamic_instructions",
        "agent_instructions_decorator",
    }

    for mode_key, decl in declarations.items():
        if not isinstance(decl, dict):
            findings.append(
                Mode2ValidationFinding(
                    severity="critical",
                    code="MODE2_INVALID_DECLARATION",
                    message=f"Mode 2 declaration for '{mode_key}' is not a mapping",
                    detail=str(decl),
                )
            )
            continue

        decl_typed = cast("dict[str, Any]", decl)

        # Check required fields.
        reason = decl_typed.get("reason")
        if not isinstance(reason, str) or len(reason) < 10:
            findings.append(
                Mode2ValidationFinding(
                    severity="critical",
                    code="MODE2_MISSING_REASON",
                    message=f"Mode 2 declaration for '{mode_key}' missing or short reason",
                    detail=f"reason: {reason!r}",
                )
            )

        variables = decl_typed.get("variables")
        if not isinstance(variables, list) or len(cast("list[Any]", variables)) < 1:
            findings.append(
                Mode2ValidationFinding(
                    severity="critical",
                    code="MODE2_MISSING_VARIABLES",
                    message=f"Mode 2 declaration for '{mode_key}' missing or empty variables",
                    detail=f"variables: {variables!r}",
                )
            )

        mechanism = decl_typed.get("injection_mechanism")
        if not isinstance(mechanism, str) or mechanism not in valid_mechanisms:
            findings.append(
                Mode2ValidationFinding(
                    severity="critical",
                    code="MODE2_INVALID_MECHANISM",
                    message=f"Mode 2 declaration for '{mode_key}' has invalid injection_mechanism",
                    detail=f"mechanism: {mechanism!r}, valid: {valid_mechanisms}",
                )
            )

    # Q1 audit hint: >5 Mode 2 declarations.
    if len(declarations) > _MODE2_AUDIT_THRESHOLD:
        findings.append(
            Mode2ValidationFinding(
                severity="warning",
                code="MODE2_AUDIT_THRESHOLD_EXCEEDED",
                message=(
                    f"{len(declarations)} Mode 2 declarations exceed "
                    f"the audit threshold of {_MODE2_AUDIT_THRESHOLD} "
                    f"(ADR-048 Q1: Mode 2 is an exception, not a default)"
                ),
            )
        )

    return findings


def check_placeholder_evidence(
    evidence_dir: Path | None = None,
) -> list[Mode2ValidationFinding]:
    """Check evidence records for placeholder prompts.

    Scans ``invocations.jsonl`` (or marker JSON files) for records whose
    ``prompt_fingerprint`` matches the known placeholder digest, or whose
    system/user fields contain the deprecated placeholder strings.

    Args:
        evidence_dir: Path to ``.evidence/`` directory. If None, returns empty.

    Returns:
        List of critical findings for each placeholder evidence record found.
    """
    if evidence_dir is None:
        return []

    findings: list[Mode2ValidationFinding] = []
    evidence_file = evidence_dir / "invocations.jsonl"

    if not evidence_file.exists():
        return findings

    placeholder_count = 0
    with evidence_file.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(record, dict):
                continue

            record_typed = cast("dict[str, Any]", record)

            # Check by fingerprint digest.
            fp = record_typed.get("prompt_fingerprint")
            if isinstance(fp, str) and fp == _PLACEHOLDER_FINGERPRINT:
                placeholder_count += 1
                continue

            # Check by raw prompt content (some legacy records may carry it).
            system = record_typed.get("system_prompt") or record_typed.get("system")
            user = record_typed.get("user_prompt") or record_typed.get("user")
            if (
                isinstance(system, str)
                and system == _PLACEHOLDER_SYSTEM
                and isinstance(user, str)
                and user == _PLACEHOLDER_USER
            ):
                placeholder_count += 1

    if placeholder_count > 0:
        findings.append(
            Mode2ValidationFinding(
                severity="critical",
                code="PLACEHOLDER_EVIDENCE_FOUND",
                message=(
                    f"{placeholder_count} evidence record(s) contain the deprecated "
                    f"placeholder prompt ({_PLACEHOLDER_SYSTEM}/{_PLACEHOLDER_USER}). "
                    f"Placeholder evidence cannot satisfy runtime adoption (ADR-048)."
                ),
                detail=f"Expected fingerprint: {_PLACEHOLDER_FINGERPRINT}",
            )
        )

    return findings


def validate_adoption_mode2(
    registry: dict[str, Any],
    evidence_dir: Path | None = None,
) -> Mode2ValidationReport:
    """Run all Mode 2 / placeholder evidence validations.

    Args:
        registry: Parsed adoption-registry.yaml as a dict.
        evidence_dir: Optional path to ``.evidence/`` directory.

    Returns:
        :class:`Mode2ValidationReport` with all findings.
    """
    findings: list[Mode2ValidationFinding] = []
    findings.extend(validate_mode2_declarations(registry))
    findings.extend(check_placeholder_evidence(evidence_dir))
    return Mode2ValidationReport(findings=findings)
