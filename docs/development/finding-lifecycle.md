<!-- Source: docs/development/finding-lifecycle.md | Priority: high | Maintained by: Documentation + Architecture Specialist -->

# Finding & ADR Status Lifecycle — Taxonomy

> **Purpose**: Define a single, unambiguous vocabulary for the status of audit
> findings, review items, and ADRs. The recurring failure mode this prevents:
> treating "documented", "ADR proposed", or "template exists" as if they meant
> "implemented" or "enforced".
>
> **Audience**: All specialists. Applies to `_audit/results/**/findings/*.md`,
> `docs/architecture/governance/aufg-registry.md`, ADR Gate-12 checklists, and
> `docs/_shared/CURRENT_STATE.md`.
>
> **Enforcement**: A finding or ADR may not be marked `resolved`/`✅ Implemented`
> without pointing to **both** (a) the implementation that exists on disk and
> (b) the test or CI-blocking checker that proves it stays fixed.

---

## 1. The cardinal rule

**Status words are earned by evidence, not by intent.** "We wrote an ADR" is
not "we shipped the fix." "A template exists" is not "runtime uses it." "The
check is green" means only *the layer the check inspects* is green — not the
whole system.

When in doubt, downgrade the status and record what is missing.

---

## 2. Finding status taxonomy

Findings live under `_audit/results/**/findings/` and carry a `Status:` line.
Status values, in lifecycle order:

| Status | Meaning | Required evidence to claim |
|--------|---------|----------------------------|
| `identified` / `open` | Problem observed, root cause not yet confirmed | Finding text + source citation |
| `triaged` | Root cause confirmed; priority + owner assigned | Root-cause analysis (≥2× "why") |
| `designed` | Architecturally correct fix proposed (ADR draft or design) | ≥2 alternatives evaluated; sustainability check |
| `accepted` | ADR ✅ Accepted for its *decisions*; implementation may be deferred | ADR file + INDEX row + Gate-12 checklist opened |
| `implemented` | Code/config/template change exists on disk and tests pass | File paths + test names + green run |
| `enforced` | A CI-blocking checker (or equivalent regression test) prevents reintroduction | Checker module + CI wiring; baseline set |
| `verified` | Independent verification (cross-feature check, eval, or audit) confirms real runtime behaviour | Verification artefact reference |
| `✅ Resolved` | **`implemented` + `enforced` (and `verified` where applicable)** | All three columns above |

**`✅ Resolved` is the terminal state and requires both implementation and
enforcement evidence.** A finding with only an ADR is at most `accepted`. A
finding with code but no checker is `implemented` (and remains regressable).

Non-terminal closure states:

| Status | Meaning |
|--------|---------|
| `accepted_risk` | Knowingly retained with owner, rationale, controls, review date |
| `covered_by_existing_aufg` | Delegated to another tracked item; no duplicate task |
| `not_applicable` | Does not apply; rationale + reviewer recorded |
| `superseded` | Replaced by a newer finding/ADR; cross-link required |

---

## 3. ADR status (Gate-12)

ADR status mirrors the finding lifecycle but uses the Gate-12 completeness
checklist as its evidence surface:

| ADR status | Gate-12 meaning |
|------------|-----------------|
| 🔄 Proposed | Decision under discussion; **no production code may depend on its contract** |
| ✅ Accepted | Decisions are in effect; implementation may still be in a later phase. Gate-12 checklist *opened* |
| ✅ Implemented | All Retrofit-Plan steps applied + all Phase-D checkers ship + regression tests pass. Gate-12 checklist *closed* |
| ⛔ Superseded | Replaced by a newer ADR; old ADR's status line updated |
| 🗄️ Deprecated | No longer relevant |

**An ADR that is `✅ Accepted` is NOT `✅ Implemented`.** The gap is the
Retrofit Plan + Phase D checkers. Index.md and CURRENT_STATE.md must reflect
the more conservative of the two.

---

## 4. Anti-patterns (forbidden)

- **"ADR proposed → mark resolved."** A Proposed ADR's contract cannot be relied
  on by production code, so it cannot close a finding. (See ADR-049 §ADR-048
  premature reference.)
- **"Template exists → assume runtime uses it."** FIND-011's exact failure: a
  governed template sat on disk while the service sent an inline f-string. The
  `INLINE-FEATURE-PROMPT` gate exists because "file exists" ≠ "file is loaded".
- **"Check is green → done."** A green check covers only the layer it inspects.
  FIND-010 survived every checker because each validated one slice and none
  validated that all slices referred to the same file.
- **"Implemented → resolved (no enforcement)."** Without a regression gate, the
  fix rots the moment the next contributor touches the area. `implemented`
  without `enforced` is regressable debt, not closure.
- **Cross-feature correctness assumed from feature-local checks.** When a change
  crosses a feature boundary, verify the *integration contract*, not just that
  each feature passes its own tests. (See ADR-050 motivation.)

---

## 5. How to write a `✅ Resolved` block

Every "resolved" claim in a finding file or CURRENT_STATE.md must contain:

1. **Design** — which ADR + which decisions close it.
2. **Implementation** — file paths that exist on disk (verified, not assumed).
3. **Enforcement** — which CI-blocking checker or regression test prevents
   reintroduction, and the ratchet baseline it set.

A block missing any of the three is not a resolution; it is a plan. See the
FIND-010 / FIND-011 "Resolution evidence" sections for the canonical format.

---

## 6. Where this taxonomy is enforced

- `_audit/results/**/findings/*.md` — `Status:` line + "Resolution evidence"
  section.
- `docs/architecture/governance/aufg-registry.md` — `Status` field per AUFG.
- ADR Gate-12 checklists in each ADR file.
- `docs/_shared/CURRENT_STATE.md` — Decisions table status must match INDEX.md.
- `scripts/check_architecture.py` — ADR-STATUS consistency (INDEX ↔ ADR file).

---

**Reference**: `docs/architecture/decisions/INDEX.md` (ADR status legend),
`docs/architecture/governance/aufg-registry.md` (AUFG lifecycle states),
`.opencode/context/narrare-dev/standards/architectural-discipline.md`
**Related**: ADR-049 (prompt-surface identity, where the "template exists ≠
runtime uses it" lesson was relearned), ADR-050 (cross-feature contracts)
