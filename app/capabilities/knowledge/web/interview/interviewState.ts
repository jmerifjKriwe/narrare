/**
 * The interview's pure state (W9 Task 10): which face the panel draws, whether
 * the proposal is ready to leave the panel, and the newest suggestion the
 * writer has not settled. The states reference draws eleven faces; the six
 * here are the ones the session and its turn decide — the chooser, the
 * question, the assistant thinking, a pending suggestion, a named failure and
 * the ended interview. «Answered» and «everything suggested» are the question
 * face with a filled, marked proposal; the list and the door are the panel's
 * own view and the graph's button, not a session state.
 */
import type { AssistantSession, AssistantTurnRead, Proposal } from "@shell/lib/api/client";
import type { MessageKey } from "@shell/lib/i18n";

export type InterviewFace = "chooser" | "question" | "thinking" | "suggestion" | "failed" | "ended";

/** The failures a turn can name. The first three are the server's turn
 *  refusals; a refused prompt renders no answer either, so it wears the same
 *  failed face with its own door. */
export const TURN_FAILURE_CODES = [
  "extraction-failed",
  "provider-unavailable",
  "provider-error",
  "prompt-refused",
] as const;

export interface InterviewFailure {
  code: string;
  detail?: string;
  /** The wire's own code when it is not one the panel names, kept beside the
   *  generic copy so an unknown refusal stays inspectable. */
  cause?: string;
  /** True when the failed turn was a chip's: its label was the body, never
   *  the composer's text, so the copy must not promise a text standing in the
   *  input field. */
  chip?: boolean;
}

export function isTurnFailure(code: string | undefined): boolean {
  return code !== undefined && (TURN_FAILURE_CODES as readonly string[]).includes(code);
}

/** The newest assistant turn whose suggestion the writer has not settled. */
export function pendingSuggestion(turns: readonly AssistantTurnRead[]): AssistantTurnRead | null {
  let newest: AssistantTurnRead | null = null;
  for (const turn of turns) {
    if (turn.suggestion === null || turn.suggestion_state !== "pending") continue;
    if (newest === null || turn.seq > newest.seq) newest = turn;
  }
  return newest;
}

/** The interface's own readiness fact: the type is the session's, a name is
 *  the proposal's — and only a present, non-blank name makes it ready. */
export function readyToSave(proposal: Proposal | null): boolean {
  return proposal !== null && typeof proposal.name === "string" && proposal.name.trim() !== "";
}

/**
 * The one face the panel draws. A closed session is read-only whatever else
 * stands; a running turn is the thinking row; a named failure keeps the
 * writer's text in the composer; a pending suggestion turns the question into
 * its three actions. With none of those, the interview is simply asking.
 */
export function interviewFace(input: {
  session: Pick<AssistantSession, "closed_at"> | null;
  turns: readonly AssistantTurnRead[];
  pending: boolean;
  failure: InterviewFailure | null;
}): InterviewFace {
  if (input.session === null) return "chooser";
  if (input.session.closed_at !== null) return "ended";
  if (input.pending) return "thinking";
  if (input.failure !== null) return "failed";
  if (pendingSuggestion(input.turns) !== null) return "suggestion";
  return "question";
}

/** The chooser's order — the states reference's 2×4 grid, typed by the
 *  contract's eight names. */
export const ENTITY_TYPE_ORDER = [
  "character",
  "location",
  "faction",
  "object",
  "system",
  "timeline",
  "event",
  "generic",
] as const;

/** The opening question is chrome, one per type: no turn, no model call. */
export const OPENING_KEYS: Record<(typeof ENTITY_TYPE_ORDER)[number], MessageKey> = {
  character: "knowledge.interview.opening.character",
  location: "knowledge.interview.opening.location",
  faction: "knowledge.interview.opening.faction",
  object: "knowledge.interview.opening.object",
  system: "knowledge.interview.opening.system",
  timeline: "knowledge.interview.opening.timeline",
  event: "knowledge.interview.opening.event",
  generic: "knowledge.interview.opening.generic",
};

/** The opening question's catalog key, with the generic fallback the type
 *  labels already use for a type the contract may add later. */
export function openingQuestionKey(type: string | null | undefined): MessageKey {
  return type !== null && type !== undefined && Object.hasOwn(OPENING_KEYS, type)
    ? OPENING_KEYS[type as keyof typeof OPENING_KEYS]
    : OPENING_KEYS.generic;
}
