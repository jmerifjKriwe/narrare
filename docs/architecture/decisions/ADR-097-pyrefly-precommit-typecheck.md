# ADR-097 — Pyrefly as Additive Pre-Commit Type Check

> **Status:** ✅ Implemented — all 7 completeness items verified; item 7
> (green CI quality job) evidenced by PR #254.
> **Date:** 2026-10-14
> **Deciders:** Architecture Agent (binding direction validated by
> measurement; see §Measurement Basis)
> **Supersedes:** none
> **Related:** none (companion plan:
> `docs/development/plans/2026-08-13-pre-commit-runtime-optimization.md`, D1)

---

## Context

### The gap D1 left

The pre-commit runtime optimization plan (2026-08-13, decision D1) moved the
slow non-mutating hooks — `pyright`, `pyright-tests`, `bandit` — from
pre-commit to a pre-push stage, where together they consume ~36s warm / ~80s
cold. The pre-commit stage keeps only fast governance hooks (<2s each),
mutating hooks (ruff/biome/openapi), and sole-local gates. That decision was
correct — pyright at commit time blew the 120s budget — but it removed all
commit-time type coverage for production code: a type error in `apps/api/` or
`packages/core/` now surfaces first at pre-push, `just verify`, or CI.

**Root cause (2× Why):**

1. *Symptom:* no type check runs between "file staged" and "commit created".
2. *Why?* D1 moved pyright to pre-push because pyright cannot check a small
   scope cheaply — its startup, binding, and memory profile are whole-project.
3. *Why is that the actual cause?* Pyright's architecture (Node process,
   watch-mode-less cold runs, eager binding of the full import graph) makes a
   staged-scope run nearly as expensive as a full run. The defect is not D1's
   staging — it is the absence of a type checker whose incremental/staged cost
   fits the <2s governance-hook budget.

### Measurement Basis

All numbers below were measured on 4 cores with a CI-faithful environment
(`uv sync --frozen --all-packages --group dev --extra embeddings`) on the
1,483-file production scope (pyright `filesAnalyzed: 1483`).

**Runtime and memory:**

| Tool | Mode | Wall | Max RSS |
|---|---|---|---|
| pyright 1.1.414 | whole project (1,483 files) | 47.2s median (46.2/47.2/51.3) | 2.20 GB |
| pyrefly 1.3.2 | whole project | 3.07s median (3.01/3.07/3.26) | 0.84 GB |
| pyrefly 1.3.2 | staged, 1 file | 0.35s | — |
| pyrefly 1.3.2 | staged, 5 files | 0.39s | — |

- Neither tool has an effective persistent cache here: pyright created no
  `.pyright/` after 6 runs; warm == cold.
- pyright heap-thrashes: "Emptying type cache to avoid heap overflow. Used
  ~1.93GB out of 2.24GB" 3× per run; binding `transformers/__init__.py`
  alone took 11.9s (5,561 files parsed/bound vs 1,483 checked).
- The `embeddings` extra costs pyright +55% (30.4s → 47.2s); pyrefly is
  unaffected (3.46s → 3.07s).
- Staged-scope pyrefly produces the identical finding as the whole-project
  run for the same file (verified on
  `apps/api/narrare/analytics/repository.py`).

**Findings (same 1,483-file scope, same venv):**

- pyright strict: **0 errors**.
- pyrefly (scoped config, default preset, `permissive-ignores`): **93
  errors**; with pyright-strict-analog severities (`unknown-*` as errors):
  264; auto-migrated without a config file: 268.
- Triage of the 93: **88 tool artifacts** (4 root causes listed in Decision 4,
  plus weaker `in`-narrowing than pyright, dead `...` after `return`, missing
  bidirectional inference, script-dir import resolution); **2 real**
  (§Implementation Notes — evidence only, fixes belong to the implementation
  wave); **3 "pyrefly-stricter, benign"**.

### The config hazard (why a committed `pyrefly.toml` is mandatory)

`pyrefly check --preset <X>` without a config file **silently discards** the
in-memory migration of `[tool.pyright]` from `pyproject.toml`: the scope
flips to the default `**/*.py*` including `tests/` — 1,480 errors in `tests/`,
197 missing-imports vs 1, and `extraPaths` lost. A committed config with
measured parity (pyright `filesAnalyzed: 1483` == pyrefly `1,483 modules`) is
therefore not a nicety but a correctness requirement.

