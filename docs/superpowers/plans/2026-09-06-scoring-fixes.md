# Scoring Diagnosis Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Fix all five gaps identified by the scoring diagnosis: (1) relationship apply dead-path, (2) predicate vocabulary, (3) merge-not-clobber metadata, (4) extraction salience policy, (5) reference alias declarations.

**Diagnosis basis:** `.superpowers/sdd/2026-09-04-pydantic-ai-followups/scoring-diagnosis.md`

## Global Constraints
- Production fixes (apps/api + packages/core) + corpus fix (benchmark/corpus/reference/).
- Each fix: regression-first, full gates after each task.
- ≤3 production files per delegation (split if needed).

---

### Task 1: Relationship apply fix (dead-path repair)
**Files:** `apps/api/narrare/kb/extraction_apply_service.py` (or `_extraction_resolution.py`), the extraction prompt, `packages/core/narrare_core/agents/extraction_agent.py` or types.

Changes:
- `ApplyExtractionItem` (or the extraction type) gains `source_entity_name` and `target_entity_name` fields for relationship items — the model identifies BOTH endpoints by name.
- The extraction prompt changes the relationship `name` semantics: instead of "Relationship label", it becomes the PREDICATE (e.g. "engaged_to"), with `source_entity_name` and `target_entity_name` for endpoints.
- `_apply_relationship` resolves source and target via name (existing resolution logic), creates the edge.
- `ApplyExtractionResponse` gains a `skipped` list with reasons (no more silent drops).

### Task 2: Predicate vocabulary (canonical registry)
**Files:** `packages/core/narrare_core/kb/` (new predicates module or extend existing), extraction prompt, reference YAML alignment.

Changes:
- Create a canonical predicate set (from the reference relations.yaml predicates + common extraction patterns).
- The extraction prompt lists the allowed predicates (the model picks from the set).
- The benchmark's relation_match.py normalizes to the canonical set.
- The reference YAML predicates are validated against the canonical set.

### Task 3: Merge-not-clobber metadata
**Files:** `apps/api/narrare/kb/extraction_apply_service.py` or `_extraction_resolution.py`.

Changes:
- When applying update_entity, merge the proposed_content into existing metadata (add new keys, update existing keys) instead of wholesale replacement.
- Preserve metadata keys not present in the update.

### Task 4: Extraction salience policy (prompt)
**Files:** `_bundled/kb/en/extraction/system.md` (governed template).

Changes:
- Add salience rules: "Extract ONLY characters who ACT or SPEAK, not those merely mentioned in passing. Do NOT extract narrative framing devices (the author reading, the narrator) as entities. Do NOT extract individual properties (someone's habit, someone's diploma) — they belong in the character's metadata. Do NOT split locations into sub-locations unless they are functionally distinct settings."
- Update the "Do NOT" section with these rules.

### Task 5: Reference alias declarations
**Files:** `benchmark/corpus/reference/entities.yaml`.

Changes:
- For each person: add the informal name(s) the text uses (e.g., p_anna_meyer: aliases ["Anna"], p_thomas_meyer: aliases ["Thomas"]).
- For descriptive locations: add the informal name (e.g., pl_eppendorfer_wohnung: aliases ["Eppendorfer Baum 14"] if the KB creates "Eppendorfer Baum 14").
- Update the benchmark's entity_match.py to check aliases (it already has alias support — just populate the data).

### Task 6: Full benchmark re-run
- Run clean incremental + clean import + light + complex.
- Compare against the 2026-09-06-clean-incremental-2 baseline.
- Document results in CURRENT_STATE.
