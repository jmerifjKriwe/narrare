# Developer Throughput Program (P1–P5): Implementation Spec

> **Status:** Proposed — Architecture layer, 2026-10-19 (awaiting PO seal)
> **Spec author:** Architecture layer
> **Binds:** ADR-099 (provider catalog SSOT — P1); ADR-025 (adoption registry),
> ADR-037 (prompt-surface manifest), ADR-038 / ADR-045 (adoption contract — P2);
> ADR-097 (pre-commit staging precedent — P3); ADR-098 (single gate SSOT — P3/P4)
> **Implementation plan:** `docs/superpowers/plans/2026-10-19-dev-throughput-program.md`
> **Baseline measured:** 2026-10-19, this working tree (all numbers below are
> re-counted from disk, not remembered)

---

## 1. Goal & Non-Goals

**Goal.** Remove the two structural costs that make every feature in Narrare more
expensive than it should be:

- **P1** — the provider set is declared fifteen times in two languages, and two of
  those declarations have already diverged into a user-visible defect. Replace the
  duplication with one catalog and generated artifacts.
- **P2** — one intent is registered in eight hand-edited declaration surfaces, and
  nothing verifies that they agree. Add a parity gate over the existing
  surfaces (no reform of the governance layer).
- **P3** — the commit hook stage runs whole-project work on every commit while the
  push stage runs almost nothing. Move the two genuinely whole-project hooks to
  push and give the developer a strictly scoped slice command that is *not* a
  substitute for the full gate.
- **P4** — the review and per-task-report policy exists only as prose in one
  coordinator file; it has no threshold, so it is applied inconsistently in both
  directions. Write the threshold down in the two documents developers actually
  read, and pin it machine-side.
- **P5** — scaffolding a feature is entirely manual across eight-plus surfaces. Add
  a scaffolder that emits only artifacts which are green on arrival.

**Non-Goals.**

- **No new providers.** P1 changes nothing about which providers Narrare supports
  (seven today). It changes where that fact is written down.
- **No model-metadata migration.** Per-provider model lists stay in the API layer;
  `check_model_registry.py` keeps its current source of truth (ADR-099 Scope
  boundary).
- **No governance reform in P2.** The manifest (ADR-037), the adoption registry
  (ADR-025) and the static/runtime adoption split (ADR-038/045) are preserved
  exactly as they are; P2 adds a comparison, it does not move authority.
- **No CI gate is weakened anywhere in this program.** P3 touches
  `.pre-commit-config.yaml` and the `justfile` only; the CI architecture job's
  OpenAPI check and the frontend job's TypeScript step stay blocking. P1 *adds* a
  CI step; it removes none.
- **No bundler, no new runtime dependency.** The generator uses `yaml` only (already
  installed); no provider listing or catalog is parsed at runtime.
- **No test-framework change**, no new CI minutes bought, no new repository service.

---

## 2. Measured baseline (2026-10-19, this tree)

| Measurement | Value | Command / source |
|---|---|---|
| pre-commit hooks, total | **41** | `.pre-commit-config.yaml`, `- id:` count |
| └ pre-commit stage | **36** (21 explicit `stages: [pre-commit]` + 15 hooks relying on the default stage) | parsed per hook block |
| └ pre-push stage | **3** (`pyright`, `pyright-tests`, `bandit`) | same |
| └ manual stage | **1** (`adoption-score`) | same |
| └ commit-msg stage | **1** (`conventional-commits`) | same |
| Provider-set declaration surfaces | **15** across 2 languages | ADR-099 §Context table |
| Providers declared in the backend | **7** | `setup/base_schemas.py:45-52` |
| Providers offered by the settings form | **5** | `ProviderForm.tsx:8-14` ← defect |
| Providers offered by the wizard | **7** | `lib/providers.ts:4-12` |
| `LLMIntent` members | **30** | `llm/intents/_enums.py` |
| Route blocks in the prompt-surface manifest | **29** (all intents except `EMBED`, which is not gateway-routed) | `scripts/architecture/prompt-surface-manifest.yaml` |
| Intent declaration surfaces | **8** | §4 Problem |
| Adoption-registry `modes:` groups | **6** (registry `version: "2.0.0"`) | `scripts/architecture/adoption-registry.yaml` |
| Bundled prompt mode directories | **15** | `prompts/_bundled/*/*/` |
| `scripts/check_*.py` at repo root | **30** | `ls scripts/check_*.py` |
| Scaffolder scripts | **0** (no `scaffold_*`, no `new_*`) | `ls scripts/` |
| Per-task report files | **26** | `docs/superpowers/plans/reports/` |
| ci.yml jobs | **13** (`changes`, `nightly-gate`, `architecture`, `quality`, `zizmor`, `test-unit`, `test-integration`, `update-coverage-badge`, `frontend`, `test-e2e`, `warnings-summary`, `budget-report`, `release-orchestration`) | `.github/workflows/ci.yml` |
| Local full gate | `just verify` = `check` + `test-all` | `justfile` |

