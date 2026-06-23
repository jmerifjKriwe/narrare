/**
 * Session socket message helpers.
 *
 * Keeps client-message construction separate from the React socket lifecycle.
 */

let messageCounter = 0;

export function createMessageId(): string {
  messageCounter += 1;
  return `msg-${messageCounter}`;
}

export interface SendMessageOptions {
  readonly invocation_id?: string;
  readonly session_id?: string;
}

export type SessionClientMessageType =
  | "user_direction"
  | "user_feedback"
  | "save_to_chapter"
  | "end_session"
  | "generate_draft"
  | "stop_generation"
  | "recover_session";

export function buildSessionClientMessage(
  type: SessionClientMessageType,
  content: string | undefined,
  options: SendMessageOptions | undefined,
  fallbackSessionId: string | undefined,
): Record<string, unknown> | null {
  if (type === "user_direction") {
    return { type, content };
  }

  if (type === "save_to_chapter") {
    return { type, text: content };
  }

  if (type === "stop_generation") {
    return { type, invocation_id: options?.invocation_id };
  }

  if (type === "recover_session") {
    const sessionId = options?.session_id ?? fallbackSessionId;
    if (!sessionId) return null;
    return { type, session_id: sessionId };
  }

  return { type };
}
