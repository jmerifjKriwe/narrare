"""Run artifacts for the beta-reader eval instrument.

Spec: ``docs/superpowers/specs/2026-09-14-beta-reader-eval-design.md`` — §6
(D4) and §9 Slice 3. All content is rendered in memory BEFORE any file is
created — a render/validation failure leaves the runs root untouched (no
partial artifact trees); each file writes through a temporary file +
``os.replace`` (atomic per file). Semantics replicated from
``benchmark/artifacts.py`` — deliberately NOT imported (spec §3 boundary:
zero code coupling to ``benchmark/``).

Run id: ``YYYY-MM-DD-<git-short>-<n>`` — ``n`` is the next free counter over
the runs-root listing for that day+commit prefix (deterministic, no
timestamps inside the id); a colliding run directory fails loudly (mkdir
without ``exist_ok``).

Secret hygiene (spec §6): the api key exists in-process only; artifacts
carry provider/model ids + a fingerprint hash. Belt-and-braces: a
secret-pattern sweep (provider key shapes, ``Bearer …``, ``api_key``
assignments, the literal key value) runs over every rendered artifact
before the first file lands — any hit aborts the run.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess  # nosec B404 — fixed internal argv, no shell
from pathlib import Path
from typing import TYPE_CHECKING, Final, cast

from pydantic import BaseModel, ConfigDict
from scripts.evals.beta_reader_runner import (
    PHASE1_MODE,
    PHASE2_MODE,
    EvalCaseResult,
    EvalLlmConfig,
)
from scripts.evals.beta_reader_scoring import Layer1Report
from scripts.evals.corpus_source import EvalCorpusManifest  # noqa: TC002  # runtime: pydantic field

from narrare_core.llm import LLMIntent
from narrare_core.prompts.registry import PromptRegistry
from narrare_core.prompts.routes import resolve_prompt_route
from narrare_core.shared.frontmatter import parse_frontmatter

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from scripts.evals.beta_reader_scoring import Layer1Report

__all__ = [
    "DEFAULT_OUT_ROOT",
    "KNOWN_GAPS",
    "ArtifactError",
    "CorpusView",
    "FingerprintView",
    "ManifestDocument",
    "ModelView",
    "RunRenderInput",
    "config_fingerprint",
    "current_git_short",
    "next_eval_run_id",
    "phase_metrics",
    "prompt_versions",
    "render_run_payload",
    "secret_sweep",
    "write_run",
]

#: Default runs root (spec §6/D4; gitignored via ``scripts/evals/runs/``).
DEFAULT_OUT_ROOT: Path = (
    Path(__file__).resolve().parents[2] / "scripts" / "evals" / "runs" / "beta-reader"
)

#: Documented fidelity gaps vs production (spec §4 steps 2/4 — recorded
#: per-run in ``manifest.known_gaps``).
KNOWN_GAPS: tuple[str, ...] = (
    "no KB envelopes (kb_characters/kb_locations empty; production renders "
    "them via the DB-backed ContextAssembler)",
    "no previous-chapter summaries (production provides them via the ContextAssembler)",
    "fixed 32k assembler budget instead of the model-window-aware cascade "
    "(ADR-082; immaterial at single-chapter scale)",
)

_VERDICT_OPTIONS: Final[str] = "regression | improvement | parity | inconclusive"
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
_GIT: Final[Path | str] = shutil.which("git") or "git"
_SEGMENT: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_BEARER: Final[re.Pattern[str]] = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{8,}")
_SK_KEY: Final[re.Pattern[str]] = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}")
_KEY_ASSIGNMENT: Final[re.Pattern[str]] = re.compile(
    r"(?i)\bapi[_-]?key\b\s*[:=]\s*['\"]?[^\s'\"]{8,}"
)
_SEVERITY_ORDER: Final[tuple[str, ...]] = ("critical", "moderate", "minor")
_OVERALL_KEYS: Final[tuple[str, ...]] = (
    "reader_engagement",
    "emotional_impact",
    "pacing_score",
    "prose_quality",
    "plot_progression",
    "character_development",
)

_RUBRIC: Final[tuple[tuple[str, str], ...]] = (
    (
        "Genre calibration",
        "Does the feedback prioritize per the manifest genre? (Literary Fiction: "
        "prose quality, interiority, thematic resonance, contemplative pacing)",
    ),
    (
        "Severity discipline",
        "Are critical/moderate/minor applied per the template definitions, or inflated/deflated?",
    ),
    (
        "False-positive impression",
        "Do flagged issues hold up against the chapter? (cross-read the grounding "
        "fraction printed in the block)",
    ),
    (
        "Craft-actionability",
        "Are suggestions concretely implementable (the template's 'immediately' standard)?",
    ),
)


class ArtifactError(ValueError):
    """Raised when rendering, sweeping, or writing run artifacts fails."""


# ---------------------------------------------------------------------------
# Typed contracts (RULE-03)
# ---------------------------------------------------------------------------


class CorpusView(BaseModel):
    """Corpus identity block of the manifest (never carries secrets)."""

    model_config = ConfigDict(frozen=True)

    name: str
    version: int
    language: str
    genre: str
    chapters: list[str]


class ModelView(BaseModel):
    """Model block of the manifest — ids/numbers only, NEVER the api key."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model_id: str
    temperature: float
    max_tokens: int