---

## Decision Drivers

- **Restore what D1 lost, without reopening D1:** commit-time type coverage
  for production code, inside the pre-commit budget (fast governance hooks
  <2s each; 120s total).
- **No quality loss (D1's own bar):** pyright strict remains THE
  authoritative type gate — RULE-09 enforcement (`just typecheck` — pyright
  strict + CI quality job) is unchanged. A second checker may only add
  signal, never dilute the existing gate.
- **Staged-scope precedent:** `pyright-tests-staged`
  (`.pre-commit-config.yaml` ~line 261, gate-fix 61f39c9b) already
  established the pattern — staged files only at commit time, full suite
  remains at pre-push/CI.
- **Determinism:** pyrefly is a Rust binary whose preset/migration defaults
  shift between minor versions; a repeatable local gate needs a pinned
  version and a committed config.
- **Channel discipline (RULE-23):** whatever baseline mechanism pyrefly uses
  must not become a second, uncontrolled type-suppression channel.

---

## Options Considered

### Option A — pyrefly additive at pre-commit, staged scope (chosen)

Add pyrefly 1.3.2 as an **additive** commit-time type check: a pre-commit
hook mirroring `pyright-tests-staged` (`stages: [pre-commit]`,
`pass_filenames: true`, `types: [python]`, staged scope), backed by a
committed `pyrefly.toml` and a small disabled-error-kind set plus a residual
baseline.

**Pros:** staged runs cost 0.35s (1 file) / 0.39s (5 files) — far inside the
governance-hook budget; staged scope produces identical findings to
whole-project (verified); whole-project fallback is 3.07s median / 0.84 GB if
the staged mode ever needs to be waived; purely additive — pyright
untouched.

**Cons:** a second type-checker surface to keep configured (version pin,
config parity, baseline discipline); 93-error artifact landscape must be
triaged and bounded; CI needs a separate wiring step (CI does not run
pre-commit).

### Option B — pyrefly additive at pre-push (rejected)

Run pyrefly at the pre-push stage next to pyright.

**Rejected:** redundant — pyright already occupies that slot and covers the
same 1,483-file scope authoritatively; the value proposition is precisely the
commit-time coverage D1 lost, which pre-push does not restore. It would add
tooling surface with no new coverage epoch.

### Option C — pyrefly replaces pyright (rejected)

Make pyrefly the single type gate (its speed would even allow whole-project
checks at pre-commit).

**Rejected:** 88 of 93 current findings are tool artifacts, and pyright is
provably more precise where it matters — minimal repro: `Final[tuple[str,
...]]` membership narrows to `Literal` under pyright, only to `str` under
pyrefly (`in`-narrowing). Switching gates would trade real precision for
speed — exactly the "quality loss" D1 ruled out — and would strand the 117
existing `# pyright: ignore` + 37 `# type: ignore` suppressions whose
semantics are pyright's.

### Option 0 — status quo (rejected)

Keep commit-time type coverage absent.

**Rejected:** the gap is real and measured (type errors surface one push
late); the `pyright-tests-staged` hook already proved staged commit-time
checks are worth having for tests — production code deserves the same.

---

## Decision

**We choose Option A** — pyrefly 1.3.2 as an additive pre-commit type check,
in seven binding decisions:

### 1. Additive only — pyright strict stays THE authoritative gate

Pyrefly does **not** replace pyright anywhere. RULE-09 enforcement
(`docs/_shared/CONSTRAINTS.md` §6 enforcement row ~line 1201: "`just
typecheck` — pyright strict (`uv run pyright`) + CI job 'Lint, Typecheck &
Security' (quality)") and CI gate G6 ("pyright (strict; mypy not required)",
`.github/workflows/ci.yml` header table, lines ~10–31) are unchanged by this
ADR. The RULE-09 enforcement row gains a pyrefly mention **in the
implementation wave, not now** — this ADR changes no CONSTRAINTS.md text.

### 2. Hook shape mirrors `pyright-tests-staged`

A pre-commit hook with `stages: [pre-commit]`, `pass_filenames: true`,
`types: [python]`, staged scope — the exact pattern of the
`pyright-tests-staged` hook (`.pre-commit-config.yaml` ~line 261). Whole-suite
type coverage stays where D1 put it (pyright at pre-push + CI).

### 3. A committed `pyrefly.toml` is MANDATORY

Measured parity: pyright `filesAnalyzed: 1483` == pyrefly `1,483 modules`.
Required contents:

```toml
project-includes = ["apps/api", "packages/core", "packages/i18n", "scripts", "benchmark"]  # mirrors pyright include; tests excluded
search-path = ["apps/api", "packages/core", "packages/i18n", "scripts"]  # = pyright extraPaths
python-version = "3.14"
python-interpreter-path = ".venv/bin/python"
permissive-ignores = true   # else the 117 existing `# pyright: ignore` + 37 `# type: ignore` are not honored and the count explodes
required-version = "==1.3.2"  # Rust binary; preset/migration defaults shift between minor versions — load-bearing for baseline stability
```

Without this file, `--preset` runs silently re-scope to `tests/` (§Context —
the config hazard). The version pin is not cosmetic: preset/migration
defaults shift between minor versions, and an unpinned checker would make the
baseline non-reproducible across machines and CI.

### 4. Error-kind set starts NARROW — disable three artifact-heavy kinds, baseline the residual

Initially disable `no-matching-overload`, `bad-argument-type`,
`missing-argument`; keep the rest; baseline the residual findings.

Justification: 86 of 93 current findings sit in exactly these three kinds
and are 100% tool artifacts from 4 root causes:

| Root cause | Count |
|---|---|
| pydantic_ai `Agent.output_validator` overloads | 30× |
| SQLAlchemy `Row.attr` via C-extension stub `BaseRow.__getattribute__` | 27× |
| `**dict` unpacking into dataclass `__replace__` typed `object` | 15× |
| duplicate module identity `scripts.x` vs `x` | 11× |

These patterns regenerate routinely — every new agent = 1 FP, every new
repository method = 2 FPs — so baselining them would create permanent
baseline-churn. Disabling the kinds at the checker level keeps the baseline
small and honest. Re-enable when upstream fixes land (Open Question OQ-1).

### 5. CI wiring is a SEPARATE mandatory step

CI does **not** run pre-commit (verified: no pre-commit invocation in
`.github/workflows/*.yml`; the `ci: skip:` block targets the hosted
pre-commit.ci service). The quality job therefore needs its own pyrefly step
**plus** a gate-matrix row in the `.github/workflows/ci.yml` header table
(currently G1–G10; line ~19 reads "G6 pyright (strict; mypy not required)").
Local-vs-CI drift has bitten this repo before (PR #236, gate-fix 61f39c9b —
see the comments in `.pre-commit-config.yaml`). An additive local gate
without CI backing would recreate exactly that drift, in reverse.

### 6. RULE-23 boundary — the pyrefly baseline is NOT a suppression channel

`scripts/check_type_ignores` (RULE-23 ratchet, baseline
`scripts/architecture/type-ignore-baseline.json`) counts only
`# type: ignore` / `# pyright: ignore` comments. The pyrefly baseline file is
a **separate artifact**: it is not a type-suppression channel, is not counted
by the RULE-23 ratchet, and gets its own update discipline — **baseline
additions require naming the error class + justification in the PR
description**. The two channels stay strictly separated. Nothing in this ADR
weakens RULE-23; no `# type: ignore` is added or migrated.

### 7. The two real findings are recorded as evidence; fixes are OUT OF SCOPE here

Both triaged-real findings (below, §Implementation Notes) belong to the
implementation wave: the `bad-override` in `ws_context_assembler.py` becomes
a baseline entry + note (optional hardening later, plus Open Question OQ-2);
the `bad-argument-type` in `analytics/repository.py` gets its 1-line widening
then. This ADR records them so the evidence survives the transition.

---

## Rationale

The defect is the absence of a type checker whose staged cost fits the
governance-hook budget — not a defect in D1's staging. Pyright cannot be that
checker on this codebase: 47.2s median and 2.20 GB RSS whole-project, no
persistent cache (warm == cold, no `.pyright/` after 6 runs), heap-thrashing
3× per run (~1.93GB of 2.24GB), 11.9s binding `transformers/__init__.py`
alone (5,561 files parsed/bound vs 1,483 checked), and a +55% penalty from
the `embeddings` extra (30.4s → 47.2s). Pyrefly's profile fits every budget
dimension: 3.07s median / 0.84 GB whole-project, 0.35s staged for one file,
0.39s for five, and `embeddings`-immune (3.46s → 3.07s) — while producing the
identical finding as its whole-project run in staged scope (verified on
`apps/api/narrare/analytics/repository.py`).

Why additive rather than a replacement: precision is not symmetric. Pyright
strict reports 0 errors on the scope; pyrefly reports 93, of which 88 are
tool artifacts with four identifiable root causes, and pyright demonstrably
narrows better (`Final[tuple[str, ...]]` membership → `Literal` vs `str`).
Replacing the gate would import churn and lose precision — the opposite of
D1's "no quality loss" bar. Why pre-commit rather than pre-push: pre-push is
already covered by the authoritative gate; the uncovered epoch is the commit
itself, and pyrefly is the only measured candidate that fits it.

The conscious trade-offs: a second checker surface (config + pin + baseline)
that must be kept in parity with pyright's scope; three error kinds disabled
at rollout, narrowing initial coverage (re-enabled as upstream fixes land);
and a mandatory separate CI step, because pre-commit hooks are invisible to
CI by construction in this repo.

---

## Consequences

**Positive:**

- Commit-time type coverage for production code restored for the first time
  since D1, at 0.35–0.39s per staged run — inside the <2s governance-hook
  budget, with whole-project runs (3.07s) affordable as a fallback.
- Type errors surface at commit, not push/verify/CI — one epoch earlier on
  every production-code change.
- Two independent checkers with different blind spots: pyrefly already found
  2 real issues pyright strict misses (both recorded below).
- Pyright's authority (RULE-09, G6, pre-push) untouched; D1's runtime win
  untouched.

**Negative / Tradeoffs:**

- A second type-checker surface to maintain: `pyrefly.toml` parity with
  pyright scope, a load-bearing version pin, and a baseline file with its own
  discipline.
- Three error kinds (`no-matching-overload`, `bad-argument-type`,
  `missing-argument`) disabled at rollout — the kinds containing 86/93
  current findings; pyrefly coverage is intentionally partial until upstream
  fixes land (OQ-1).
- CI quality job grows one step + one gate-matrix row (separate mandatory
  implementation wave).
- Occasional pyrefly-strict-but-benign noise (3 current findings) that
  pyright deliberately does not report.

**Constraints introduced:**

- RULE-09 — unchanged in text and enforcement; pyright strict remains THE
  authoritative gate. (The §6 enforcement row's pyrefly mention is an
  implementation-wave change, deliberately not made by this ADR.)
- RULE-23 — the pyrefly baseline file is defined as NOT a type-suppression
  channel and stays outside the `check_type_ignores` ratchet; the two
  channels must never be merged.
- New-tool discipline (ADR-006 spirit): pyrefly is pinned (`==1.3.2`),
  scoped by a committed config, and additive — promotion to anything more
  requires a new ADR.

---

## Implementation Notes

**Files touched by the implementation wave (none touched by this ADR):**

- `.pre-commit-config.yaml` — new `pyrefly` hook next to the pyright block
  (~lines 228–268), mirroring `pyright-tests-staged` (~line 261):
  `stages: [pre-commit]`, `pass_filenames: true`, `types: [python]`, staged
  scope. Note the `typecheck-frontend` precedent (~lines 343–351):
  whole-project tsc runs at pre-commit when it is cheap enough — pyrefly's
  staged mode is the same argument, one epoch earlier.
- `pyrefly.toml` (new) — contents per Decision 3.
- `.github/workflows/ci.yml` — pyrefly step in the quality job + gate-matrix
  row in the header table (currently G1–G10; line ~19 "G6 pyright (strict;
  mypy not required)").
- `docs/_shared/CONSTRAINTS.md` — RULE-09 enforcement row gains a pyrefly
  mention (implementation wave only).
- Baseline artifact for the residual findings (separate from
  `scripts/architecture/type-ignore-baseline.json`; update discipline per
  Decision 6).

**The two real findings (evidence; fixes out of scope for this ADR):**

1. **`apps/api/narrare/writing/ws_context_assembler.py:86` —
   `bad-override` (LSP narrowing).**
   `WsWritingContextAssembler.assemble(self, *, chapter_id: UUID,
   project_id: UUID | None = None, mode: str | None = None, **kwargs: Any)`
   overrides a chain in which every other link accepts all-optional kwargs:
   `ContextAssembler[T].assemble(**kwargs: Any)` (abstract) and
   `WritingContextAssembler.assemble` — all keyword-only WITH defaults +
   `**_extra: Any` (signature at
   `packages/core/narrare_core/writing/context_assembler.py:124-161`). The WS
   override is the ONLY link making `chapter_id` required. Pyright skips
   override checks over `Any`-`**kwargs` bases (deliberate pyright
   carve-out); pyrefly flags it. Contained: both base-typed call sites pass
   `chapter_id` (`apps/api/narrare/writing/ws_turn_service.py:230`;
   `packages/core/narrare_core/agents/writing_graph_kb_context.py:51`). The
   ABC docstring (`packages/core/narrare_core/context/assembler.py:29-35`)
   explicitly sanctions per-subclass kwargs. **Resolution: baseline entry +
   note; optional hardening later.**

2. **`apps/api/narrare/analytics/repository.py:153` —
   `bad-argument-type`.**
   `_to_agg_row(..., cost: Decimal | int, ...)` receives the
   `func.coalesce(func.sum(...), 0).label(...)` row element whose true static
   type is `Decimal | None`. Proven: pyright reveals `Label[Decimal | None]`
   but loses precision in the `Row[*tuple[Unknown, ...]]` unpacking (stays
   silent); pyrefly keeps it and flags. The annotation is ALSO narrower than
   the downstream helper `_to_decimal(value: Decimal | int | None)`
   (`repository.py:65-74`; its docstring explicitly handles the COALESCE
   case). **Resolution: 1-line widening `cost: Decimal | int | None` in the
   implementation wave.**

**ADR Implementation Completeness:** An ADR is not implemented until it is
fully wired, tested, consumed, and documented. For this ADR the binding
checklist is: (1) pre-commit `pyrefly` hook, (2) `pyrefly.toml` with the
version pin, (3) `pyrefly-baseline.json`, (4) CI quality-job step, (5)
gate-matrix row G6a, (6) the RULE-09 enforcement-row mention in
`docs/_shared/CONSTRAINTS.md`, and (7) a green CI run of the quality job
(the only item that cannot be produced locally). Items 1–6 are wired in
this branch; item 7 gates the flip to ✅ Implemented.

---

## Open Questions

**OQ-1 — Re-enable triggers for the three disabled error kinds.**
`no-matching-overload`, `bad-argument-type`, `missing-argument` stay disabled
until their root causes shrink upstream. Concrete triggers to watch:
pydantic_ai `Agent.output_validator` overload resolution (30×), SQLAlchemy
C-extension `Row` stubs (27×), dataclass `__replace__` typing for `**dict`
unpacking (15×), and the `scripts.x` vs `x` duplicate-identity resolution
(11×). Re-enabling is a baseline-shrinking event: each trigger landing should
drop the kind's disabled flag and re-triage what surfaces.

**OQ-2 — `ContextAssemblerProtocol` signature drift (do NOT fix in this
wave).** `ContextAssemblerProtocol` in
`packages/core/narrare_core/writing/contracts.py:60-84` declares yet another,
stricter signature (positional `chapter_id: UUID, project_id: UUID`, required
kw-only `mode: GenerationMode`) that **neither** the base chain **nor** the
WS subclass satisfies exactly — a latent contract drift between the Protocol
and the implementations it names. Recorded here so the finding is not lost
when the `bad-override` baseline entry lands; resolving it (aligning
Protocol, ABC, and subclass signatures) is its own change with RULE-03
implications.

---

## Review Trigger

- [ ] When an upstream pyrefly release fixes any of the four artifact root
      causes (OQ-1): re-enable the affected error kind, re-triage, shrink
      the baseline.
- [ ] When pyrefly's minor version bumps beyond the pin: re-measure the
      baseline before relaxing `required-version` (the pin is load-bearing;
      preset/migration defaults shift between minor versions).
- [ ] After 3 months of additive operation: evaluate whether pyrefly's
      whole-project run (3.07s) should also join `just verify` as a cheap
      second opinion — via amendment, not silently.
- [ ] When OQ-2 is resolved (Protocol/ABC/subclass signature alignment):
      remove the corresponding baseline entry and close the open question.
- [ ] If pyrefly findings churn becomes a routine tax (baseline additions in
      most PRs): reconsider the error-kind set or the tool's value against
      its maintenance cost.
