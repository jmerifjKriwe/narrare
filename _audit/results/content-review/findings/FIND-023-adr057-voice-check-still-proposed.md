# FIND-023 — ADR-057 Voice-Check Checking-Path Contract Still Proposed

> **Status:** `identified` (open, blocked on ADR-057 acceptance)
> **Priority:** P2
> **Source:** CR-04 Cross-Feature Coherence (2026-06-30 re-review)
> **Related:** CR-AUFG-04-09, CR-AUFG-04-14, ADR-055, ADR-057
> **Lifecycle:** `docs/development/finding-lifecycle.md`

---

## Problem

ADR-055 ✅ unified character voice storage and made `VOICE` routeable.
However, ADR-057 (voice_check checking-path contract) remains 🔄 Proposed.
Generation and checking paths do not yet share the same provider contract
until ADR-057 is accepted and implemented. `VoiceProfileConsumer.assemble_for_checking`
is not yet implemented.

## Code References

- **ADR-055 ✅:** `docs/architecture/decisions/ADR-055-character-voice-contract.md` — Character-Voice-Storage-Contract + `VOICE` routeable + `analysis/character_voice`.
- **ADR-057 🔄 Proposed:** `docs/architecture/decisions/ADR-057-voice-check-checking-path-contract.md` — INDEX row shows 🔄 status; `voice_check` context_mode + `VoiceProfileConsumer.assemble_for_checking` not yet implemented.
- **Generation path:** uses `VOICE` intent via `PromptComposer` (ADR-055).
- **Checking path:** `analysis/character_voice` exists but does not use the same `VoiceProfileConsumer` contract as generation.

## Impact

- Voice profile generation and checking use different provider contracts, meaning a voice profile extracted for generation may not be directly usable for checking.
- This is a partial-implementation gap: ADR-055 closed the storage contract, but the checking-path unification is blocked on ADR-057.
- Not a runtime defect — both paths work independently — but they are not unified.

## Prioritized Remediation

1. **Accept ADR-057** (voice_check checking-path contract).
2. **Implement `VoiceProfileConsumer.assemble_for_checking`** so generation and checking share the same provider contract.
3. **Add `voice_check` context_mode** to route table + manifest.
4. **Surface freshness/confidence** in prompt context where voice output is influenced.

## Alternatives Considered

- **Accept current split.** Rejected: ADR-055 Risk #1 explicitly calls out this gap; ADR-057 is the designed remedy.
- **Unify without ADR-057.** Rejected: the checking-path contract needs its own ADR to define scope (flag+score, no rewrites) and module home (`analysis/`).