class FingerprintView(BaseModel):
    """provider/model + hash over the REDACTED llm section (no secrets)."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    config_hash: str


class ManifestDocument(BaseModel):
    """The run manifest (spec §6): identity, versions, model, cli, gaps."""

    model_config = ConfigDict(frozen=True)

    run_id: str
    created_at: str
    git_commit: str
    dry_run: bool
    corpus: CorpusView
    prompt_versions: dict[str, str]
    model: ModelView
    config_fingerprint: FingerprintView
    cli_args: dict[str, object]
    call_count: int
    known_gaps: list[str]


class RunRenderInput(BaseModel):
    """Everything one run's artifact tree is rendered from."""

    model_config = ConfigDict(frozen=True)

    manifest: EvalCorpusManifest
    cases: list[EvalCaseResult]
    document: ManifestDocument


# ---------------------------------------------------------------------------
# Run identity + fingerprints + template versions
# ---------------------------------------------------------------------------


def next_eval_run_id(existing: Sequence[str], day: str, git_short: str) -> str:
    """``YYYY-MM-DD-<git-short>-<n>`` with n = max existing suffix + 1 (pure)."""
    prefix = f"{day}-{git_short}-"
    numbers = [
        int(suffix)
        for name in existing
        if (suffix := name.removeprefix(prefix)) and suffix.isdigit()
    ]
    return f"{prefix}{max(numbers, default=0) + 1}"


