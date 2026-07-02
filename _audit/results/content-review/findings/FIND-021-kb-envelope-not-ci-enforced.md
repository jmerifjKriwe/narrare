# FIND-021 — KB Context Envelope Not CI-Enforced for All Renderers

> **Status:** `identified` (open)
> **Priority:** P3
> **Source:** CR-04 Cross-Feature Coherence (2026-06-30 re-review)
> **Related:** CR-AUFG-04-11, ADR-050 P1-A
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

The KB Context Envelope contract (ADR-050 P1-A) exists: every renderer must
preserve provenance or explicitly via `RenderedKBContext.omitted_fields` +
`OmissionReason`. The main renderers comply, but there is no CI checker
enforcing this. A new renderer could silently drop provenance without CI
catching it.

## Code References

- **Envelope contract:** `packages/core/narrare_core/context/_kb_envelope.py:1-24`, `78-118`, `148-180`.
- **RenderedKBContext.omitted_fields:** `packages/core/narrare_core/prompts/context.py:183-233`.
- **Compliant renderers:** `context.py` (compact formatter), `_helpers.py:74-100` (format_entities), `context_wiki.py:32-101` (format_entities_with_wiki).
- **No CI checker:** grep `_checkers/` for `envelope`/`omitted_fields` returns empty — no checker module enforces envelope usage.

## Impact

- Current renderers are compliant, so this is a narrow governance gap, not a current runtime defect.
- Without a checker, a future renderer could silently omit provenance, violating RULE-11 (no silent failures) and the ADR-050 envelope contract.
- The gap is preventive: it prevents future drift rather than fixing current breakage.

## Prioritized Remediation

1. **Write a checker** that scans KB-Context renderer functions for `RenderedKBContext` usage / `omitted_fields` declaration.
2. **Set a test baseline** (current renderers pass).
3. **Wire into `just check-architecture`** so new renderers are caught.

## Alternatives Considered

- **Accept current manual review.** Rejected: without CI enforcement, the envelope contract is regressable debt the moment a new renderer is added.
- **Add runtime assertion.** Rejected: a static checker is more appropriate than a runtime assertion for template/renderer governance.
