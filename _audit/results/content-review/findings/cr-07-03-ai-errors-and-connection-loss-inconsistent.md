# CR-07-03 — AI errors and connection loss are inconsistently actionable

**Priority:** High

**Status:** partial — most named sites resolved via `mapSSEError` and `useAIOperation`; 2 residual raw-`error.message` sites remain. Verified 2026-06-20. See [Residual Sites & Remediation Plan](#residual-sites--remediation-plan-2026-06-20) below.

## Finding

Multiple AI flows still display raw technical errors or discard connection-loss semantics, despite `docs/development/ui-principles.md:880-895` and `docs/development/ui-principles.md:905-911` requiring actionable messages, partial-output preservation, and retry.

## Evidence

- `packages/web/lib/api/streaming.ts:44-49` raises raw `HTTP ${status}` / `No response body`; consumers often pass this through.
- `packages/web/lib/api/generation.ts:259`, `generation.ts:404`, `generation.ts:478` throw raw `HTTP ${status}` in rewrite/extend/generation SSE.
- `packages/web/components/studio/editor/GenerationPanel.tsx:136-143` exposes raw HTTP messages as errors and only sets `connectionLost` for non-HTTP errors.
- `packages/web/components/studio/editor/GenerationPanel.tsx:270-275` retries by starting a new request but does not visibly preserve partial output as a connection-loss banner flow in the read component tree.
- `packages/web/components/studio/editor/ContinueButton.tsx:105-108` silently resets on extend errors; no actionable error, retry, or preserved partial-output banner.
- `packages/web/components/studio/TipTapEditor.tsx:363-366` silently resets rewrite on error; no actionable error, retry, or connection-loss handling.
- `packages/web/components/studio/editor/CoAuthorPanel.tsx:325-329` and `CoAuthorPanel.tsx:400-402` display `err.message`, so raw `HTTP 500` style messages can reach users.
- `packages/web/components/studio/kb/KBInterviewView.tsx:177-190`, `KBEnhanceReview.tsx:158-172`, and `KBAssistedCreationPanel.tsx:247-255` display raw `error.message` or English fallback text.

## User impact

When AI calls fail, users see technical status codes or no feedback at all, with unclear next steps. Some flows lose partial progress or silently stop, which is especially damaging during long writing/KB operations.

## Expected standard

All AI errors should follow `[what happened] [what to do]`, map common statuses (401/413/429/timeout/network) to user-facing i18n keys, preserve partial AI output where applicable, and show retry/reconnect actions.

## Residual Sites & Remediation Plan (2026-06-20)

**Status:** partial — most named sites resolved via `mapSSEError` (`packages/web/lib/api/ai-error-mapping.ts:72`) and `useAIOperation` (`packages/web/lib/hooks/useAIOperation/use-ai-operation.ts`); 2 residual raw-`error.message` leaks remain. `just check-ai-ux` (Check 4) currently reports **2 violations**.

### Resolved sites (representative evidence)
- GenerationPanel/controller: `errorMsg=state.error?.userMessage` (`generationPanelController.ts:233`), error phase + connection-lost banner (`GenerationPanel.tsx:119-162`).
- CoAuthor: `useCoAuthorPanel.ts:124`.
- ContinueButton → `useContinueStream.ts:52` (useAIOperation).
- TipTap/GhostText → `suggest.ts:96` (mapSSEError).

### Still-open residual sites
1. `packages/web/components/studio/kb/KnowledgeGraphView.tsx:55-58` — falls back to raw `error.message ?? "Failed to load graph data"` for non-structured errors.
2. `packages/web/components/studio/settings/LearningTab.tsx:53` and `:104-106` — `analysisMutation` (an AI operation: LLM preference analysis) renders raw `error.message` with **no retry and no connection-loss handling**.

### Remediation (frontend-scoped)
- `LearningTab.tsx`: route `analysisMutation` through `useAIOperation` (like `KBEnhanceReview`), or replace both fallbacks with the mapped `userMessage` from `mapSSEError(...)` plus an i18n default; add Retry + connection-lost banner for parity with `GenerationPanel`.
- `KnowledgeGraphView.tsx:58`: replace raw fallback with `mapSSEError(controller.error)?.userMessage ?? t("kb.graphLoadFailed")`; add `kb.graphLoadFailed` key to `packages/i18n/messages/{de,en,fr}/studio.json`.
- Re-verify `just check-ai-ux` → expect `Violations: 0`; then this finding can be resolved and its file deleted.

### Note on the "0 violations" claim
`docs/_shared/CURRENT_STATE.md` (lines 155/168/215/268) claims `just check-ai-ux` reports "0 violations". That claim is stale — the checker currently reports 2 violations (the residual sites above). The CURRENT_STATE wording will be corrected as part of the CR-07-03 closure commit.
