# ADR-041 — Typed Manifests / Doc-Drift Automation / Quality Metrics / Persistent Evidence

> **Status:** ✅ Accepted
> **Date:** 2026-06-07
> **Deciders:** Architecture Specialist
> **Supersedes:** —
> **Related:** ADR-038, ADR-040, ADR-032, ADR-035, INFRA-013, CONSTRAINTS.md RULE-03/RULE-04/RULE-06/RULE-07/RULE-14/RULE-20/RULE-22

---

## Context

This ADR completes the **P3 architecture specification** for the CR-03 AI Invocation
Adoption Contract (INFRA-013 §P3). P0–P2 are implemented; four long-term hardening
concerns remain:

1. **Registry drift**: `adoption-registry.yaml` (v2.0.0, 27 modes across 5 categories)
   is hand-maintained. It declares context variables, infrastructure requirements, and
   runtime requirements per mode/category. When prompt files, agent implementations, or
   context variables change without a corresponding registry update, adoption scores
   become stale. The P2 `check_kg_consistency.py` catches KG variable drift but does not
   cover infrastructure declarations, mode existence, or `requires_runtime_evidence`
   flags.

2. **Doc-drift gap**: `check_doc_drift.py` exists but only validates Node.js version
   consistency across docs and CI. It does not validate:
   - ADR status ↔ spec status alignment
   - Spec file-path references ↔ actual file existence
   - Checker terminology ↔ spec terminology (e.g., adoption states, RULE-XX names)
   - RULE-XX references ↔ canonical `CONSTRAINTS.md` text
   - ADR cross-references ↔ actual ADR file existence
   This is a governance gap: 40+ ADRs and 22 RULE-XX are manually cross-referenced.

3. **Quality metrics disconnect**: `scripts/eval_drift/` parses Pydantic Eval results
   (`EvalResultFile`, `TestCaseScore`) and compares against baselines. `core/ai_invocation/`
   produces `FeatureInvocationEvidence` at runtime. But there is **no join** between
   evaluation results and invocation evidence. A mode can have strong eval scores and
   weak runtime adoption, or vice versa, without anyone noticing.

4. **Evidence persistence**: All `FeatureInvocationEvidence` is ephemeral —
   `LoggingEvidenceSink` writes structured logs and nothing else. Evidence is not
   queryable after log rotation. The audit lifecycle (ADR-040 Decision 3) depends on
   evidence for state transitions, but `AuditReport` is CI-generated from a snapshot
   rather than queryable history.

### Current State Summary

| Concern | Exists? | Location | Gap |
|---------|---------|----------|-----|
| Adoption registry YAML | ✅ | `scripts/architecture/adoption-registry.yaml` | Hand-maintained, drift-prone |
| KG consistency checker | ✅ | `scripts/check_kg_consistency.py` | KG variables only; not full registry drift |
| Doc drift checker | ✅ | `scripts/check_doc_drift.py` | Node.js version only; not ADR/spec/RULE cross-refs |
| Eval drift parser | ✅ | `scripts/eval_drift/parser.py` | No join to invocation evidence |
| Eval drift comparison | ✅ | `scripts/eval_drift/comparison.py` | Baseline comparison; no quality metrics |
| Invocation evidence model | ✅ | `core/ai_invocation/models.py` | Frozen Pydantic; privacy-safe |
| LoggingEvidenceSink | ✅ | `core/ai_invocation/evidence/logging_sink.py` | Ephemeral only |
| AuditReport | ✅ | `scripts/adoption/audit_report.py` | CI snapshot; not queryable |
| AdoptionReport | ✅ | `scripts/adoption/scorer.py` | Static+runtime scoring |
| ModeScore | ✅ | `scripts/adoption/scorer_modes.py` | Per-mode scoring |
| Registry schema validation | ❌ | — | No schema; YAML parsed without validation |
| Doc cross-reference checker | ❌ | — | No ADR↔spec↔checker cross-validation |
| Quality metrics report | ❌ | — | No eval↔evidence join |
| Persistent evidence store | ❌ | — | No storage beyond logs |

---

## Decision Drivers

- **RULE-03**: Contracts before implementation — every new script, model, and API must
  have a defined contract.
- **RULE-04**: File size limits — modularization, not compression. New scripts must
  stay under 400 lines.
- **RULE-06**: Single responsibility — registry drift, doc drift, quality metrics, and
  evidence persistence are four separate concerns in four separate modules.
- **RULE-07**: Core → Platform dependency direction. Platform scripts never import Core
  directly — they consume structured output (JSON, logs).
- **RULE-14**: Any DB schema change requires an Alembic migration with integration tests.
- **RULE-20**: Static-only adoption is incomplete; P3 must not regress to static-only gates.
- **RULE-22**: Cross-feature coherence — quality metrics must use the same vocabulary as
  invocation evidence and adoption scoring.
- **Privacy guarantee (ADR-038)**: Evidence NEVER contains raw prompt text or user prose.
  This extends to quality metrics — no eval case content in metric reports.
