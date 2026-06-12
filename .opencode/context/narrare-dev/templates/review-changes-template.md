<!-- Context: narrare-dev/templates/review-changes-template | Priority: medium | Source: RULE-21 in CONSTRAINTS.md | Updated: 2026-06-12 -->

# Material Changes from Previous Review (RULE-21)

> This template is used by the Architecture Specialist when a material change
> to a previously-reviewed plan is detected. Fill in every section before
> resubmitting for re-review.

---

## Original Plan Reference

- **Plan ID / Feature:** _e.g., WRITE-005, INFRA-012_
- **Previous Review Date:** _YYYY-MM-DD_
- **Previous Review Outcome:** _PASS / PASS-WITH-CONCERNS / REJECT_
- **Reviewer:** _Architecture Specialist_

---

## Material Change Checklist

Check all categories that apply to this change:

- [ ] **New files/modules** — Files or modules added that were not in the reviewed plan
- [ ] **Module boundary changes** — Responsibility moved to a different module or package
- [ ] **New external dependencies** — Dependencies not present in the reviewed plan
- [ ] **Constructor signature changes** — DI wiring or constructor signatures modified
- [ ] **Public API changes** — Public interfaces, endpoints, or contracts modified

---

## What Changed?

_Describe every deviation from the reviewed plan. Be specific — list file paths,
module names, API endpoints, or dependency names._

<!-- Example:
- Added `packages/core/narrare_core/analysis/coreference.py` (new module for coreference resolution)
- Moved embedding batch logic from `core/llm/gateway.py` to `core/llm/embedding_batch.py`
- Added `spacy-coref` dependency to pyproject.toml
- Changed `AnalysisService.__init__` to accept `CoreferenceAgent` via DI
- Changed `POST /analysis/coreference` response schema to include `chain_count`
-->

---

## Why?

_Justify each change. Why was the original plan insufficient? What new information
or requirement necessitated the deviation?_

---

## Impact on Existing Plan

_How do these changes affect:_
1. **Scope** — Is the feature larger/smaller now?
2. **Timeline** — Any impact on implementation order or dependencies?
3. **Risk** — New risks introduced? Previously-identified risks mitigated or worsened?
4. **Architecture** — Does this affect other modules, features, or cross-cutting concerns?

---

## Declaration

> I confirm that all material deviations from the previously-reviewed plan are
> listed above. No undisclosed material changes have been made.
>
> **Coordinator / Author:** _name_
> **Date:** _YYYY-MM-DD_
