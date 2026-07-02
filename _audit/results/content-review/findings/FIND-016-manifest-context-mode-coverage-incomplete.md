# FIND-016 — Prompt-Surface Manifest Context-Mode Coverage Incomplete

> **Status:** `identified` (open)
> **Priority:** P2
> **Source:** CR-01 (GOV-01), carried by CR-02, CR-03, CR-04
> **Related:** CR-AUFG-01-10, CR-AUFG-02-12, CR-AUFG-03-12, CR-AUFG-04-12
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

The runtime route table declares `allowed_context_modes` for several intents,
but the prompt-surface manifest does not fully declare/enforce them. The
checker `_check_prompt_surface.py` applies variable/security checks only to
top-level manifest entries, not to context-mode sub-entries. As a result,
`check_prompt_surface_contract.py` passes despite runtime-used templates
lacking full manifest governance.

## Code References

- **ANALYSE route table:** `packages/core/narrare_core/prompts/route_table.py:181-185` — declares `allowed_context_modes` including `pov`, `readability`.
- **ANALYSE manifest:** `scripts/architecture/prompt-surface-manifest.yaml:279-287` — lists only `review`, `coreference` under `ANALYSE` context_modes.
- **BETA_READ route table:** `route_table.py:191-198` — declares `beta_reader_deepdive`.
- **BETA_READ manifest:** `prompt-surface-manifest.yaml:309-312` — has no `context_modes` section.
- **Checker scope:** `scripts/architecture/_checkers/_check_prompt_surface.py:215-294` — iterates only top-level manifest entries for variable/security checks.
- **Orphan checker:** `_check_prompt_orphan.py:103-187` — validates context-mode existence/frontmatter, not full variable/security parity.
- **Runtime consumers:** `apps/api/narrare/analysis/pov_service.py:151-164`, `readability_service.py:180-192` compose via `PromptComposer`.
- **Stale manifest comments:** `prompt-surface-manifest.yaml:87-91`, `414-422` — claim context-mode checker not landed, while `_check_prompt_orphan.py` now validates context-mode existence.

## Impact

- CI evidence is weaker for several runtime-used templates: `pov`, `readability`, `beta_reader_deepdive` pass no full variable/security manifest check.
- A future template change in these context modes could introduce unwrapped user content or deprecated variables without CI catching it.
- Manifest comments are stale, misleading reviewers about actual checker coverage.

## Prioritized Remediation

1. **Add missing manifest context-mode entries:** `ANALYSE` (`pov`, `readability`), `BETA_READ` (`beta_reader_deepdive`).
2. **Extend `_check_prompt_surface.py`** to require every runtime `allowed_context_modes` entry appears in manifest and receives the same variable/security checks as top-level routes.
3. **Update stale manifest comments** to distinguish existence/frontmatter checks (done) from full variable/security parity (pending).
4. **Add test** proving runtime `allowed_context_modes` ⊆ manifest `context_modes`.

## Alternatives Considered

- **Accept current coverage.** Rejected: the gap means CI cannot prove full prompt-surface governance for all runtime-used templates.
- **Remove context modes from route table.** Rejected: the modes are runtime-used and valuable; the manifest should catch up, not the runtime regress.