- **Opt-in constraint**: Quality metrics must be opt-in, not default-on. Runtime
  overhead for observability is gated behind configuration.
- **INFRA-013 §P3 exit criteria**:
  - Registry/checker drift is automatically detected.
  - Quality metrics are opt-in, privacy-safe, and tied to evaluation contracts.
  - Persistent evidence, if added, has a storage/API contract and migration.

---

## Decision 1 — Typed Feature Manifests and Registry Drift Detection

### Options Considered

#### Option A — Generate registry from code annotations (decorators/attrs on agent/prompt classes)

Add decorators or class attributes to agent classes and prompt definitions that
auto-declare mode requirements. A generation script reads these at build time and
produces the registry YAML.

**Pros:**
- Single source of truth in code — registry is always in sync with implementation.
- Impossible for registry to drift from actual agent/prompt surfaces.
- Developer ergonomics: adding a mode is one annotation, not a YAML edit + code change.

**Cons:**
- **Violates RULE-07**: The generation script would need to import Core agent/prompt
  modules. Platform would depend on Core internals — the exact dependency that
  RULE-07 prevents.
- Requires Core modules to carry platform-level metadata (infrastructure levels,
  context variables) — mixes concerns.
- Cannot validate things that exist in registry but NOT in code (e.g., `i18n` levels,
  `inline_fallbacks`, `feature_templates`).
- Prompt template files are Markdown, not Python — annotation cannot reach them
  without a parallel mechanism.
- Breaks the current architecture where Platform is a **consumer** of evidence, not
  a **producer** of runtime configuration.

#### Option B — Typed manifest files (one per feature/mode) validated against schema

Replace the single `adoption-registry.yaml` with per-mode YAML/JSON manifest files
(e.g., `scripts/architecture/manifests/writing/new_chapter.yaml`), each validated
against a JSON Schema at CI time.

**Pros:**
- Each manifest is small and focused (RULE-06).
- JSON Schema validation catches structural errors (missing fields, wrong types).
- CI can detect orphan manifests (mode in manifests/ but not in prompts/) and missing
  manifests (prompt exists but no manifest).
- Natural scaling: adding a mode adds one file.

**Cons:**
- Explodes from 1 file to 27+ manifest files — high migration cost.
- Category-level defaults (`category_defaults` section) need a separate resolution
  mechanism (inheritance/merge).
- Feature templates and infrastructure definitions are cross-cutting — they don't
  fit per-mode files.
- Diff noise: 27 files changed when a shared field changes.
- Current `scorer.py` reads a single dict — would need aggregation logic.

#### Option C — Keep YAML but add CI schema validation + drift detection against actual prompts/code

Keep the single `adoption-registry.yaml` (it works well for 27 modes), but add:
1. A **JSON Schema** (`adoption-registry.schema.json`) that validates registry structure.
2. A **drift detection** extension to `check_kg_consistency.py` (or a new
   `check_registry_drift.py`) that compares registry declarations against actual prompt
   files, agent implementations, and variable registrations.