Two premise corrections against the request that produced this spec, recorded for
honesty: the pre-commit stage holds **36** hooks (not 21 — 21 is the count of hooks
that state the stage explicitly; the remaining 15 inherit `pre-commit` by default),
and the model-listing constant is `SUPPORTED_CATALOG_PROVIDERS`
(`llm/model_listing.py:62`), not `_VALID_PROVIDERS`.

---

## 3. P1 — Provider catalog single source of truth

**→ ADR-099.** This section records the program-level view; ADR-099 is the binding
decision.

### Problem (measured)

Fifteen declaration surfaces (§2) hold the same fact: which providers exist.
`ProviderForm.tsx:8-14` holds five of the seven the backend accepts, so a user with
a Groq or Z.AI key cannot add that key in Studio → Settings → AI, while the wizard
offers it. Nothing in the toolchain compares any two of the fifteen surfaces:
`check_model_registry.py` compares model IDs against models.dev and never looks at
the provider set.

### Decision

`packages/core/narrare_core/llm/_providers/catalog.yaml` is the SSOT;
`scripts/generate_provider_catalog.py` renders a checked-in Python `StrEnum`
(class syntax, measured pyright-clean) and a checked-in TypeScript module from it;
`--check` additionally enforces the handwritten-surface invariants of ADR-099
point 7; display labels become i18n keys resolved from
`packages/i18n/messages/{en,de,fr}/settings-ai.json`. Full detail, rejected
alternatives and the derived/handwritten table live in ADR-099.

### Acceptance criteria

1. The seven provider IDs, their order, their env var names, their settings field
   names, their listing strategies, their pricing defaults, their cache policies,
   their fallback model ID lists, their settings-editability and their
   endpoint-selector requirement are authored in exactly one file.
2. `scripts/generate_provider_catalog.py --check` exits 0 on a pristine tree, and
   exits 1 with a per-surface report when any generated artifact or handwritten
   invariant is out of step.
3. `AIProvider` remains importable from `apps/api/narrare/setup/base_schemas.py`,
   `apps/api/narrare/setup/schemas.py` and `packages/web/types/index.ts`.
4. `docs/reference/openapi.json` still declares `components.schemas.AIProvider`
   (`title: "AIProvider"`, seven-value enum) and `export_openapi.py --check` is
   green.
5. A component test at
   `packages/web/components/studio/settings/__tests__/ProviderForm.test.tsx`
   asserts the settings provider select renders all seven ids in canonical order —
   recorded RED before the fix, when it rendered five.
6. Pyright strict passes with the RULE-23 suppression baseline unchanged.
7. Every parity invariant has a test that fails when the invariant is deliberately
   broken (not merely a test that passes on the pristine tree).
8. The gate runs at commit time (new hook, `always_run`), in the local
   architecture surface (`check-architecture` recipe) and in the CI architecture
   job.

### Risks

