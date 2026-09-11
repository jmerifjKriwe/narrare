/**
 * SSE → Promise bridge for useChatStream (extracted with it from useChat,
 * RULE-04; mirrors consistency-stream-bridge for useConsistencyStream).
 *
 * Turns the callback-based chatApi.streamChat transport into the plain
 * `execute(signal) => Promise<string>` contract useAIOperation needs: token
 * accumulation, conversation-id capture, per-chunk progress pings, and
 * error rejection for the error pipeline. The hook retains React state and
 * the partial-output ref; this module owns the transport boundary and is
 * unit-testable without React.
 *
 * @module chat-stream-bridge
 */

import { chatApi } from "@/lib/api/client";

/** Arguments for {@link bridgeChatStream}. */
export interface BridgeChatStreamArgs {
  /** Chat request body: message, project/note scope, conversation id. */
  readonly body: Parameters<typeof chatApi.streamChat>[0];
  /** Abort signal from useAIOperation. */
  readonly signal: AbortSignal;
  /** Called with the conversation id from the stream's meta event. */
  readonly onConversationId: (conversationId: string) => void;
  /** Called with the ACCUMULATED content after each token (partial-output ref). */
  readonly onToken: (accumulated: string) => void;
  /** Progress ping per chunk (useAIOperation notifyData → streaming state). */
  readonly notifyData: () => void;
}

/**
 * Run one streaming chat turn and resolve with the full reply content.
 *
 * Rejects when the stream reports an error (the `throw` inside `onError`
 * propagates through `streamChat`, exactly as the pre-extraction inline
 * wiring did) so useAIOperation's error pipeline maps it.
 */
export async function bridgeChatStream(args: BridgeChatStreamArgs): Promise<string> {
  const { body, signal, onConversationId, onToken, notifyData } = args;
  let content = "";
  await chatApi.streamChat(
    body,
    {
      onMeta: (meta) => {
        onConversationId(meta.conversation_id);
        notifyData();
      },
      onToken: (text: string) => {
        content += text;
        onToken(content);
        notifyData();
      },
      onDone: () => {
        /* content accumulated */
      },
      onError: (err: Error) => {
        throw err;
      },
    },
    signal,
  );
  return content;
}
