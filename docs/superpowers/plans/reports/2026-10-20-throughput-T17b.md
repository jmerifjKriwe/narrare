# Throughput T17b — the two missing CI gates, and the SSOT table that forgot four

- **Date:** 2026-10-20
- **Branch:** `brave-egret`
- **Base commit:** `0052f5da` (plus the uncommitted T17a work — untouched)
- **Status:** implemented, verified, **not committed** (no git writes per task constraints)
- **Review finding:** the CI `architecture` job invoked `scripts/check_architecture.py`
  directly instead of `just check-architecture`; T9's
  `check_pre_commit_gate_tiers.py` and T11's
  `check_review_policy_consistency.py` live only in the recipe, so neither ever
  ran in CI.

## 1. Gap

`just check` / `just verify` delegate the architecture surface to
`scripts/_check_steps.py`, which runs the `check-architecture` recipe. CI cannot
run `just` there, so it enumerates the same scripts by hand — and the hand list
had silently fallen behind the recipe. Concretely:

- a hook could be moved out of the `pre-push` tier back into `pre-commit`
  (`check_pre_commit_gate_tiers.py` would exit 1 locally, CI stayed green);
- the review/report caps could be restated in a pointing document or the marker
  could disappear (`check_review_policy_consistency.py` would exit 1 locally,
  CI stayed green).

T15's `check_intent_parity.py` had the same shape of problem on the
documentation side: it *did* run, but the header table — declared in the file
itself as "the CI-gate SSOT" — did not list it.

## 2. Change (`.github/workflows/ci.yml` only)

Two steps added to `jobs.architecture`, immediately after the intent-parity
step, so they run on the same deterministic venv (`uv run --no-sync`) as their
neighbours:

```yaml
      - name: Check pre-commit gate tiers (ADR-098)
        run: uv run --no-sync python scripts/check_pre_commit_gate_tiers.py

      - name: Check review/report policy consistency (ADR-093)
        run: uv run --no-sync python scripts/check_review_policy_consistency.py
```

Four rows added to the header audit table (the declared CI-gate SSOT), using the
table's `--` gate-id convention because no G-number exists for these checks:

| Gate | Tool / Check | Why it was missing |
|------|--------------|--------------------|
| `--` | `generate_provider_catalog.py --check` (ADR-099) | ran in CI since T7, never tabled |
| `--` | `check_intent_parity.py` (ADR-025/037/038) | ran in CI since T15, never tabled |
| `--` | `check_pre_commit_gate_tiers.py` (ADR-098) | new step (T17b) |
| `--` | `check_review_policy_consistency.py` (ADR-093) | new step (T17b) |

Placement follows the table's grouping, not the job's step order (the table
already lists `check_doc_drift.py` and friends out of execution order): the
provider-catalog and intent-parity rows sit beside `check_prompt_surface_contract.py`
(the other prompt-surface checks), the two throughput rows beside
`check_adr_naming.py` (the governance-drift group).

## 3. Doc mirror — not required, nothing changed there

`docs/development/quality-gates.md` carries a byte-for-byte mirror of the table,
so I read `scripts/check_gate_drift.py` and `scripts/gate_drift_checks.py`
before touching it. The checker's actual rule set is four items
(`run_all_checks`):

1. `ssot-present` — the file `docs/development/quality-gates.md` exists; never
   exception-eligible (W1-9a);
2. `coverage-threshold` — extracts `--cov-fail-under` from `ci.yml` and compares
   it to the documented 80;
3. `streaming-compliance` — `check_streaming_compliance.py` appears as a step
   and is not `continue-on-error`;
4. `locale-sync` — same for `check_locale_sync.py`.

None parses either table. There is no row-level comparison anywhere:
`check_doc_drift.py --governance-only` covers ADR/spec/terminology/just/agent
names, not gate rows. Per the task constraint ("`quality-gates.md` only if the
drift checker requires it") and the checker's rules, **no doc change was made**.
Authoritative file for the table: the `ci.yml` header block (as its own comment
and `gate_drift_checks.py`'s module docstring both state); the doc is the prose
mirror. Consequence: the mirror now lags by these four rows, and nothing fails
when it does — recorded as a concern, not fixed here.

## 4. Gates (raw tails)

```
$ python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml')); print('YAML parses')"
YAML parses
```

```
$ uv run --all-packages python scripts/check_gate_drift.py
✅ ssot-present: Quality gates SSOT present at docs/development/quality-gates.md
✅ coverage-threshold: CI --cov-fail-under=80, documented target 80%
✅ streaming-compliance: Blocking in CI
✅ locale-sync: Blocking in CI

Summary: 0 critical, 0 warnings (all drifts have registered exceptions)
exit=0
```

```
$ uv run --all-packages python scripts/check_doc_drift.py --governance-only
⚠️  57 doc drift warnings

✅ Doc drift check passed (with warnings)
exit=0
```

```
$ uv run --all-packages python scripts/check_pre_commit_gate_tiers.py
✅ pre-commit hook tiering matches the pinned tiers (.pre-commit-config.yaml)
exit=0

$ uv run --all-packages python scripts/check_review_policy_consistency.py
✅ review/report policy marker, normative block and pointers agree
exit=0
```

```
$ pre-commit run --files .github/workflows/ci.yml
Architecture Constraints.............................................................Passed
...
check for added large files..........................................................Passed
exit=0
```

`check_gate_drift.py` itself runs in the edited job, so the two new steps are now
themselves covered by a CI check that reads this workflow file.

## 5. Concerns

- **Mirror drift, unguarded.** The four new rows exist only in `ci.yml`; the
  `quality-gates.md` table still has 36 rows. The checker's name ("gate drift")
  suggests row parity, but its rules are presence plus three specific
  value/step checks. Adding a `gate-table-parity` rule would close this class —
  out of scope here by task constraint.
- **Recipe/CI duplication remains.** The underlying failure mode (a recipe step
  that CI does not mirror) is still possible for the next check added to
  `just check-architecture`; T17b only closes the two known instances.
- `python` is not on `PATH` in this environment; `python3` was used for the YAML
  parse (same interpreter family, same result as the `uv run` calls).