| Risk | Mitigation |
|---|---|
| A generated file drifts from the catalog unnoticed | `--check` compares bytes; the pre-commit hook fires on every commit |
| Generated output stops being format-clean after a ruff/biome upgrade | the generator's committed-bytes test turns that into a red gate with an obvious fix (regenerate) |
| "Derive everything" creep pulls model metadata into the catalog and shrinks `check_model_registry.py`'s coverage | ADR-099 Scope boundary is explicit and has a Review Trigger; the parity gate asserts *ID lists*, not metadata |
| A future author rewrites the enum as a functional `StrEnum` "for brevity" | ADR-099 §Rationale carries the measured 6-error result, and the generated file header says DO NOT EDIT |
| Provider labels silently regress to English literals | the generator asserts every `label_key` resolves in all three locales; ADR-099 Consequences makes it a rule |

---

## 4. P2 — Intent-contract parity gate

### Problem (measured)

Adding one intent requires hand edits in **eight** surfaces:

1. `packages/core/narrare_core/llm/intents/_enums.py` — `LLMIntent` (30 members today)
2. `packages/core/narrare_core/llm/intent_profiles.py` — `INTENT_PROFILES`
3. `packages/core/narrare_core/llm/intent_categories.py` — `INTENT_CATEGORY_MAP`
4. `packages/core/narrare_core/prompts/route_table.py` — `ROUTE_CONFIGS`
5. `packages/core/narrare_core/prompts/route_table_intents.py` — `INTENT_TO_CATEGORY` and `INTENT_TO_MODE`
6. `packages/core/narrare_core/prompts/_bundled/{category}/{lang}/{mode}/system.md` — one directory per locale
7. `scripts/architecture/prompt-surface-manifest.yaml` — the ADR-037 route block (29 blocks today, of which 24 are `routeable: true`)
8. `scripts/architecture/adoption-registry.yaml` — the ADR-025/038 adoption entry (`version: "2.0.0"`)

Existing checks cover parts of this (`check_prompt_surface_contract.py` reads the
manifest against the route table; `check_locale_sync.py` checks per-group locale
parity; `check_adoption.py` reads the registry), but **no single check answers the
whole question** — "does this intent exist in every surface, with the same
category and mode?" — and each check fails with its own vocabulary, so an author
learns the answer one red gate at a time, across several commits. This is the
throughput cost: a 30-member set with an 8-surface write amplification.

### Decision

Add **one** parity gate, `scripts/check_intent_parity.py`, that reads the
declaration surfaces above and reports every disagreement among them as a single
table:

- `LLMIntent` members ↔ `INTENT_CATEGORY_MAP` keys ↔ `INTENT_TO_CATEGORY` keys
  ↔ `INTENT_TO_MODE` keys ↔ `INTENT_PROFILES` keys ↔ `ROUTE_CONFIGS` keys;
- `INTENT_TO_CATEGORY[i]` keys exist in `INTENT_CATEGORY_MAP` (key-set only; the
  two are **different taxonomies** — model routing (ADR-001) vs prompt category —
  and disagree by design for CHAT, SUMMARIZE, EXTRACT, FACT_EXTRACT and SUGGEST).
  Corrected after T14a measured the surfaces: the earlier "values are equal" claim
  was false and would have made the gate demand a rename of one taxonomy.
- `INTENT_TO_CATEGORY[i]` == the `category` of the route block for `i`, and
  `INTENT_TO_MODE[i]` == `ROUTE_CONFIGS[i].mode` for every intent;
- the prompt directory `_bundled/{category}/{lang}/{mode}/system.md` exists for
  every (intent, locale) pair that ADR-026's locale policy requires — `en` for every
  group, `en`/`de`/`fr` only for meta/universal — using the intent's own resolved
  category and mode. (Corrected after T14b: a flat three-locale grid describes no
  real group; `writing/` ships `en` only, and the literal rule emitted 44 violations
  on the pristine tree.)
- the manifest has exactly one route block per gateway-routed intent, and each
  block's `category`/`mode`/`intent` agree with the route table;
- the adoption registry has an entry for every routed intent and **no** entry for a
  non-existent intent. The registry is keyed by prompt path
  (`prompt_path_compliance: {category}/{mode}`), so several intents share one entry:
  46 entries cover the 24 routed intents (measured in T14b).