def current_git_short() -> str:
    """Production git provider: ``git rev-parse --short=8 HEAD`` (no shell)."""
    completed = subprocess.run(  # noqa: S603  # nosec B603 — fixed internal argv, no shell
        [_GIT, "rev-parse", "--short=8", "HEAD"],
        cwd=_REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise ArtifactError(
            f"git rev-parse failed (rc={completed.returncode}): {completed.stderr.strip()}"
        )
    return completed.stdout.strip()


def config_fingerprint(llm_config: EvalLlmConfig) -> FingerprintView:
    """SHA-256 over the REDACTED llm section's canonical JSON (spec §6)."""
    redacted = llm_config.model_dump(exclude={"api_key"})
    canonical = json.dumps(redacted, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return FingerprintView(
        provider=llm_config.provider, model=llm_config.model, config_hash=f"sha256:{digest}"
    )


def prompt_versions(modes: Sequence[str]) -> dict[str, str]:
    """Template frontmatter ``prompt_version`` per mode (spec §11-4).

    Bundled templates are authoritative in the eval (no DB overrides); the
    route resolution keeps the category path governed instead of hardcoded.
    """
    bundled_root = PromptRegistry().bundled_root
    versions: dict[str, str] = {}
    for mode in modes:
        route = resolve_prompt_route(LLMIntent.BETA_READ, mode)
        path = bundled_root / route.category / "en" / route.mode / "system.md"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise ArtifactError(f"bundled template for {mode!r}: unreadable ({exc})") from exc
        versions[mode] = str(parse_frontmatter(text).metadata.get("prompt_version", "0.0.0"))
    return versions


# ---------------------------------------------------------------------------
# Secret sweep (spec §6 — aborts BEFORE the first file lands)
# ---------------------------------------------------------------------------


def secret_sweep(files: Mapping[str, str], *, secrets: Sequence[str] = ()) -> None:
    """Raise :class:`ArtifactError` on the first secret hit in any artifact."""
    for name in sorted(files):
        content = files[name]
        for secret in secrets:
            if len(secret) >= 8 and secret in content:
                raise ArtifactError(f"secret sweep hit in {name}: literal secret value")
        for pattern, label in (
            (_BEARER, "Bearer token"),
            (_SK_KEY, "provider key shape (sk-…)"),
            (_KEY_ASSIGNMENT, "api_key assignment"),
        ):
            if (hit := pattern.search(content)) is not None:
                raise ArtifactError(f"secret sweep hit in {name}: {label} ({hit.group(0)!r})")


# ---------------------------------------------------------------------------
# In-memory render (failures here never touch the runs root)
# ---------------------------------------------------------------------------


def render_run_payload(data: RunRenderInput) -> dict[str, str]:
    """Render ALL files in memory; any failure happens before a write."""
    _validate(data)
    files = {"manifest.json": _dumps(data.document.model_dump(mode="json"))}
    for case in data.cases:
        files.update(_case_files(case))
    files["summary.md"] = _render_summary(data)
    files["rating.md"] = _render_rating(data)
    return files


def _validate(data: RunRenderInput) -> None:
    known = {chapter.stem for chapter in data.manifest.chapters}
    for case in data.cases:
        if case.stem not in known:
            raise ArtifactError(f"case stem {case.stem!r} is not in the corpus manifest")
    stems = [case.stem for case in data.cases]
    if len(set(stems)) != len(stems):
        raise ArtifactError(f"duplicate case stems in one run: {stems}")


def _dumps(document: object) -> str:
    return json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)


def _case_files(case: EvalCaseResult) -> dict[str, str]:
    phase1 = case.phase1
    phase2 = case.phase2
    layer1_phase1 = case.layer1_phase1
    layer1_phase2 = case.layer1_phase2
    files = {
        f"{case.stem}__{PHASE1_MODE}/system_prompt.txt": case.system_prompt,
        f"{case.stem}__{PHASE1_MODE}/user_prompt.txt": case.user_prompt,
        f"{case.stem}__{PHASE2_MODE}/system_prompt.txt": case.deepdive_system_prompt,
        f"{case.stem}__{PHASE2_MODE}/user_prompt.txt": case.deepdive_user_prompt,
    }
    if case.dry_run:
        # Placeholder-free capture (spec §6): prompts only, nothing fabricated.
        return files
    if phase1 is None or layer1_phase1 is None:
        raise ArtifactError(f"case {case.stem}: non-dry-run result missing phase1 output")
    if phase2 is None or layer1_phase2 is None:
        raise ArtifactError(f"case {case.stem}: non-dry-run result missing phase2 output")
    files[f"{case.stem}__{PHASE1_MODE}/response.json"] = _dumps(phase1.model_dump(mode="json"))
    files[f"{case.stem}__{PHASE1_MODE}/layer1.json"] = _layer1_doc(layer1_phase1)
    files[f"{case.stem}__{PHASE2_MODE}/response.json"] = _dumps(phase2.model_dump(mode="json"))
    files[f"{case.stem}__{PHASE2_MODE}/layer1.json"] = _layer1_doc(layer1_phase2)
    return files


def _layer1_doc(report: Layer1Report) -> str:
    return _dumps(
        {
            "phase": report.phase,
            "passed": report.passed,
            "violations": [violation.model_dump() for violation in report.violations],
            "grounding": report.grounding.model_dump() if report.grounding else None,
        }
    )


def _render_summary(data: RunRenderInput) -> str:
    header = [
        f"# Beta-Reader Eval Summary — {data.document.run_id}",
        "",
        f"created: {data.document.created_at} · git: {data.document.git_commit} · "
        f"llm calls: {data.document.call_count} · "
        f"{'dry run' if data.document.dry_run else 'real run'}",
        f"chapters: {', '.join(data.document.corpus.chapters)}",
        "",
    ]
    body: list[str] = []
    for case in data.cases:
        body += _case_block(case, PHASE1_MODE)
        body += _case_block(case, PHASE2_MODE)
    return "\n".join(header + body)


def _case_block(case: EvalCaseResult, mode: str) -> list[str]:
    lines = [f"## {case.stem} x {mode}", ""]
    report = case.layer1_phase1 if mode == PHASE1_MODE else case.layer1_phase2
    output = case.phase1 if mode == PHASE1_MODE else case.phase2
    if report is None or output is None:
        return [*lines, "- layer1: n/a (dry run — no model output)", ""]
    metrics = phase_metrics(mode, output.model_dump(mode="json"))
    counts = [
        key
        for key in metrics
        if not key.startswith("sev_") and key not in _OVERALL_KEYS and key != "category_score"
    ]
    severities = [key for key in metrics if key.startswith("sev_")]
    lines.append("- counts: " + " · ".join(f"{key}={metrics[key]}" for key in counts))
    lines.append(
        "- severity: "
        + " · ".join(f"{key.removeprefix('sev_')}={metrics[key]}" for key in severities)
    )
    if mode == PHASE2_MODE:
        lines.append(f"- category_score: {metrics['category_score']}")
    else:
        lines.append("- overall: " + " · ".join(f"{key}={metrics[key]}" for key in _OVERALL_KEYS))
    lines.append(_grounding_line(report))
    violations = [
        f"  - {violation.check_id}: {violation.detail}" for violation in report.violations
    ]
    lines.append(f"- violations ({len(report.violations)}):")
    lines += violations if violations else ["  - (none)"]
    lines.append("")
    return lines


def _grounding_line(report: Layer1Report) -> str:
    grounding = report.grounding
    if grounding is None or grounding.fraction is None:
        return "- grounding: n/a (no excerpts)"
    return f"- grounding: {grounding.grounded}/{grounding.total} ({grounding.fraction:.2f})"


def _render_rating(data: RunRenderInput) -> str:
    lines = [
        f"# PO Rating — {data.document.run_id}",
        "",
        "Ground truth: rate every dimension 1-5 with one evidence line each,",
        "then record the verdict. The template is yours to edit in place.",
        "",
    ]
    for case in data.cases:
        for mode in (PHASE1_MODE, PHASE2_MODE):
            lines += _rating_block(case, mode)
    lines += [
        "## Overall",
        "",
        f"Run verdict ({_VERDICT_OPTIONS}):",
        "Compared against run:",
        "Notes:",
        "",
    ]
    return "\n".join(lines)


def _rating_block(case: EvalCaseResult, mode: str) -> list[str]:
    report = case.layer1_phase1 if mode == PHASE1_MODE else case.layer1_phase2
    grounding_line = (
        _grounding_line(report).replace("- grounding", "grounding (auto)")
        if report is not None
        else "grounding (auto): n/a (dry run — no model output)"
    )
    lines = [f"## {case.stem} x {mode}", "", grounding_line, ""]
    for index, (name, question) in enumerate(_RUBRIC, start=1):
        lines += [f"{index}. {name}: __ /5", f"   Evidence: ({question})", ""]
    lines += [f"Verdict ({_VERDICT_OPTIONS}):", "Compared against run:", ""]
    return lines


# ---------------------------------------------------------------------------
# Metric projections (shared by summary + diff)
# ---------------------------------------------------------------------------


def _severity_distribution(rows: list[dict[str, object]]) -> dict[str, int]:
    counts = {f"sev_{severity}": 0 for severity in _SEVERITY_ORDER}
    for row in rows:
        key = f"sev_{row.get('severity')}"
        counts[key] = counts.get(key, 0) + 1
    return counts


def phase_metrics(mode: str, response: dict[str, object]) -> dict[str, int]:
    """Flat metric→int projection over one phase's response document."""
    if mode == PHASE2_MODE:
        suggestions = cast("list[object]", response["revision_suggestions"])
        feedback = cast("list[dict[str, object]]", response["detailed_feedback"])
        return {
            "detailed_feedback": len(feedback),
            "revision_suggestions": len(suggestions),
            "category_score": int(cast("int", response["category_score"])),
            **_severity_distribution(feedback),
        }
    strengths = cast("list[object]", response["strengths"])
    feedback = cast("list[dict[str, object]]", response["feedback"])
    questions = cast("list[object]", response["questions"])
    overall = cast("dict[str, object]", response["overall"])
    return {
        "strengths": len(strengths),
        "feedback": len(feedback),
        "questions": len(questions),
        **_severity_distribution(feedback),
        **{key: int(cast("int", overall[key])) for key in _OVERALL_KEYS},
    }


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------


def write_run(out_dir: Path, run_id: str, files: Mapping[str, str]) -> Path:
    """Create ``<out_dir>/<run_id>`` (loud on collision) and write atomically."""
    if not run_id or not _SEGMENT.fullmatch(run_id):
        raise ArtifactError(f"run_id {run_id!r} is not a safe path segment")
    out_dir.mkdir(parents=True, exist_ok=True)
    run_dir = out_dir / run_id
    run_dir.mkdir()  # collision → loud FileExistsError, never exist_ok
    for rel in sorted(files):
        target = run_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, files[rel])
    return run_dir


def _atomic_write(path: Path, content: str) -> None:
    """Write via temp file + rename — a reader never sees a partial file."""
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)
