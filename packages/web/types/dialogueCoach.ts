// Dialogue Coach types — mirror apps/api/narrare/ai_assist/schemas.py (RULE-17).
// snake_case matches the Pydantic SSOT.
// Pydantic fields-with-defaults (mode, severity, explanation, adaptive_summary)
// are still required on the wire, so they stay required here; only the SSE
// stream-event type uses optional `?` fields (matching the established analysis
// SSE precedent: coreference-stream.ts, character-voice-stream.ts).

/**
 * Mirrors `DialogueCoachMode = Literal["analyze", "improve"]`.
 */
export type DialogueCoachMode = "analyze" | "improve";

/**
 * One proposed rewrite.
 *
 * RULE-17 contract parity: mirrors `DialogueAlternativeResponse` (frozen).
 */
export interface DialogueAlternative {
  rewrite: string;
  explanation: string;
}

/**
 * One diagnosed issue.
 *
 * RULE-17 contract parity: mirrors `DialogueIssueResponse` (frozen).
 *
 * `severity` is `string` (the backend field is plain `str`, not a Literal —
 * expected values are `"low" | "medium" | "high"`; narrowed in the UI for
 * badges only). `alternatives` is `null` in analyze mode, populated in improve
 * mode (mirrors `list[DialogueAlternativeResponse] | None`).
 */
export interface DialogueIssue {
  issue_type: string;
  speaker: string;
  original_quote: string;
  diagnosis: string;
  severity: string;
  alternatives: DialogueAlternative[] | null;
}

/**
 * Non-streaming response (the `"result"` event payload).
 *
 * RULE-17 contract parity: mirrors `DialogueCoachResponse` (frozen).
 */
export interface DialogueCoachResponse {
  chapter_id: string;
  mode: DialogueCoachMode;
  issues: DialogueIssue[];
  adaptive_summary: string;
}

/**
 * POST body for `/ai-assist/dialogue-coach/{chapter_id}`.
 *
 * RULE-17 contract parity: mirrors `DialogueCoachRequest` (`extra="forbid"`).
 */
export interface DialogueCoachRequest {
  selection_text: string;
  mode: DialogueCoachMode;
}

/**
 * One event in the dialogue-coach SSE stream.
 *
 * RULE-17 contract parity: mirrors `DialogueCoachStreamEvent`. Follows the
 * established analysis SSE pattern (`CoreferenceStreamEvent`,
 * `CharacterVoiceStreamEvent`): the backend Pydantic `event` field is `str`
 * but its description enumerates exactly these four values, so it is typed as
 * a literal union here (consistent with the two sibling stream-event types).
 * `event` discriminates between:
 *  - `"progress"` — status update (carried in `progress`).
 *  - `"result"`   — carries the full `DialogueCoachResponse` in `result`.
 *  - `"done"`     — terminal success (`is_final === true`).
 *  - `"error"`    — terminal error (`is_final === true`; `error` carries the message).
 *
 * All fields are optional (mirrors the sibling stream-event types): a given
 * event carries only the fields relevant to its `event` type.
 */
export interface DialogueCoachStreamEvent {
  event?: "progress" | "result" | "done" | "error";
  result?: DialogueCoachResponse | null;
  progress?: string | null;
  error?: string | null;
  is_final?: boolean;
}