The gate is **comparison only**. It does not generate, does not move authority
out of the manifest or the registry, and does not relax ADR-037/ADR-038/ADR-045.
A single documented exemption list (in the script, keyed to ADR-025) covers
`EMBED`, which is deliberately not gateway-routed.

Not chosen (recorded so the choice is not re-litigated): **full derivation** of the
eight surfaces from one source. It would delete the manifest and the registry as
independently reviewable artifacts, weakening the two governance mechanisms that
ADR-037/038 built — a much larger decision than a throughput fix justifies.

### Acceptance criteria

1. `scripts/check_intent_parity.py` exits 0 on the pristine tree and prints a
   one-line summary (`30 intents, 24 routed, 0 disagreements`; the earlier 29 counted
   every manifest block including the 5 marked `routeable: false` — corrected after
   T14a measured the real surfaces).
2. Each of the six relationship families above has at least one test that mutates a
   surface and asserts a non-zero exit with a message naming the intent and the two
   surfaces that disagree.
3. The gate runs at commit time, in the local architecture surface and in the CI
   architecture job (same wiring pattern as P1's gate).
4. No existing gate is removed, narrowed, or made non-blocking.
5. Adding a new intent becomes: edit the enum once, then run the gate, which lists
   the remaining seven surfaces with the exact values they must contain.

### Risks

| Risk | Mitigation |
|---|---|
| The gate becomes a fourth overlapping checker whose failures contradict the existing three | it reports *disagreement*, never a rule of its own; the six families are stated in the spec and each is pinned by a mutation test |
| A gate that only compares Python structures misses the prompt directories | locale/directory existence is one of the six families, not an afterthought |
| Governance layer gets "simplified" later because a gate now exists | ADR-037/038/045 are cited as preserved; the spec's Non-Goals state it, and the script's docstring repeats it |

---

## 5. P3 — Gate tiering and a scoped slice command

### Problem (measured)

The commit stage holds 36 of 41 hooks, including two that are whole-project by
nature:

- `openapi-regenerate` (default `pre-commit` stage, `files: ^(apps/api/|packages/core/)`)
  imports the entire FastAPI application to rewrite `docs/reference/openapi.json`,
  and it *mutates* the tree during a commit.
- `typecheck-frontend` (explicit `pre-commit` stage, `always_run: true`) runs
  `tsc --noEmit` over the whole frontend **even on commits that touch no TypeScript
  at all**, because `always_run` overrides its `types: [tsx]` filter.

Meanwhile the push stage holds only `pyright`, `pyright-tests` and `bandit` — the
three hooks that are already correctly tiered. The asymmetry means the developer
pays the expensive work at the moment they want the fastest possible feedback, and
the corresponding configuration-was-wrong class of error (a stale OpenAPI file) is
still caught in CI regardless. Wall-clock cost of the two hooks is **not** measured
in this spec; the implementing task records before/after timings in its report
rather than asserting a number here. For scale, ADR-097 measured whole-project
pyright at 47.2s and staged-scope pyright at ~0.35s per file.

### Decision

1. **Move exactly two hooks** from `pre-commit` to `pre-push` in
   `.pre-commit-config.yaml`: `openapi-regenerate` and `typecheck-frontend`. Both
   change only their `stages:` value; their `entry`, `files`/`always_run` and
   `types` are untouched.
2. **Everything else stays.** In particular `pyright-tests-staged`, `pyrefly`,
   `biome-frontend`, `check-testid`, `validate-i18n`, `secrets-gitleaks`,
   `ruff-lint`, `ruff-format`, `architecture-constraints`, `prompt-structure`,
   `type-ignore-discipline`, `python-file-size` and `frontend-file-size` remain
   commit-time. `pyright`, `pyright-tests` and `bandit` remain push-time. The
   `adoption-score` (manual) and `conventional-commits` (commit-msg) stages are
   untouched.
3. **New scoped command** `verify-slice`, variadic over paths. Its contract: it
   lints *and* type-checks *and* test-runs **only** the given paths, and it
   additionally runs the scoped frontend checks when a given path is under
   `packages/web/`. It is explicitly **not** a substitute for `just verify`; the
   two-hook move is the only thing that reduces what a commit pays for, and no
   hook's coverage moves into this recipe.
4. **`just verify` and `just verify-quick` are unchanged.** `verify` stays the
   full local gate (`check` + `test-all`); `verify-quick` stays unit + frontend
   tests. `verify-slice` is additive.
5. **No CI change.** `.github/workflows/ci.yml` is not edited by this program
   beyond P1's and P2's additive steps. In particular the architecture job's
   `export_openapi.py --check` step and the frontend job's TypeScript step stay
   exactly as they are — the two hooks that moved to push therefore lose *no*
   protection, because CI was and remains the authority that catches them.
6. **The tiering is recorded in a document that names it**, and pinned
   machine-side so it cannot silently regress. See the plan for the file and the
   checker; the record deliberately points at the CI gate SSOT (ci.yml header
   table + CONSTRAINTS §6, per ADR-098) rather than restating any CI gate.

### Acceptance criteria

1. `.pre-commit-config.yaml` has exactly five push/other-stage hooks: `pyright`,
   `pyright-tests`, `bandit` (push), `adoption-score` (manual),
   `conventional-commits` (commit-msg) — plus the two newly moved hooks at push.
   No hook loses stage status silently.
2. A machine check fails if any hook other than the frozen allowlist declares
   `pre-push`, and fails if either moved hook returns to the commit stage.
3. The implementing task's report contains measured before/after wall-clock for a
   commit touching one backend file and one TSX file.
4. `verify-slice` on a Python path runs ruff (check + format), pyright (correct
   config for `tests/` vs production paths) and the matching pytest files, and on
   a `packages/web/` path additionally runs the scoped frontend check; it does not
   run integration or E2E tests.
5. `just verify` still runs `check` + `test-all` and passes.
6. CI is byte-identical apart from the additive P1/P2 steps.

### Risks

| Risk | Mitigation |
|---|---|
| Moving `openapi-regenerate` means a stale `docs/reference/openapi.json` reaches the push/CI stage instead of failing at commit | CI's architecture job already runs `export_openapi.py --check` and stays blocking; the hook still runs before the branch can be pushed |
| `typecheck-frontend` at push lets a TS error into a commit | `biome-frontend` and `check-testid` remain at commit time, CI's frontend job stays blocking, and the push stage runs within seconds of the commit |
| `verify-slice` gets used as "the" gate and integration regressions slip through | the recipe's own help text and the tiering document say it is not a substitute; `just verify` is unchanged and remains the pre-merge gate |
| Tiering silently reverts during a later hook edit | machine-pinned by the new checker, not by prose |

---

## 6. P4 — Review and report policy

### Problem (measured)

- Root `AGENTS.md` mentions review in exactly one line (line 58, "Review
  non-trivial changes (Reviewer subagent, edit: deny)") with no threshold, no
  batching rule and no report rule.
- The package caps (≤3 files / ≤250 new LOC) live in
  `.opencode/agents/NarrareDevCoordinator.md:300-311` and are restated in every
  plan's Global Constraints — three locations, one fact, no check.
- `docs/development/quality-gates.md` — the committed gate SSOT — says nothing
  about review or reports.
- The plan house style requires a report file for *every* task; the reports
  directory already holds 26 files for PLAN-001. There is no stated threshold at
  which a report is required, so a two-line change and a cross-layer change are
  treated identically by the rule and differently in practice.
- The result is inconsistent in both directions: trivial slices get a review round
  and a report file they do not need, and batches of related slices get one review
  where an individual one was worth it.

### Decision

Write the policy down, in the two documents a developer or coordinator actually
reads, with explicit thresholds:

1. **Per-task report file — required when** a task changes ≥2 production files, or
   adds ≥80 new production LOC, or crosses a layer boundary, or changes a governed
   surface (`docs/_shared/CONSTRAINTS.md`, an ADR, `scripts/architecture/*`,
   `.github/workflows/ci.yml`, `justfile`, `.pre-commit-config.yaml`). Otherwise the
   commit message body is the record and no report file is created. (Test files do
   not count toward the file count, matching the existing cap convention.)
2. **Batch review — allowed when** the tasks are in the same layer, share a file
   cluster, and at least one task in the batch met the report threshold; the batch
   then carries one reviewer pass whose report names every task it covers.
3. **Per-task review — mandatory** when a task adds or renames a Protocol /
   contract, changes a manifest or registry, changes the public shape of an API
   response, or edits a governed surface (same list as 1). These are never batched.
4. The caps and thresholds appear **once** as normative text (in
   `docs/development/quality-gates.md`) and are **referenced**, not restated, from
   `AGENTS.md` and the coordinator agent file.
5. A machine check asserts the numbers agree wherever they appear, so "referenced,
   not restated" cannot decay into "three copies, one wrong".

### Acceptance criteria

1. `AGENTS.md` and `docs/development/quality-gates.md` both state the report
   threshold, the batch rule and the mandatory-review list; the coordinator agent
   file points at them instead of restating the caps.
2. The caps (≤3 files / ≤250 new LOC) are stated once as normative text and
   referenced elsewhere.
3. A checker fails if the caps or the report threshold differ between the files
   that mention them, and fails if the normative text disappears.
4. This program's own plan obeys the new policy: its 15 tasks each state whether a
   report file is required, and the answer follows the threshold rather than the
   house-style default.

### Risks

| Risk | Mitigation |
|---|---|
| Lowering the report requirement loses evidence for later archaeology | the commit message is the substitute and is already mandatory; the threshold is set so anything non-trivial still produces a report |
| A number in a document is not the same as a number in a tool | the machine check pins the numbers; the policy that *cannot* be pinned is kept to three sentences |
| Coordinator behaviour does not follow the doc | the coordinator agent file points at the normative section, so there is one text to follow, and it is the one the coordinator already loads |

---

## 7. P5 — Feature scaffolder

### Problem (measured)

No scaffolder exists (`scripts/` holds 30 `check_*.py` and zero `scaffold_*` /
`new_*` scripts). Bringing up one feature currently means, by hand: the feature
document plus its `INDEX.md` row and frontmatter paths (verified by
`check_feature_path_accuracy.py`), the prompt directories across three locales
(verified by `check_locale_sync.py`), the eight intent declaration surfaces when a
new intent is involved (§4), test skeletons in the right directories, and a task
report stub. Each of those is a separate gate that fails on its own, so the cost of
the first commit of a feature is dominated by discovering which gate it tripped.

### Decision

Add a `new-feature` recipe (`new-feature <id> <layer...>`) backed by
`scripts/scaffold_feature.py`, which generates **only artifacts that are green on
arrival**:

- a feature document from the house template with valid frontmatter, listing only
  paths that already exist or that the same run creates;
- test skeletons in the correct directories for each named layer;
- a task-report stub following the report contract;
- a Protocol/contract stub when `core` is among the layers (RULE-03 requires the
  contract to exist first, so a contract stub *is* the first correct artifact);
- with an explicit `--with-intent <NAME>` flag: the full intent declaration set
  across the eight surfaces **and** the three locale prompt directories whose
  `system.md` files are structurally complete (frontmatter plus the required
  `## System Prompt` heading and the intent's short scope summary) — never a
  placeholder body.

It deliberately **does not** generate service, router, repository or component
stubs. A generated stub of those is precisely the half-implementation RULE-20
forbids, and it is where a scaffolder would do the most damage.

Its post-condition is a gate run: after writing, the scaffolder runs the scoped
architecture checks and the P2 parity gate, and exits non-zero if the scaffold is
not already green — so a generated feature either arrives clean or arrives with an
explicit, actionable failure.

Dependencies: it consumes the P1 catalog (for provider-touching features) and,
for `--with-intent`, it produces exactly what the P2 gate validates. It can
therefore land before P2, with P2's acceptance test scaffolding a throwaway feature
and running the parity gate over it — which is how the P5→P2 dependency is closed.

### Acceptance criteria

1. `new-feature <id> <layer...>` on an empty worktree produces a tree on which the
   scoped architecture checks and the P2 parity gate both pass, without any manual
   edit.
2. `--with-intent` produces a valid entry in all eight declaration surfaces and
   three structurally valid prompt files; the prompt-structure check passes on
   them.
3. The scaffolder refuses (non-zero exit, no partial tree) when the id already
   exists in any declaration surface.
4. No service, router, repository or component file is ever generated.
5. The tool is documented where a developer will look for it, and that document
   and the recipe land in the same task.
6. A test scaffolds into a temporary tree and asserts the gate-green post-condition;
   a second test asserts the refusal path.

### Risks

| Risk | Mitigation |
|---|---|
| The scaffolder becomes an excuse to ship incomplete features | it refuses to generate the stubs that would let that happen; acceptance criterion 4 is a test, not a guideline |
| Its generated prompt skeletons rot as the prompt standards evolve | the post-condition runs the real prompt checks, so rot shows up as a red scaffold immediately |
| It silently drifts from the eight surfaces when P2 adds a surface | the parity gate reads the surfaces, so a new surface that the scaffolder does not write fails the gate — the failure names the missing surface |

---

## 8. Open Questions

Each has a recommended default so nothing here blocks the wave. PO may overrule any
of them; the default is what the plan implements.

- **OQ-1 — Should any provider be `settings_editable: false`?** `ollama` takes no
  API key, so an "add provider key" form listing it is arguably noise. *Default:
  keep all seven `true`.* The catalog introduces the flag so a future ADR can flip
  one provider without code, but flipping it now would change behaviour beyond the
  defect fix this program is justified by.
- **OQ-2 — Does P1 add any provider?** *Default: no.* The catalog describes the
  existing seven. Adding a provider is a separate decision with its own fetcher,
  pricing and cache semantics, and mixing it into a de-duplication program would
  make the wave impossible to review.
- **OQ-3 — Which locales must `label_key` resolve in?** *Default: `en`, `de`, `fr`
  (RULE-16).* A locale the repository does not ship is not asserted.
- **OQ-4 — Should `verify-slice` also run frontend tests when no path is under
  `packages/web/`?** *Default: no.* Scoping is the point of the command; a backend
  slice should not pay for a frontend suite. Paths under `packages/web/` get the
  scoped frontend check.
- **OQ-5 — Where does P3's tiering record live?** *Default: a new
  `docs/development/pre-commit-gate-tiers.md`, scoped explicitly to local hook
  staging and pointing at the CI gate SSOT.* Recording it inside
  `docs/development/quality-gates.md` was considered and rejected: that file declares
  itself to mirror the ci.yml audit block, and local hook staging is not a CI gate,
  so adding it there would blur ADR-098's single-SSOT statement.

---

## 9. Sequencing, dependencies and landability

Task numbers are the plan's; the order below is the plan's execution order
(P1 → P3 → P4 → P5 → P2), as required.

| Task | Program | Depends on | Independently landable |
|---|---|---|---|
| T1–T7 | P1 | — (T2–T5 need T1; T6 needs T1–T5; T7 needs T6) | yes, in order |
| T8–T9 | P3 | T8 independent of P1; T9 needs T8 | yes, parallel to P1 |
| T10–T11 | P4 | T11 needs T10 | yes, parallel to P1/P3 |
| T12–T13 | P5 | T12 uses the P1 catalog; T13 needs T12 | yes after P1 |
| T14–T15 | P2 | T14 independent; T15 needs T14 **and** T12 (it scaffolds a feature and runs the gate over it) | yes, last |

**Document/reality coupling (binding on the plan).** A `just` recipe must land in
the same task as the document that names it: the documentation-drift check
(`doc-drift` hook, `scripts/check_doc_drift.py --governance-only`) validates
backtick-quoted `just <recipe>` references in `docs/**` against the real recipe set.
Task directories under `docs/superpowers/plans/` are excluded from that check, so
the plan may name recipes freely — but every *living* document that names
`verify-slice` (T8) or `new-feature` (T13) must be written in the task that adds
the recipe.

**Rollback.** Every task is a normal revert except T8, whose revert restores the
two hooks to the commit stage and leaves `verify-slice` as an unused recipe (its
document must be reverted with it). No task migrates data, so no task needs a
forward-repair path.