**Pros:**
- Minimal disruption — existing YAML stays, existing scorer/checker pipeline works.
- Schema validation catches structural drift (wrong field types, missing required fields).
- Drift detection catches semantic drift (modes declared but no prompt; variables declared
  but never used; infrastructure levels that don't match actual code).
- Fits RULE-07: drift checker reads files on disk, not Python imports.
- Incremental: schema can be added first, drift detection second.

**Cons:**
- YAML remains hand-maintained — drift is detected, not prevented.
- Schema must be kept in sync with registry format version changes.
- No developer-ergonomics improvement over status quo.

---

**Decision: Option C — Keep YAML, add schema validation + drift detection.**

### Rationale

The registry YAML is 351 lines serving 27 modes. It is not yet at a scale where
per-mode manifests justify the migration cost. The root problem is **undetected drift**,
not hand-maintenance per se. Schema validation + drift detection directly address the
root cause: they make drift visible in CI before it reaches adoption scoring.

Option A is rejected because it violates RULE-07 (Platform importing Core) and mixes
concerns (code carrying platform metadata). Option B is rejected because the migration
cost (1→27 files, new aggregation logic, category default inheritance) is not justified
for 27 modes. If the mode count exceeds 50, Option B should be reconsidered (see
Review Triggers).

### Consequences

**Positive:**
- Registry drift becomes a CI failure, not a manual audit finding.
- Schema validation is additive — existing pipeline unchanged.
- Drift detection reuses `check_kg_consistency.py` infrastructure patterns.

**Negative / Tradeoffs:**
- YAML remains hand-maintained — developers must still update it for new modes.
- Schema file adds a maintenance surface (must track registry format version).

**Constraints introduced:**
- `adoption-registry.schema.json` must validate against the current YAML structure.
- `check_registry_drift.py` must run in CI alongside `check_kg_consistency.py`.
- New modes MUST be added to the registry before CI passes (drift detection gates this).

### New Files

| File | Responsibility | Max Lines |
|------|----------------|-----------|
| `scripts/architecture/adoption-registry.schema.json` | JSON Schema for registry v2.0.0 | ~150 |
| `scripts/check_registry_drift.py` | Registry ↔ prompts/agents/variables drift detection | ~350 |

### Drift Detection Checks

`check_registry_drift.py` performs:

1. **Schema validation**: Load YAML, validate against JSON Schema. FAIL on structural
   errors.
2. **Mode existence**: For each registry mode, verify a corresponding prompt directory
   exists in `_bundled/{category}/en/{mode}/`. WARN if missing (mode may be in development).
3. **Prompt orphan detection**: For each prompt directory in `_bundled/`, verify a
   corresponding registry entry exists. FAIL if orphan prompts found (mode running
   without adoption tracking).
4. **Variable coverage**: For each registry mode's `context_variables.must`, verify
   the variable appears in at least one prompt template. WARN if missing (variable
   declared but never used).
5. **Infrastructure evidence**: For each `required_infrastructure` item, verify evidence
   logic exists in the checker (currently heuristic; FAIL if new infrastructure type
   has no evidence mapping).
6. **Runtime requirements drift**: For each mode with `requires_runtime_evidence: true`,
   cross-reference with `ModeScore.runtime_verified` from the adoption report. WARN if
   declared required but not verified.

---

## Decision 2 — Doc-Drift Automation

### Options Considered

#### Option A — Static analysis script that validates cross-references

Extend `check_doc_drift.py` with new check families that:
1. Parse ADR frontmatter (status, date, supersedes, related) and validate cross-references.
2. Parse spec frontmatter (status, contract references) and validate file existence.
3. Extract RULE-XX references from ADRs/specs and validate against `CONSTRAINTS.md`.
4. Extract checker terminology (enum values, state names) and validate against spec.

**Pros:**
- Extends existing infrastructure — `check_doc_drift.py` already has the check registry
  pattern.
- Pure text analysis — no frontmatter format enforcement.
- Incremental: add check families one at a time.

**Cons:**
- Relies on regex/text parsing of Markdown — fragile if ADR format drifts.
- No schema enforcement for ADR/spec frontmatter — format compliance is voluntary.
- Cross-reference extraction depends on consistent citation syntax.

#### Option B — Schema-validated frontmatter in docs with CI enforcement

Define YAML/JSON frontmatter schemas for ADRs and feature specs. CI validates frontmatter
against schema and checks cross-references.

**Pros:**
- Schema validation ensures consistent structure.
- Frontmatter fields are machine-parseable — no regex guessing.
- Can enforce: status is one of accepted values, date is ISO-8601, references are lists.

**Cons:**
- Requires all 40+ existing ADRs to adopt frontmatter — migration cost.
- Some ADRs use informal headers (not YAML frontmatter) — format inconsistency.
- Adds maintenance surface (schema files for ADRs, specs, checkers).

#### Option C — Both: frontmatter validation + cross-reference checker — **Chosen**

Define lightweight frontmatter expectations for ADRs and specs (status, date, related
references) while extending `check_doc_drift.py` with cross-reference check families.
Frontmatter is parsed from existing Markdown headers (not requiring a new format), and
the checker validates both structure and cross-references.

**Pros:**
- No ADR format migration — parses existing Markdown conventions.
- Cross-reference checks catch real governance gaps.
- Extends existing `check_doc_drift.py` infrastructure.
- Incremental: each check family is independently valuable.

**Cons:**
- Two categories of checks (frontmatter + cross-refs) in one script — may approach
  file size limit if many check families added.
- Markdown parsing is inherently heuristic — some ADRs may use non-standard formats.

---

**Decision: Option C — Extend `check_doc_drift.py` with frontmatter parsing + cross-reference checks.**

### Rationale

The existing `check_doc_drift.py` already has the right architecture: a check registry
with pluggable check families. Extending it is the simplest correct solution. ADR format
migration (Option B alone) is rejected because it is pure overhead without adding drift
detection — it standardizes input format but doesn't check content. Option A alone is
fragile without at least basic structure expectations. Option C combines both: it parses
existing Markdown conventions for structure and validates cross-references for content.

### Consequences

**Positive:**
- ADR↔spec↔checker cross-references are validated in CI.
- RULE-XX references are checked against the canonical `CONSTRAINTS.md`.
- Orphan docs (ADR references non-existent spec) become CI failures.

**Negative / Tradeoffs:**
- `check_doc_drift.py` grows — may need extraction of check families into a
  `doc_drift/` package if it exceeds 400 lines.
- Markdown parsing is heuristic — may need refinement for edge-case ADR formats.

**Constraints introduced:**
- New ADRs must include `Related:` references that reference existing ADR IDs.
- Feature specs must include `contract:` path that points to an existing file.
- `CONSTRAINTS.md` is the canonical RULE-XX source — no ADR may define new rules
  without updating it.

### New Check Families

Added to `check_doc_drift.py` (or extracted to `scripts/doc_drift/` if size requires):

1. **ADR Cross-Reference Integrity**:
   - Parse `Related:` line from each ADR.
   - Verify each referenced ADR file exists in `docs/architecture/decisions/`.
   - FAIL on broken references.

2. **ADR Status Consistency**:
   - Parse `Status:` line from each ADR.
   - Verify status is one of: `Proposed`, `Accepted`, `Implemented`, `Superseded`,
     `Deprecated`.
   - Verify `Supersedes:` references point to ADRs that actually exist and have status
     `Superseded` or `Deprecated`.
   - FAIL on inconsistent supersession chains.

3. **Spec File Reference Integrity**:
   - Parse `contract:` and `router:` paths from spec frontmatter.
   - Verify referenced files exist.
   - FAIL on broken file references; WARN on `null` contract/router where mode has
     runtime evidence requirements.

4. **RULE-XX Reference Validation**:
   - Extract all `RULE-XX` references from ADRs and specs.
   - Verify each `XX` exists in `CONSTRAINTS.md`.
   - FAIL on references to non-existent rules.

5. **ADR↔Spec Bidirectional Link**:
   - Verify that if an ADR references a spec (or vice versa), the referenced document
   - exists and reciprocally references back.
   - WARN on one-way references.

6. **Checker Terminology Alignment**:
   - Extract adoption state names from `scorer_modes.py`, `audit_report.py`, and
     `core/ai_invocation/_enums.py`.
   - Verify state names used in `check_adoption.py` and `check_kg_consistency.py`
     match the canonical set.
   - FAIL on terminology drift.

---

## Decision 3 — Quality Metrics Connecting Evidence to Evaluation

### Options Considered

#### Option A — New script that joins eval results with evidence logs by mode/intent

Create `scripts/check_quality_metrics.py` that:
1. Parses Pydantic Eval results from `evals/results/` (reusing `eval_drift/parser.py`).
2. Parses structured invocation evidence logs (from `LoggingEvidenceSink` output).
3. Joins by `(feature_id | mode | intent)` to produce a per-mode quality score that
   combines eval scores with adoption evidence.

**Pros:**
- Direct join between two data sources — identifies modes with strong evals but weak
  adoption, or vice versa.
- Reuses existing parsing infrastructure.
- Output can be consumed by CI gates.

**Cons:**
- Requires structured evidence logs to be parseable — log format must be stable.
- Join key (mode/intent) must match between eval results and evidence — naming
  consistency is critical.
- Log rotation means historical data is lost — cannot compute trends.
- Privacy risk: joining eval data (which may contain test case names/scores) with
  invocation data (which contains feature IDs, modes) creates a correlation surface.

#### Option B — Extend `AuditReport` to include quality metric section

Add a `quality_metrics: list[ModeQualityMetric]` section to the existing `AuditReport`
model. Each `ModeQualityMetric` contains:
- `mode: str`
- `latest_eval_score: float | None`
- `eval_drift: float | None`
- `runtime_evidence_count: int`
- `adoption_score: float`
- `quality_adoption_gap: bool` (True if eval score high but adoption score low, or vice versa)

**Pros:**
- One report for both audit lifecycle and quality metrics.
- No new script — extends existing `audit_report.py`.
- Natural CI integration — `check_adoption.py` already generates `AuditReport`.

**Cons:**
- Mixes two concerns in `AuditReport`: lifecycle tracking and quality metrics.
- `AuditReport` currently does not know about eval results — adding this creates a
  new dependency on `eval_drift/parser.py`.
- Quality metrics require eval results to exist — report generation becomes conditional
  on eval run completion.

#### Option C — Separate `QualityReport` that references both eval results and evidence — **Chosen**

Create `scripts/quality/quality_report.py` with a dedicated `QualityReport` model:

```python
@dataclass
class ModeQualityMetric:
    mode: str
    category: str
    adoption_state: str          # From AuditReport
    static_score: float          # From AdoptionReport
    runtime_verified: bool       # From ModeScore
    eval_score: float | None     # From EvalResultFile (None if no evals)
    eval_drift: float | None     # Latest drift vs baseline
    eval_case_count: int         # Number of eval test cases
    evidence_count: int          # Runtime evidence records found
    quality_adoption_gap: bool   # eval > 0.7 but adoption < 0.85, or vice versa

@dataclass
class QualityReport:
    generated_at: str
    metrics: list[ModeQualityMetric]
    modes_with_evals: int
    modes_without_evals: int
    gap_count: int               # Modes with quality-adoption gap
```

**Pros:**
- Single responsibility: `QualityReport` owns quality↔adoption correlation; `AuditReport`
  owns lifecycle tracking; `AdoptionReport` owns scoring.
- No changes to existing report models — additive only.
- Opt-in: `QualityReport` is generated only when `--quality` flag is passed or when
  `NARRARE_QUALITY_METRICS=1` is set.
- Privacy-safe: contains only scores, counts, booleans, and identifiers — no eval case
  content or prompt text.

**Cons:**
- New script and model.
- Requires eval results to exist for meaningful output — degrades gracefully to
  adoption-only metrics when no evals found.
- Evidence count comes from parsing structured logs — same log-format dependency as
  Option A.

---

**Decision: Option C — Separate `QualityReport` that references both eval results and evidence.**

### Rationale

Quality metrics are a new concern that crosses two existing data sources (evals and
evidence). Injecting this into `AuditReport` (Option B) mixes lifecycle tracking with
quality correlation — a RULE-06 violation. Option A produces data but no structured
report. Option C creates a clean, opt-in, privacy-safe report that joins eval scores
with adoption/evidence data without modifying existing models.

The `quality_adoption_gap` flag is the key output: it identifies modes where eval
scores and adoption evidence disagree. A mode with high eval scores but low adoption
(e.g., `eval_score=0.9`, `adoption_state=static_verified`) has a gap — it performs well
in tests but lacks runtime proof. Conversely, a mode with strong adoption but poor evals
may have runtime wiring that doesn't produce quality output.

### Consequences

**Positive:**
- Quality↔adoption correlation becomes visible without manual cross-referencing.
- Opt-in: no runtime overhead unless explicitly enabled.
- Privacy-safe: no raw prompt text, no eval case content, no user data.
- Reuses existing `eval_drift/parser.py` infrastructure.

**Negative / Tradeoffs:**
- New Platform script and data model.
- Evidence count depends on log parsing — not perfectly reliable (log rotation).
- Initial version is CI-only (no real-time dashboard).

**Constraints introduced:**
- `QualityReport` generation requires `NARRARE_QUALITY_METRICS=1` or `--quality` flag.
- Report contains ONLY scores, counts, booleans, and identifiers — never eval case
  names, prompt text, or user content.
- Join key is `(category, mode)` — eval result file naming and evidence `mode` field
  must use the same canonical mode names as the adoption registry.

### New Files

| File | Responsibility | Max Lines |
|------|----------------|-----------|
| `scripts/quality/__init__.py` | Package init | ~5 |
| `scripts/quality/quality_report.py` | `ModeQualityMetric`, `QualityReport` models + builder | ~250 |
| `scripts/quality/joiner.py` | Eval↔evidence join logic | ~200 |
| `scripts/check_quality_metrics.py` | CLI entry point for quality report generation | ~150 |

### Data Flow

```text
evals/results/*.json ──→ eval_drift/parser.py ──→ EvalResultFile[]
                                                        ↓
adoption-registry.yaml ──→ scorer.py ──→ AdoptionReport  ↓
                              ↓                          ↓
                    scorer_modes.py ──→ ModeScore[]       ↓
                              ↓                          ↓
                    audit_report.py ──→ AuditReport      ↓
                              ↓                          ↓
                    structured logs ──→ evidence parse ──→↓
                              ↓                          ↓
                         quality/joiner.py ──→ ModeQualityMetric[]
                              ↓
                    quality/quality_report.py ──→ QualityReport
                              ↓
                    check_quality_metrics.py ──→ CI output (JSON/text)
```

---

## Decision 4 — Evidence Persistence

### Options Considered

#### Option A — No persistent storage — structured logs are sufficient for CI

Keep `LoggingEvidenceSink` as the only sink. P3 evidence needs (audit lifecycle,
quality metrics) are met by parsing structured logs at CI time. Log aggregation
(e.g., OpenTelemetry collector) provides durability.

**Pros:**
- Zero implementation cost — status quo.
- No privacy surface beyond what already exists.
- No migration, no DB schema, no API.
- Structured logs are already queryable with standard tools (jq, grep, Loki).

**Cons:**
- Log rotation destroys history — no evidence trail beyond CI run artifacts.
- AuditReport can only see evidence from the current CI run.
- QualityReport evidence counts are approximations (depend on log completeness).
- Cannot answer: "what was the evidence state 3 days ago?"
- OpenTelemetry collector is recommended but not yet deployed (ADR-031).

#### Option B — Add PostgreSQL table for evidence records (with migration)

Create an `invocation_evidence` table with:
- `id`, `feature_id`, `intent`, `mode`, `preference_status`, `kb_suggested_status`,
  `voice_profile_status`, `output_budget_profile`, `final_prompt_validated`,
  `validation_errors` (JSONB), `audit_state`, `created_at`
- Standard CRUD via a new `PersistentEvidenceSink` implementing the existing
  `FeatureInvocationEvidenceSink` protocol.

**Pros:**
- Queryable evidence history — trend analysis, drift detection, audit forensics.
- Natural fit with existing PostgreSQL + SQLAlchemy stack.
- `AuditReport` can query actual evidence state at any point in time.
- `QualityReport` gets accurate evidence counts without log parsing.
- Enables future: evidence-based regression detection, mode-level SLA monitoring.

**Cons:**
- Requires Alembic migration (RULE-14).
- Adds a DB write to every AI invocation — latency impact.
- Privacy surface: even though evidence is privacy-safe, a DB table is more sensitive
  than ephemeral logs (retention policy needed).
- Backend dependency: `PersistentEvidenceSink` lives in Backend, not Core — requires
  API layer wiring.
- Over-engineering risk: evidence volume may be low (CI/test probes only, not
  production traffic).

#### Option C — Add file-based evidence store (JSON lines in `.evidence/`) — **Chosen**

Create an append-only JSON Lines evidence store:
- File: `.evidence/invocations.jsonl` (gitignored, CI-artifact-only)
- Each line is a serialized `FeatureInvocationEvidence` with an added `timestamp` field.
- A new `FileEvidenceSink` implements `FeatureInvocationEvidenceSink`.
- CI artifacts: `.evidence/` is uploaded as a CI artifact and rotated per run.
- Local development: evidence accumulates in `.evidence/` and can be queried with
  standard tools (jq, `python -c "..."`).

**Pros:**
- No DB migration, no Alembic, no Backend wiring — pure Platform/Core.
- Evidence is queryable (jq, Python, grep) without DB infrastructure.
- Append-only — no mutation, no deletion, no consistency concerns.
- Gitignored — never committed to repo; CI artifact provides durability.
- `QualityReport` can read `.evidence/` directly for accurate evidence counts.
- `AuditReport` can derive state transitions from evidence history.
- Fits the "Platform consumes evidence" pattern — no new Core dependency.

**Cons:**
- File I/O on every invocation — negligible for CI/test probes; may be noticeable
  in high-volume production.
- No built-in retention/rotation — files grow unbounded without cleanup.
- Not as queryable as PostgreSQL for complex joins — but quality metrics only need
  per-mode counts and latest states.
- Local `.evidence/` may contain stale data from previous runs — CI artifacts are
  per-run.

---

**Decision: Option C — File-based evidence store (JSON lines in `.evidence/`).**

### Rationale

P3 is a long-term hardening increment, not a production monitoring system. The
evidence volume in P3 is CI test probes and development invocations — not production
traffic. A PostgreSQL table (Option B) is architecturally correct for production
monitoring but is premature for P3: it requires a migration, Backend wiring, retention
policies, and privacy review that belong in a dedicated observability ADR, not bundled
into P3.

Option A (no persistence) is rejected because it leaves the audit lifecycle and quality
metrics dependent on ephemeral logs, which cannot support trend detection or historical
state reconstruction — both required for P3 exit criteria ("registry/checker drift is
automatically detected" implies drift over time, not just a snapshot).

Option C is the simplest correct solution: file-based, append-only, gitignored, CI-
artifact-capable. It provides the queryability needed for `QualityReport` and
`AuditReport` without the infrastructure cost of a DB table. When production monitoring
requires real-time queryability, an ADR should upgrade to Option B (see Review Triggers).

### Consequences

**Positive:**
- Evidence becomes queryable without log parsing.
- `QualityReport` gets accurate evidence counts.
- `AuditReport` can derive state transitions from evidence history.
- No DB migration, no Backend wiring — pure Core/Platform.
- `.evidence/` is a standard pattern for CI artifacts (same as `evals/baselines/`).

**Negative / Tradeoffs:**
- File I/O on every invocation — acceptable for CI/test probes.
- No built-in retention — files grow. Mitigated by CI artifact rotation.
- Not suitable for production-scale monitoring — see Review Triggers for upgrade path.

**Constraints introduced:**
- `.evidence/` must be in `.gitignore`.
- `FileEvidenceSink` must handle I/O errors gracefully (non-blocking, log warning
  on failure, never block invocation pipeline).
- Evidence files use append-only — no mutation or deletion.
- Privacy: file contents match `FeatureInvocationEvidence.model_dump()` + `timestamp`
  — same privacy guarantee as structured logs.

### New Files

| File | Responsibility | Max Lines |
|------|----------------|-----------|
| `packages/core/narrare_core/ai_invocation/evidence/file_sink.py` | `FileEvidenceSink` implementation | ~100 |
| `.evidence/.gitkeep` | Ensure directory exists (gitignored) | 0 |
| Update `.gitignore` | Add `.evidence/*.jsonl` | 1 line |

### FileEvidenceSink Contract

```python
class FileEvidenceSink:
    """Append-only JSON Lines evidence sink.

    Writes each FeatureInvocationEvidence as one JSON line to
    .evidence/invocations.jsonl.  Non-blocking: I/O errors are
    logged but never block the invocation pipeline.

    Args:
        evidence_dir: Directory for evidence files.
            Defaults to REPO_ROOT / ".evidence".
        filename: Evidence file name.
            Defaults to "invocations.jsonl".
    """

    async def record(self, evidence: FeatureInvocationEvidence) -> None:
        """Append evidence as a JSON line.

        On I/O error: logs a warning and returns (no exception).
        """
        ...
```

---

## Implementation Plan (P3 Layer-by-Layer)

### Layer 1 — Core: File-based evidence sink

| File | Responsibility |
|------|----------------|
| `packages/core/narrare_core/ai_invocation/evidence/file_sink.py` | `FileEvidenceSink` — append-only JSON Lines |
| `.evidence/.gitkeep` | Ensure evidence directory exists |
| `.gitignore` | Add `.evidence/*.jsonl` exclusion |

**Dependencies:** None (self-contained).

### Layer 2 — Platform: Registry drift detection

| File | Responsibility |
|------|----------------|
| `scripts/architecture/adoption-registry.schema.json` | JSON Schema for registry v2.0.0 |
| `scripts/check_registry_drift.py` | Registry ↔ prompts/agents/variables drift detection |

**Dependencies:** None (reads files on disk).

### Layer 3 — Platform: Doc-drift automation

| File | Responsibility |
|------|----------------|
| `scripts/doc_drift/__init__.py` | Package init |
| `scripts/doc_drift/adr_checks.py` | ADR cross-reference and status checks |
| `scripts/doc_drift/spec_checks.py` | Spec file reference and RULE-XX checks |
| `scripts/doc_drift/terminology_checks.py` | Checker terminology alignment checks |
| `scripts/check_doc_drift.py` | Update: import new check families |

**Dependencies:** None (reads Markdown files on disk).

### Layer 4 — Platform: Quality metrics

| File | Responsibility |
|------|----------------|
| `scripts/quality/__init__.py` | Package init |
| `scripts/quality/quality_report.py` | `QualityReport` + `ModeQualityMetric` models |
| `scripts/quality/joiner.py` | Eval↔evidence↔adoption join logic |
| `scripts/check_quality_metrics.py` | CLI entry point |

**Dependencies:** Layer 1 (FileEvidenceSink produces `.evidence/` data),
`eval_drift/parser.py` (reads eval results).

### Layer 5 — Platform: Integration and CI wiring

| File | Responsibility |
|------|----------------|
| Update `scripts/check_adoption.py` | Add `--drift` flag to run registry drift checks |
| Update `.github/workflows/ci.yml` | Add registry drift + doc drift + quality metrics jobs |

**Dependencies:** Layers 2, 3, 4.

### Layer 6 — Docs

| File | Responsibility |
|------|----------------|
| Update `docs/features/infra/INFRA-013-...md` | P3 status update |
| Update `docs/architecture/decisions/INDEX.md` | Add ADR-041 entry |

### Dependency Order

```
Layer 1 (file sink) ←── independent
Layer 2 (registry drift) ←── independent
Layer 3 (doc drift) ←── independent
Layer 4 (quality metrics) ←── depends on Layer 1 (reads .evidence/)
Layer 5 (CI integration) ←── depends on Layers 2, 3, 4
Layer 6 (docs) ←── depends on Layer 5
```

Layers 1–3 can be implemented in parallel. Layer 4 depends on Layer 1 for
evidence data but can start with a log-parsing fallback. Layer 5 integrates
everything into CI.

---

## RULE-XX Compliance

| Rule | Status | Evidence |
|------|--------|----------|
| RULE-01b | ✅ | No changes to agent/model/gateway paths. |
| RULE-02/02a | ✅ | No changes to prompt composition or content categories. |
| RULE-03 | ✅ | ADR-041 and this spec define contracts before implementation. `FileEvidenceSink` implements existing `FeatureInvocationEvidenceSink` protocol. |
| RULE-04 | ✅ | New scripts stay under 400 lines; doc-drift checks extracted to `doc_drift/` package if needed. |
| RULE-05 | ✅ | Core owns file sink; Platform owns drift checkers, quality metrics, and CI wiring. |
| RULE-06 | ✅ | Registry drift, doc drift, quality metrics, and evidence persistence are four separate modules. |
| RULE-07 | ✅ | Platform scripts read files on disk (JSON, YAML, Markdown) — never import Core. `QualityReport` consumes `EvalResultFile` data (parsed from JSON), not Core types. |
| RULE-09 | ✅ | All new public functions and models require full type annotations. |
| RULE-10 | ✅ | Each new script has corresponding unit tests. Quality metrics have integration tests with fake eval/evidence data. |
| RULE-11 | ✅ | `FileEvidenceSink` handles I/O errors gracefully — logs warning, never blocks pipeline. |
| RULE-14 | ✅ | No DB schema change in P3. File-based evidence store uses no migrations. PostgreSQL upgrade is deferred to a future ADR. |
| RULE-20 | ✅ | Registry drift detection prevents static-only adoption from going unnoticed. |
| RULE-22 | ✅ | Quality metrics use the same mode/category vocabulary as adoption registry, eval results, and evidence. |

---

## Sustainability Check

1. **Correct in 3 months?** Yes. Schema validation, drift detection, quality metrics,
   and file-based evidence are all additive — they do not constrain future choices. If
   PostgreSQL evidence is needed, `FileEvidenceSink` becomes a secondary sink while
   `PersistentEvidenceSink` is added behind a feature flag.

2. **Hard-to-undo coupling?** Minimal. `FileEvidenceSink` implements the existing
   `FeatureInvocationEvidenceSink` protocol — replacing it requires only a new
   implementation. Quality metrics depend on file paths and naming conventions, not
   on internal APIs. Doc-drift checks read Markdown files — no code coupling.

3. **Simplest correct solution?** Yes. Each decision picks the option that addresses
   the root cause without over-building: schema + drift detection (not code generation),
   extend existing checker (not new format), separate report (not mixed), file-based
   store (not DB).

4. **Design intent clear?** Yes. Four decisions, each addressing one P3 exit criterion:
   - Decision 1 → "Registry/checker drift is automatically detected"
   - Decision 2 → "Registry/checker drift is automatically detected" (docs dimension)
   - Decision 3 → "Quality metrics are opt-in, privacy-safe, and tied to evaluation"
   - Decision 4 → "Persistent evidence, if added, has a storage/API contract"

---

## Review Trigger

- [ ] When mode count exceeds 50 — reconsider per-mode manifests (Decision 1 Option B).
- [ ] When evidence volume exceeds 10,000 records/day — upgrade to PostgreSQL
  evidence store (Decision 4 Option B) via a new ADR.
- [ ] When real-time evidence querying is needed (dashboard, not just CI) — upgrade
  to PostgreSQL evidence store.
- [ ] When ADR count exceeds 60 and `check_doc_drift.py` becomes slow — consider
  incremental/frontmatter-only checking.
- [ ] When eval suite names diverge from registry mode names — add naming convention
  enforcement to registry drift checker.
- [ ] When Pydantic Evals changes its report JSON format — update `eval_drift/parser.py`
  and `quality/joiner.py` in lockstep.

---

## INFRA-013 Status Update (Draft)

Insert the following into `INFRA-013-ai-invocation-adoption-contract.md` under
§ Status and Decision Summary:

```
- 2026-06-07 — P3 Architecture Spec complete: ADR-041 defines registry drift
  detection (JSON Schema + drift checker), doc-drift automation (ADR/spec/RULE-XX
  cross-reference validation), quality metrics (QualityReport joining eval results
  with invocation evidence), and file-based evidence persistence (FileEvidenceSink
  with .evidence/invocations.jsonl). P3 implementation begins. P0, P1, and P2 are
  fully implemented (24/27 modes wired).
```

---

## ARCHITECTURE HANDOFF

### Spec
- Typ: ADR (ADR-041)
- Pfad: `docs/architecture/decisions/ADR-041-typed-manifests-drift-metrics.md`
- Status: Accepted

### Root Cause
P0–P2 built the invocation contract, adoption registry, and audit lifecycle — but
governance relies on hand-maintained YAML, no cross-reference validation, no quality
correlation, and ephemeral-only evidence. P3 automates the governance layer.

### Alternatives Considered
- **Decision 1**: Code annotations (rejected — RULE-07 violation), per-mode manifests
  (rejected — premature for 27 modes), schema + drift (chosen — addresses root cause).
- **Decision 2**: Static analysis only (rejected — fragile), frontmatter enforcement
  (rejected — migration cost), both (chosen — incremental, extends existing infra).
- **Decision 3**: Join script (rejected — no report model), extend AuditReport
  (rejected — RULE-06 violation), separate QualityReport (chosen — clean separation).
- **Decision 4**: No persistence (rejected — cannot detect drift over time), PostgreSQL
  (rejected — premature), file-based (chosen — simplest correct for CI/test evidence).

### Implementation Plan
1. **Core**: FileEvidenceSink → Core Specialist
2. **Platform**: Registry schema + drift checker → Platform Specialist
3. **Platform**: Doc-drift checks → Platform Specialist
4. **Platform**: Quality metrics report → Platform Specialist
5. **Platform**: CI integration → Platform Specialist
6. **Docs**: INFRA-013 + INDEX.md update → Docs Specialist

### Critical Constraints
- **RULE-07**: Platform scripts never import Core — they read files on disk.
- **RULE-14**: No DB migration in P3 — file-based evidence only.
- **Privacy**: QualityReport contains only scores/counts/booleans — never eval content.
- **Opt-in**: Quality metrics generation requires explicit flag.

### Risks & Trade-offs
- **File-based evidence is not production-grade**: Accepted because P3 evidence volume
  is CI/test probes, not production traffic. Upgrade path defined in Review Triggers.
- **Doc-drift parsing is heuristic**: Accepted because ADR format is stable (40+ ADRs
  follow the template). Edge cases can be refined incrementally.
- **Quality join depends on naming consistency**: Mitigated by registry drift checker
  validating mode names match across sources.

### Definition of Done
- [x] ADR-041 approved by user
- [x] JSON Schema validates adoption-registry.yaml without errors
- [x] Registry drift checker detects: orphan modes, missing prompts, undeclared variables
- [x] Doc-drift checker detects: broken ADR cross-refs, invalid RULE-XX references
- [x] QualityReport generates successfully with opt-in flag
- [x] FileEvidenceSink writes to .evidence/invocations.jsonl
- [x] All new scripts have corresponding unit tests
- [x] INFRA-013 P3 exit criteria satisfied
- [x] No workarounds or shortcuts
