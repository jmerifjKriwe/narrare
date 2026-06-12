# CR-07-03 — AI errors and connection loss are inconsistently actionable

**Priority:** High

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
