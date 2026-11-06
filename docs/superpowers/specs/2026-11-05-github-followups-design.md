# GitHub platform follow-ups — design

**Date:** 2026-11-05 · **Index:** #607
**Children still open:** #596, #597, #598, #599, #600, #602, #603, #604, #605, #606, #610
(#601 was fixed on `main` in 673306b3 before this wave started and is closed.)

## Intent

The platform wave (PR #594, design
`docs/superpowers/specs/2026-11-05-github-platform-design.md`) shipped one
required check, one map, one Dependabot config and a security baseline. Its
follow-ups are twelve findings; one is already fixed. Four of the remaining
eleven are mechanical, four are real coverage gaps, and three record something
GitHub does not offer this repository today. The wave that closes them must not
pretend the last group is a code defect, and must not leave the gaps as prose.

## What is true today (probed 2026-11-05, not read from the issue text)

1. **The branch is one commit behind.** `main` is 673306b3 ("Dependabot accepts
   the Actions cooldown again", `Closes #601`); the worktree is b38f11e2. The
   worktree still carries `semver-major-days: 14`, `main` does not. The wave
   starts from `narrare/main` (the remote is `narrare`, not `origin`), so #601
   needs no task.
2. **#596 cannot be enabled from this repository.** It is public and
   **user-owned** (`private: false`, no organisation). GitHub's docs put both
   features behind Secret Protection, which is org-scoped (Team/Enterprise):
   non-provider patterns are documented for "Organization-owned repositories on
   GitHub Team with GitHub Secret Protection", validity checks for Team and
   Enterprise only. The map's "Re-applying the settings PATCH is the fix" is
   therefore wrong.
3. **#602 cannot flip yet.** `actionlint`'s latest release is **1.7.12**
   (2026-03-30) and rhysd/actionlint#732 (`$/` support) is still **open**. The
   tree has **14** `zizmor: ignore[self-repository]` site comments (the issue
   says six) and **16** mentions of the pin `1.7.7`; both counts matter to the
   bump.
4. **#604's scorecard proof already exists.** `scorecard.yml` ran three times on
   `main` (runs 42080606005, 42086972305, 42088177236), and code scanning holds
   three `Scorecard` analyses on `refs/heads/main` (`supply-chain/local`,
   `supply-chain/branch-protection`, `supply-chain/online-scm`).
5. **#604's nightly proof does not exist.** No `schedule` or `workflow_dispatch`
   run of `nightly.yml` has completed; the only listed run is a 0-second
   failure from a branch during the gate proof.
6. **#603's digest is known and checkable.** `pgvector/pgvector:pg17` is the
   index digest `sha256:7d0a41464797aeb9862dfdc0bbf1526b82cfd324cdd8036df19e3545f4a9ccb8`
   (tag moved 2026-10-31). Docker Hub's tag API returns exactly that digest.
   `rhysd/actionlint:1.7.12` resolves to
   `sha256:b1934ee5f1c509618f2508e6eb47ee0d3520686341fec936f3b79331f9315667`
   by the same API.
7. **#597's widening is green today.** Full `uv export --locked` (1030
   requirements, vs 723 with `--no-dev`) + `uvx pip-audit==2.10.1 --strict` →
   "No known vulnerabilities found"; `pnpm audit --audit-level high` (all
   scopes) → "No known vulnerabilities found".
8. **#598's pins are partly stale.** zizmor pinned 1.30.1, upstream **1.32.0**;
   actionlint digest pinned 1.7.7, upstream **1.7.12**; pip-audit 2.10.1 and
   codecov-cli v11.3.2 are current. Both bumps are green on this tree
   (actionlint 1.7.12 reports nothing; zizmor 1.32.0 reports nothing, default
   persona, offline).
9. **#610's premise is still live but its check passes.** The PGDG step uses
   `$(lsb_release -cs)-pgdg`; `resolute-pgdg` exists (HTTP 200 on 2026-11-05),
   `noble-pgdg` exists, `plucky-pgdg` and `questing-pgdg` do not. The failure in
   run 42088177589 was a transient TLS EOF on `ubuntu-26.04` (codename
   `resolute`), not a missing repo.
10. **Cost of a product file.** `scripts/affected.py` resolves `HARNESS` before
    `INERT`, so a workflow-only branch owes `settings`; a change under
    `app/kernel/` owes **every** suite. A tested `scripts/` helper makes this
    branch a full-matrix branch.
11. **Pyright does not include `scripts/`.** `pyproject.toml` sets
    `include = ["app"]`; `uv run pyright scripts/affected.py` (explicit path)
    analyses it cleanly, so the new script is checked that way, not by changing
    the config.
12. **The dependency review's own comment is right.** The action's v5 source
    calls `setFailed` on both `forbidden` and `unresolved`; a non-SPDX license
    reddens as unresolved. A license proof would be ambiguous; a vulnerable
    dependency is not.

## Goals

- #596, #600, #602: correct the record, close each with the condition that
  re-opens it.
- #597: the nightly audits dev dependencies too, with no second job.
- #598: every pin Dependabot cannot follow is visible in a monthly advisory
  check that opens one issue.
- #599, #603, #606, #610: the mechanical fixes the issues name.
- #604: the four proofs run and are recorded on the issue; this branch proves
  the SHARED path, a separate one-line PR proves the HARNESS path.
- #605: one copy of the `ci-required` verdicts.
- The index #607 closes with its last child.

## Non-goals

- No repository-settings change GitHub refuses; no attempt to buy or emulate
  Secret Protection.
- No ruleset edit, no change to the required-check set, no new required check.
- No new third-party action; the new workflow reuses the pinned
  `actions/checkout` and the runner's `gh`, `jq`, `python3`.
- No `pyproject.toml` change (the pyright include stays `["app"]`).
- No fix for the PGDG codename mapping beyond #610's retry; the codename check
  is a recorded probe, not a new mechanism.
- No work on `plucky`/`questing` pgdg absence: no runner image here uses them.

## Anti-goals

- A check that only reminds but is itself unchecked (a regex that silently
  finds nothing) — the pin parser gets a hermetic test that reads the live tree.
- A widened audit that turns the nightly red on the day it lands — verified
  green before the commit.
- Closing #596/#600/#602 as "worked around" without a named re-open trigger.
- A second copy of a rule, table or pin value in the tree.
- A proof that passes for the wrong reason (a license red that is really
  "unresolved"): the #604 proof uses a known-vulnerable pin, not a license.

## Approaches considered

### #597 — dev-scope audit

- **A. Widen the existing audit (chosen).** One full `uv export --locked` list
  and `pnpm audit --audit-level high` without `--prod`. Covers runtime and dev
  with fewer commands than today; the trade is that a report no longer separates
  runtime from dev by construction — the package name does that in practice.
- **B. A second `audit-dev` job.** Preserves the split, adds a job and a second
  summary. Rejected: the split buys nothing a package name does not, and the
  issue's own fix is one scope decision, not new machinery.
- **C. Record the accepted gap.** Rejected: dev CVEs exist and the nightly is
  the only surface that would see one after merge.

### #598 — a Dependabot path for the pins

- **A. One monthly check for all five pins (chosen).** `scripts/check_pins.py`
  reads each pin from the file that carries it and asks upstream; a monthly
  advisory workflow opens, comments on or closes one `ci/tool-pins` issue. The
  actionlint pin is checked on **both** its version comment and its Docker Hub
  digest, so a comment/digest divergence cannot pass as current.
- **B. Move `pip-audit` (and zizmor) into a uv dependency group.** Dependabot's
  `uv` entry would follow two of five; zizmor would leave `zizmor-action` (losing
  its annotations), and the actionlint digest and Codecov CLI would stay manual.
  Rejected: it splits the problem and leaves three pins silent.
- **C. Document all of them as manual.** Rejected: the issue exists because a
  silent stale pin is the defect.

### #605 — two copies of the `ci-required` verdicts

- **A. The doc points at the code (chosen).** The table leaves
  `docs/architecture/github.md`; a two-line pointer names the `ci-required` job
  comment in `ci.yml` as the single copy.
- **B. The code points at the doc.** Rejected: a reader of `ci.yml` would have to
  leave the file for the rule it enforces.
- **C. A test comparing prose.** Rejected: parsing English comment text against
  a Markdown table reddens on rewording and proves nothing.

### #601 — already fixed

`main`'s 673306b3 removed the key and corrected the map row; the issue is
closed. This wave only records it and starts from that commit.

### #603 — the Postgres tag

- **A. Pin the index digest everywhere (chosen).** `_test.yml`, `_e2e.yml` and
  both services in `docker-compose.dev.yml` carry
  `pgvector/pgvector@sha256:7d0a4146…` with `# pg17` as the name.
- **B. Pin CI only, leave compose on the tag.** Rejected: two answers for one
  image is the drift the map exists to prevent.
- **C. Record the tag as deliberate.** Rejected: it contradicts the
  `sha_pinning_required` posture and leaves a moved tag unobserved.

### #610 — the PGDG fetch

- **A. Retry the fetch (chosen).** `curl --retry 5 --retry-all-errors
  --retry-delay 2` on the key fetch. The failure was a transient TLS EOF; the
  retry is the smallest fix that survives it.
- **B. Source the key from the apt repo.** Rejected for now: it changes the
  trust root of the client install to fix a transport failure.
- **C. Record as flake.** Rejected: the run reddened the required `tests` job.

### The record-only findings

- **#596.** One PATCH attempt in the implementation, its response recorded. If
  it still refuses, the map's false sentence is replaced with the org-scoped
  reason, and the issue closes with the trigger "the repository moves under an
  organisation with Secret Protection, or GitHub makes the features
  repository-scoped".
- **#600.** The blind spot is already in the map; close with the trigger "GitHub
  adds a ruleset event, or `main` moves back to classic protection".
- **#602.** The trigger sits at all 14 sites; close with "actionlint releases
  `$/` support (rhysd/actionlint#732), or `sha_pinning_required` rejects `./`".
- Closing with a trigger is a close comment, not a commit: none of the three has
  a code change to land. The map corrections they need land in one `docs(ci)`
  commit.

### #604 — the proofs

- Scorecard: already proved (fact 4). Recorded.
- HARNESS: this branch is a full-matrix branch (fact 10), so the proof is a
  separate one-line workflow PR (a comment change in `_test.yml`) whose
  `changes` job must resolve `["settings"]`.
- Manual nightly dispatch: on `main` after the merge; ~15 minutes, opens no
  issue.
- Dependency review: a scratch branch pinning `lodash@4.17.20` at the workspace
  root — GHSA-35jh-r3h4-6jhm / CVE-2021-23337, **high**, above the
  `fail-on-severity: high` threshold. Expect `dependency-review` red and
  `ci-required` red; close the PR and delete the branch. A license pin was
  rejected: the action fails "unresolved" and "forbidden" with different words,
  and `AGPL-3.0-or-later` need not satisfy a deny entry of `AGPL-3.0`.
- Record: a comment on #604 with the four run URLs and what each showed.

## Decisions that are mine (and why)

- The two green tool bumps (actionlint 1.7.12, zizmor 1.32.0) land **before**
  the new check, so the check's first dispatch is green and its red proof uses a
  deliberately temporary stale pin.
- The pin check runs monthly, on the 1st at 08:23 UTC, off the nightly's and
  scorecard's slots, and is advisory (no required-check context).
- A lookup failure reddens the monthly run; a pin that cannot be parsed reddens
  it too. The check must not be able to say "current" when it could not ask.
- The widened audit keeps one report; no runtime/dev split.
- `check_pins.py` lives in `scripts/` and its test in `app/kernel/tests/`,
  matching `affected.py`; pyright checks it by explicit path. The consequence —
  every suite on this branch — is accepted and used as the SHARED proof.
- The bump updates all 16 `1.7.7` mentions, not only the two digits of the pin:
  a stale comment is a defect.

## Risks

- `pnpm audit` against dev dependencies can go red later on an advisory with no
  fix; the nightly then opens its `ci/nightly` issue, which is the designed
  channel.
- Pinning a digest freezes a base image; a security fix needs a manual digest
  bump. The monthly check names a moved tag the same day it moves.
- The `ci/tool-pins` workflow adds a write-token job (`issues: write`). It reads
  nothing private and opens issues only.
- The PATCH for #596 may land (GitHub changes plans); the implementation records
  the live answer either way.
- The branch starts from `narrare/main` 673306b3; if `main` moves again during
  the wave, Task 0's rebase is repeated before the push.

## What is left to the builder

- Exact YAML and script bodies, the `# pg17` comments, and the close wording.
- The `ci/tool-pins` label colour and description.
- Whether Compose digest pinning needs a `docker compose pull` note in
  `CONTRIBUTING.md` — settle it from the file.
- The wave report's exact numbers (wall clock of `frontend`/`build`, the
  full-matrix run URL, the dependency-review run URL).
