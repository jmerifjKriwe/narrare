# Architecture Authority Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One normative page a new developer reads first, one process page for agents that no longer restates it, one ADR for the key-storage decision, and the architecture spec corrected where it names things that no longer exist.

**Architecture:** Two tiers, one state each. `docs/_shared/CONSTRAINTS.md` becomes the binding page (five rules + the shape of a capability + reading order); `AGENTS.md` keeps only process and points at it; the architecture spec keeps the reasoning and is allowed to age. Nothing is added to the governance surface: no new document, no new rule, no new gate.

**Tech Stack:** Markdown only. No code, no dependencies, no migrations.

**Spec:** `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` (authority, §8 governance budget) and `docs/_shared/CONSTRAINTS.md` (current rules). The plan implements the consolidation agreed in the session of 2026-10-28, not a new design.

## Global Constraints

- English only in every file this plan touches (repository rule 5).
- **No new rule, registry, check script, hook, required field or mandatory document** (spec §8). The structural contract moves existing §3/§4 decisions into the rules page; it does not decide anything new. Anything that reads like a new rule is a defect of this plan, not a liberty of the implementer.
- Numbers may be stale (owner ruling, 2026-10-28). Do **not** "fix" counts (recipes, hooks, CI jobs, ADR count, LOC). Fix only **paths, names and prescriptions** that send a reader to something that does not exist or describe the provider model wrongly.
- Conventional commit, `docs:` type, no `User-visible:` line (not `feat`/`fix`). No `--no-verify`.
- One commit for the whole change, not one per task: the five files are one statement (owner preference to consolidate; deviation from the skill's per-task commits, recorded in the commit body).
- Working tree must be clean apart from these five files before staging (`git status --porcelain` checked, deviations halt).

## Review Focus

The failure modes this change can introduce, most likely first. Each is pinned by a check in the task that owns it.

1. **An agent reads only `AGENTS.md` and never opens `CONSTRAINTS.md`.** After Task 3 the rules exist in exactly one file; the pointer must be unmissable and must say the file is normative.
2. **The rules page grows into a rulebook.** Above ~60 lines, it starts to age like the 1,389-line v1 `CONSTRAINTS.md`. The page's length is the maintenance budget; a reviewer counts lines.
3. **A path in the spec still points at nothing.** Every path the spec names must resolve on disk (`docs/adr/`, `generated/`, `knowledge-base/`, `Alembic`), except the dated §2 baseline, which is evidence and stays.
4. **The ADR claims an approval nobody gave.** It ships as `Proposed`; only the product owner flips it to `Accepted` (spec §8 requires explicit approval for the second store).
5. **The deduplication is cosmetic.** If `AGENTS.md` keeps a clause-by-clause paraphrase, the two copies drift again. The pointer paragraph must contain zero rule text.

---

### Task 1: The ADR for provider profiles and key storage

**Files:**
- Create: `docs/architecture/decisions/ADR-102-provider-profiles-and-key-storage.md`
- Modify: `docs/architecture/decisions/INDEX.md` (add one row above ADR-101)

**Interfaces:**
- Consumes: the WP2a design record (`docs/superpowers/specs/2026-10-26-wp2a-providers-catalog-settings-design.md`, approved 2026-10-27) and the code it produced (`app/kernel/secrets.py`, `app/kernel/llm/profiles.py`, `app/kernel/llm/resolution.py`).
- Produces: the decision text that Task 2 cites for the provider paragraph and Task 4 cites in §4, §7, §12.2 and §14. The filename is referenced verbatim by Task 2, so it must not change.

- [ ] **Step 1: Write the ADR**

Exact content:

```markdown
# ADR-102 — Provider profiles, per-task assignment and tiered key storage

> **Status:** ⏳ Proposed — awaiting the product owner's acceptance
> **Date:** 2026-10-28
> **Deciders:** Product owner
> **Amends:** the provider model in the v2 architecture spec §4 and §12.2

---

## Context

The v2 spec assumed one provider per process, declared in a hand-edited
`llm/_providers/catalog.yaml` (spec §2), so that "adding a provider is one catalog
entry" (§4, §12.2). The WP2a design measured that assumption against the product:
every user brings their own model and key, the model set moves faster than this
repository, and a process-wide environment variable cannot name which
configuration an audited call used.

Three facts forced the change:

- One provider per process means every user of a process shares it; the product is
  local-first with one fixed local user today and a hosted future (ADR-101).
- Prices, context windows and output limits change monthly; a hand-maintained
  catalog ages between releases.
- An API key is a secret. It cannot sit in plaintext beside the row that uses it,
  and it cannot live only in a process environment.

## Decision

**Providers are data, not code.** A user owns `ProviderProfile` rows
(`app/kernel/llm/models.py`): `kind` is `fake` or `openai-chat`, plus `base_url`,
`model`, optional `context_window` / `max_output_tokens` / `temperature` /
`request_timeout`, and a key. `TaskAssignment` names one profile per task key
(`writing.continuation`, `chat.ask`, `knowledge.extract-entities`,
`knowledge.check-consistency`, `settings.test`). Resolution is exact task key →
prefix → the user's default → environment → `fake`
(`app/kernel/llm/resolution.py`). A new vendor on the OpenAI chat shape is a
profile row and no code; a new API shape is an adapter plus one `PROFILE_KINDS`
value.

**Model metadata comes from a vendored snapshot.**
`app/kernel/llm/data/models.json` is a models.dev snapshot refreshed by
`python -m app.kernel.llm.data.refresh`; an entry the snapshot does not know
prices a call as `NULL`, never as zero.

**A key has two storage tiers** (`app/kernel/secrets.py`). The OS keychain comes
first, behind a usability probe that rejects a backend returning null or failing
writes; otherwise the key is Fernet-encrypted under `NARRE_SECRET_KEY` in the row.
`NARRE_KEYRING=off` forces the Fernet tier. Neither tier available raises
`NoKeyStoreError` and creates no row (HTTP 503). The plaintext key exists only in
the create response; the stored hint is its last four characters.

## Consequences

- The second store (the OS keychain) is deliberate. Spec §8 requires the product
  owner's explicit approval for a boundary crossing; the WP2a design acceptance of
  2026-10-27 is that approval, and this record is its dated trace.
- Reversing the key tiers means re-encrypting or re-prompting every stored key —
  expensive enough to belong in an ADR rather than in a diff.
- Spec §4 and §12.2 are superseded on this point: "adding a provider is one
  catalog entry" becomes "adding a provider is one profile row".
- E2E pins the Fernet tier with a fixed test key and `NARRE_KEYRING=off`
  (`app/kernel/testing/stack.py`), so no test touches a developer's keychain.
- `LlmCall.profile_id` and `cost_usd` now name the configuration a call used; the
  audit table carries two more columns than §9 D14 described.
```

- [ ] **Step 2: Add the index row**

Insert above the ADR-101 row in `docs/architecture/decisions/INDEX.md`, matching
the existing table's column order and status glyph:

```markdown
| [ADR-102](ADR-102-provider-profiles-and-key-storage.md) | Providers are per-user profiles with per-task assignment and two key-storage tiers — the hand-edited catalog is gone | ⏳ | 2026-10-28 |
```

- [ ] **Step 3: Verify the paths in the new ADR resolve**

Run:

```bash
cd /home/kiesow/projects/narrare && for p in app/kernel/secrets.py app/kernel/llm/profiles.py app/kernel/llm/resolution.py app/kernel/llm/models.py app/kernel/llm/data/models.json app/kernel/testing/stack.py; do test -f "$p" && echo "ok $p" || echo "MISSING $p"; done
```

Expected: six `ok` lines, no `MISSING`.

- [ ] **Step 4: Verify the index links resolve**

Run:

```bash
cd /home/kiesow/projects/narrare && test -f docs/architecture/decisions/ADR-102-provider-profiles-and-key-storage.md && grep -c "ADR-102" docs/architecture/decisions/INDEX.md
```

Expected: exit 0, and `1`.

### Task 2: `CONSTRAINTS.md` becomes the normative page

**Files:**
- Modify: `docs/_shared/CONSTRAINTS.md` (full replacement, 22 → ≤ 60 lines)

**Interfaces:**
- Consumes: Task 1's ADR filename (`../architecture/decisions/ADR-102-provider-profiles-and-key-storage.md`); the facts verified in the audit: `capability.yaml` fields are `id, title, path, needs, nav`; `setup` is the smallest capability (12 files), `writing` the one with the prompt and streaming path; `docs/superpowers/specs/` holds six dated work-package designs.
- Produces: the URL Task 3 points at, and the exact rule-2 wording that Task 4 must not contradict in the spec.

- [ ] **Step 1: Replace the file with the text below**

```markdown
# Narrare — Standing Constraints

The five rules every change obeys, the shape of a capability, and where to read
what. The architecture authority — reasoning, boundaries and the governance
budget — is the [v2 architecture spec](../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md).

## The five rules

1. **One capability is one folder** under `app/capabilities/<name>/`. A capability
   never imports another capability; shared domain lives in `app/kernel/`.
2. **A capability is done only with a green E2E** that drives the real UI, the real
   backend and the real database. The only permitted fake is the LLM provider at
   its boundary: a provider profile of kind `fake`, chosen by configuration, never
   a test branch.
3. **No side effect in the request path** beyond the request's own transaction.
4. **Every user-owned row carries `user_id`**; data access goes through the scoped
   repository base.
5. **English in code, tests and developer documentation; user-visible text in en,
   de and fr** through the i18n catalog. A missing key is a build error.

## The shape of a capability

- Its facts are in `capability.yaml` — `id`, `title`, `path`, `needs`, `nav` — and
  a field exists only while two generated views read it. Views are written by
  `just generate` and never edited by hand.
- Its code is `router.py` (delegates immediately), `service.py` (the logic),
  `repository.py` (its tables), `schemas.py`, `tests/`, `e2e/`, and its UI in
  `web/` with the `routes.tsx` the shell mounts.
- Imports point one way: `api → capabilities → kernel`. A capability reaches the
  shell through `@shell/*`; the shell reaches a capability only through the
  generated tables.
- A provider is a profile row (`fake` or `openai-chat`), assigned per user and task
  in `/settings`. A new vendor on that API shape needs no code; a new API shape is
  an adapter plus one `PROFILE_KINDS` value. Keys and their two storage tiers are
  decided in [ADR-102](../architecture/decisions/ADR-102-provider-profiles-and-key-storage.md).
- A second data store, a global store or a migration tool crosses a boundary and
  needs the product owner's explicit approval (spec §8).

## Read this in this order

1. [`README.md`](../../README.md) — what the product is, and how to run it.
2. This page — the rules and the shape.
3. One capability folder end to end: `app/capabilities/setup/` (the smallest), then
   `app/capabilities/writing/` for the prompt and streaming path.
4. [`TESTING.md`](../../TESTING.md) — the layers, the gates and how to run them.
5. The [architecture spec](../superpowers/specs/2026-10-21-narrare-v2-architecture-design.md)
   — why, not how — then the [ADRs](../architecture/decisions/INDEX.md) for the
   choices that are expensive to reverse. The dated designs under
   `docs/superpowers/specs/` are the records of finished work packages; read one
   only when a comment points at it.

## Changing a rule

Adding a sixth rule, a registry, a check script, a hook, a required field or a
mandatory document is forbidden by default: report `NEEDS-APPROVAL` with the
failure it prevents, the effort it creates per change, and the cheaper
alternative (spec §8).
```

- [ ] **Step 2: Verify the links resolve and the page stays short**

Run:

```bash
cd /home/kiesow/projects/narrare && for p in README.md TESTING.md docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md docs/architecture/decisions/INDEX.md docs/architecture/decisions/ADR-102-provider-profiles-and-key-storage.md app/capabilities/setup app/capabilities/writing; do test -e "$p" && echo "ok $p" || echo "MISSING $p"; done; wc -l docs/_shared/CONSTRAINTS.md
```

Expected: seven `ok` lines and a line count **≤ 60**.

- [ ] **Step 3: Verify no rule text was added that is not already decided**

Run:

```bash
cd /home/kiesow/projects/narrare && rg -n "^[0-9]+\." docs/_shared/CONSTRAINTS.md
```

Expected: exactly five numbered lines, the same five subjects as before (folder,
E2E, side effects, `user_id`, language). Any sixth numbered rule fails this step.

### Task 3: `AGENTS.md` stops restating the rules

**Files:**
- Modify: `AGENTS.md:11-28` (the `## Rules` section, replaced by a three-line pointer)

**Interfaces:**
- Consumes: the file path from Task 2 (`docs/_shared/CONSTRAINTS.md`).
- Produces: nothing other tasks read. Every other section of `AGENTS.md` (`Verify`, `Follow-ups`, `Plan mode`, `Tools`, `Git`) stays byte-identical.

- [ ] **Step 1: Replace the Rules section**

Old text, exactly (lines 11-28):

```markdown
## Rules

- One capability is one folder under `app/capabilities/<name>/`, including its
  frontend under `web/`; routes are generated, so a new one needs `just generate`.
  A capability never imports another capability; shared domain lives in
  `app/kernel/`, shared UI in the shell.
- A capability is done only with a green E2E that drives the real UI, the real backend
  and the real database. The only permitted fake is the LLM provider at its boundary.
- No side effect in the request path beyond the request's own transaction.
- Every user-owned row carries `user_id`; data access goes through the scoped
  repository base.
- English in code, comments, tests and developer documentation. User-visible text in
  en, de and fr through the i18n catalog; a missing key is a build error.
- Never add a rule, registry, check script, hook, required field or mandatory document.
  Report `NEEDS-APPROVAL` with the failure it prevents, the effort it creates per
  change, and the cheaper alternative.
- A boundary can be reopened. The spec's §8 names the procedure: three statements
  and the product owner's explicit approval.
```

New text:

```markdown
## Rules

The five standing rules, the shape of a capability and the reading order are
normative in [`docs/_shared/CONSTRAINTS.md`](docs/_shared/CONSTRAINTS.md) and are
not restated here — read that page before your first change. A change that
violates one of its rules is a review finding, not a style question. The
governance budget (spec §8) lives there too: a new rule, gate or mandatory
document is proposed, never added.
```

- [ ] **Step 2: Verify no rule text survived in `AGENTS.md`**

Run:

```bash
cd /home/kiesow/projects/narrare && rg -in "user-owned row|missing key is a build error|only permitted fake|never imports another capability|NEEDS-APPROVAL" AGENTS.md
```

Expected: **no output** (exit 1). Any hit means a paraphrase survived.

- [ ] **Step 3: Verify the pointer and the untouched sections**

Run:

```bash
cd /home/kiesow/projects/narrare && rg -n "docs/_shared/CONSTRAINTS.md" AGENTS.md && rg -c "^## " AGENTS.md
```

Expected: one hit for the path (the `## Rules` pointer) and `6` section headings (`Rules`, `Verify`, `Follow-ups`, `Plan mode`, `Tools (optional)`, `Git`).

### Task 4: The spec stops naming what does not exist

**Files:**
- Modify: `docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md` at the eight places below, plus one clause in §2 and one bullet in §14.

**Interfaces:**
- Consumes: Task 1's ADR (`ADR-102`) and Task 2's rule-2 wording (the fake is a profile of kind `fake`); the paths verified in the audit (`docs/architecture/decisions/`, `app/generated/`, `web/lib/generated/`, `app/capabilities/knowledge`).
- Produces: nothing other tasks read. Counts, tables and the §2 baseline stay untouched.

- [ ] **Step 1: §3, two kernel tree lines**

Old: `    db/          session factory, scoped repository base, Alembic tree`
New: `    db/          session factory, scoped repository base, schema from the models`

Old: `    llm/         provider catalog, fetch strategies, fake provider`
New: `    llm/         provider profiles, vendored model catalog, audit, one chat adapter`

(`fetch strategy` survives only on the embedding side, `app/kernel/embeddings/__init__.py:4`; the chat side has one adapter since WP2a.)

- [ ] **Step 2: §3, the capability folder name**

Old: `    knowledge-base/   same shape`
New: `    knowledge/        same shape`

- [ ] **Step 3: §3, the generated views and the docs paths**

Old:

```text
generated/       capability registry (Python + TypeScript), docs index, TS client
docs/
  adr/           ≤ 15 decisions
  user/          generated user documentation (en, de, fr)
scripts/         generate · new-capability  (two, not 84)
```

New:

```text
app/generated/       capability registry (Python); web/lib/generated/ the TS views
docs/
  architecture/decisions/  ≤ 15 ADRs
  user/              generated user documentation (en, de, fr)
scripts/             generate · new-capability · export-openapi · secrets
```

- [ ] **Step 4: §4, how a provider is added**

Old: `New capability: one folder, its facts file, prompt, code, tests, `e2e/`. New
provider: one catalog entry, plus one fetch strategy only if it is a new API shape.`

New: `New capability: one folder, its facts file, prompt, code, tests, `e2e/`. New
provider: one profile row in `/settings`, plus an adapter and one `PROFILE_KINDS`
value only if it is a new API shape (ADR-102).`

- [ ] **Step 5: §7, the fake provider**

Old: `**The only fake sits at the outermost boundary: the LLM provider** — and any other
external, paid or non-deterministic service. The fake provider is a first-class
provider-catalog entry with the same interface as the real ones, so routing, prompt
composition, streaming and persistence all execute the production code path.`

New: `**The only fake sits at the outermost boundary: the LLM provider** — and any other
external, paid or non-deterministic service. The fake provider is a provider profile
of kind `fake` with the same interface as the real ones, so routing, prompt
composition, streaming and persistence all execute the production code path.`

- [ ] **Step 6: §11, the feature corpus**

Old: `The feature files themselves are not
migrated: a capability's user-visible documentation is generated (D5), and git
history keeps the old corpus.`

New: `The feature files themselves are not
migrated into a capability: a capability's user-visible documentation is generated
(D5), and `docs/features/` stays in the tree as the v1 product history, explicitly
non-binding — its `INDEX.md` says so.`

- [ ] **Step 7: §12.2, the success criterion**

Old: `2. **Adding a provider is one catalog entry** — and a fetch strategy only for a new API
   shape.`

New: `2. **Adding a provider is one profile row** — and an adapter only for a new API
   shape.`

- [ ] **Step 8: §2, one clause on the historical catalog**

In the provider note of §2, after `One hand-edited catalog feeds two generated
artefacts (Python, TypeScript).` add: `WP2a replaced that file with per-user profiles
and a vendored models.dev snapshot (ADR-102); the row records the surface as it stood
on 2026-10-21.`

- [ ] **Step 9: §14, one bullet for the provider layer**

Append to §14's list:

```markdown
- **Providers are data, not a catalog file (§4, §12.2).** Per-user
  `ProviderProfile` rows with per-task assignment, a vendored models.dev snapshot
  for prices and limits, and two key-storage tiers: OS keychain first, then
  Fernet under `NARRE_SECRET_KEY` (`app/kernel/secrets.py`). The audit names the
  profile and a real cost. The decision and its consequences are ADR-102.
```

- [ ] **Step 10: Verify the false statements are gone**

Run:

```bash
cd /home/kiesow/projects/narrare && rg -n "one catalog entry|catalog entry|knowledge-base|docs/adr/|Alembic tree|provider-catalog entry" docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md
```

Expected: **no output**, except one allowed hit in §2 (`catalog.yaml`, the dated
baseline is evidence and stays — `catalog entry` itself must not appear).

- [ ] **Step 11: Verify the corrected paths resolve**

Run:

```bash
cd /home/kiesow/projects/narrare && for p in docs/architecture/decisions app/generated web/lib/generated app/capabilities/knowledge docs/features/INDEX.md; do test -e "$p" && echo "ok $p" || echo "MISSING $p"; done
```

Expected: five `ok` lines.

- [ ] **Step 12: Verify nothing else in the spec changed**

Run:

```bash
cd /home/kiesow/projects/narrare && git diff --stat docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md && git diff -U0 docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md | rg "^[+-]" | rg -v "^(\+\+\+|---)" | wc -l
```

Expected: one file, and a changed-line count **≤ 44** (12 replacements plus the §2
clause and the §14 bullet). A larger diff means a count or a table was "fixed" —
revert it.

### Task 5: The stale devcontainer promise in `CONTRIBUTING.md`

> Out of the five-file set but part of "a new developer reads this": the paragraph
> points at a `.devcontainer/` that `ad3aaf63` deleted. Drop the task if the owner
> rules it out of scope; do not decide that alone.

**Files:**
- Modify: `CONTRIBUTING.md:26-28` (the `**DevContainer (VS Code):**` paragraph, deleted)

**Interfaces:**
- Consumes: the verified absence of `.devcontainer/` in the tree.
- Produces: nothing.

- [ ] **Step 1: Delete the paragraph**

Remove the whole paragraph beginning `**DevContainer (VS Code):**` including its
trailing blank line.

- [ ] **Step 2: Verify neither the promise nor the path remains**

```bash
cd /home/kiesow/projects/narrare && rg -in "devcontainer" CONTRIBUTING.md README.md; test -d .devcontainer || echo "no .devcontainer"
```

Expected: no `rg` output, and `no .devcontainer`.

### Task 6: One commit, verified before staging

**Files:**
- Stage: the five (or six, with Task 5) files only.

**Interfaces:**
- Consumes: all tasks above.
- Produces: the branch and commit the review reads.

- [ ] **Step 1: Check the working tree against the expected file set**

```bash
cd /home/kiesow/projects/narrare && git status --porcelain
```

Expected exactly:

```text
 M AGENTS.md
 M CONTRIBUTING.md            (only if Task 5 ran)
 M docs/_shared/CONSTRAINTS.md
 M docs/architecture/decisions/INDEX.md
 M docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md
?? docs/architecture/decisions/ADR-102-provider-profiles-and-key-storage.md
```

Any other path (including `_scratch/`, `docs/superpowers/follow-ups.md`, `justfile`)
halts the commit; report it, do not stage it.

- [ ] **Step 2: Stage and re-check**

```bash
cd /home/kiesow/projects/narrare && git add AGENTS.md CONTRIBUTING.md docs/_shared/CONSTRAINTS.md docs/architecture/decisions/INDEX.md docs/architecture/decisions/ADR-102-provider-profiles-and-key-storage.md docs/superpowers/specs/2026-10-21-narrare-v2-architecture-design.md && git diff --cached --stat
```

Expected: the same six paths, nothing else.

- [ ] **Step 3: Commit**

```bash
git commit -m "docs(architecture): one normative page, and the records name the tree as it is" -m "The five standing rules existed twice — AGENTS.md restated all five and CONSTRAINTS.md held the normative text — and the copy had already drifted: rule 2 still called the fake provider a catalog entry after WP2a replaced the catalog with per-user profiles. CONSTRAINTS.md is now the single page a new developer reads first: the five rules, the shape of a capability (moved from spec §3/§4, not new), and a reading order that names the one capability folder to copy and demotes the six work-package designs to what they are.

AGENTS.md keeps process only and points at that page; the rules are not paraphrased there, so they cannot diverge again.

The spec keeps the reasoning and is allowed to age: only the statements that sent a reader to something that does not exist were corrected — the Alembic tree, docs/adr/, generated/, knowledge-base/, and the three sentences that made 'adding a provider' a catalog edit. Counts stay as they are; the owner ruled stale numbers acceptable and §2 is dated evidence.

ADR-102 records the provider-profile and key-storage decision that WP2a took with the owner on 2026-10-27 and that spec §8 requires as a dated approval for the second store. It ships Proposed; only the owner accepts it.

No rule, gate or document is added (spec §8)."
```

- [ ] **Step 4: Verify the tree and the commit**

```bash
cd /home/kiesow/projects/narrare && git status --porcelain && git show --stat --oneline HEAD
```

Expected: a clean tree and a commit whose stat lists the same six paths.

## Self-Review

**Spec coverage.** The owner's two goals map to Task 2 (binding rules central) and Task 3 (one page a newcomer reads, no rule duplication). Task 1 closes the one decision the audit found homeless (secret tier, §8 boundary crossing). Task 4 removes the statements a newcomer would follow into nothing. Task 5 is the one leftover onboarding lie. Deliberately not covered: variant C (generated as-built view) — rejected; stale counts — owner ruling; the six WP design specs — they stay as dated records, now demoted by the reading order.

**Step scan.** Every step names the exact file and, where wording matters, the exact string. The only judgement left to the implementer is line wrapping.

**Type consistency.** The ADR filename is used identically in Task 1 (create), Task 2 (link), Task 4 (three citations) and Task 6 (staging). The rule-2 wording ("provider profile of kind `fake`") appears in Task 2 and matches Task 4's §7 replacement.

**Review Focus.** Each of the five lines has a check: 3→Step 2 (pointer), 2→Task 2 Step 2 (≤60 lines) and Step 3 (exactly five numbered rules), 1→Task 4 Steps 10-11, 4→Task 1 Step 1 (`Proposed`) plus the commit body, 5→Task 3 Step 2 (`rg` returns nothing).

**Proportion.** The plan is mostly verbatim payload, which is the deliverable here; there is no code to transcribe.

## Execution notes

- Branch: `docs/architecture-authority`, one commit, PR titled `docs(architecture): one normative page, and the records name the tree as it is`. A docs-only change may also go straight to `main` under the repository's lean path; a PR is recommended only because the ADR records a boundary-crossing approval and benefits from a review trail.
- After the owner accepts ADR-102, flip its status line to `✅ Accepted` and the index glyph to `✅` with the acceptance date — a second tiny commit, not part of this plan.
- Follow-ups: if the review finds anything open (for example a spec sentence still naming something absent), append a row to `docs/superpowers/follow-ups.md` before merging, per the repository rule.
