# CR-07-02 — KB AI flows miss cancel controls and canonical AI action labels

**Priority:** High

## Finding

KB assisted-creation AI flows use feature-local labels and lack visible cancel for multiple long-running AI operations, violating `docs/development/ui-principles.md:846-879` and `docs/development/ui-principles.md:897-903`.

## Evidence

- Field suggestion starts via `KBAssistedCreationPanel.tsx:120-128` and `KBSessionFieldList.tsx:129-137`; no `AbortController` is created or passed, and no stop/cancel button is shown while `suggestingFieldKey` is active.
- KB enhance is requested by `KBAssistedCreationPanel.tsx:162-171`; it never passes a signal to `requestEnhance()`, while `KBEnhanceReview.tsx:140-155` shows loading only and no stop button.
- KB suggestion accept/reject uses local keys `t("kb.reject")` / `t("kb.accept")` in `KBSessionFieldList.tsx:211-226`, not `studio.aiActions.*`.
- KB enhance accept/reject/select/apply uses local keys in `KBEnhanceReview.tsx:189-203`, `KBEnhanceReview.tsx:287-313`, and `KBEnhanceReview.tsx:335-350`, not `studio.aiActions.*`.
- Several KB UI fallbacks are hardcoded English strings, e.g. `KBAssistedCreationPanel.tsx:189-190`, `KBAssistedCreationPanel.tsx:238-240`, `KBSessionFieldList.tsx:158-159`, `KBInterviewView.tsx:181-189`, `KBEnhanceReview.tsx:162-171`.

## User impact

Users can start a KB AI operation and then have no reliable way to stop it. Labels are inconsistent with writing/generation AI flows, and non-German fallback strings leak into the reference-language UI.

## Expected standard

Every long-running KB AI operation should expose visible AbortController cancellation and use canonical `studio.aiActions.*` labels for accept/reject/retry/stop/apply-style AI output actions.
