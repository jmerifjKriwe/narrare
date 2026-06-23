import type { MutableRefObject } from "react";
import { describe, expect, it } from "vitest";
import type { SessionResponse } from "@/lib/api/generation";
import type { Message } from "../ChatMessage";
import { createSessionMessageHandler } from "../createSessionMessageHandler";

type RecoveryState = "idle" | "reconnecting" | "recovered" | "failed";

function createHarness() {
  let messages: Message[] = [];
  let streamingText = "";
  let isStreaming = false;
  let isConnected = false;
  let saveNotification: string | null = null;
  let recoveryState: RecoveryState = "idle";
  const streamingTextRef: MutableRefObject<string> = { current: "" };

  const callbacks: Parameters<typeof createSessionMessageHandler>[0] & {
    readonly recoveryFailedLabel: string;
    readonly setRecoveryState: (state: RecoveryState) => void;
  } = {
    setMessages: (value) => {
      messages = typeof value === "function" ? value(messages) : value;
    },
    setStreamingText: (text) => {
      streamingText = text;
    },
    setIsStreaming: (streaming) => {
      isStreaming = streaming;
    },
    setIsConnected: (connected) => {
      isConnected = connected;
    },
    setSaveNotification: (notification) => {
      saveNotification = notification;
    },
    streamingTextRef,
    mode: "interactive_session",
    sessionEndedLabel: "Session ended",
    errorConnectingLabel: "Connection failed",
    savedLabel: "Saved",
    recoveryFailedLabel: "Recovery failed",
    setRecoveryState: (state) => {
      recoveryState = state;
    },
  };

  return {
    handler: createSessionMessageHandler(callbacks),
    state: () => ({
      messages,
      streamingText,
      isStreaming,
      isConnected,
      saveNotification,
      recoveryState,
    }),
    streamingTextRef,
  };
}

describe("createSessionMessageHandler stop and recovery messages", () => {
  it("moves generation_stopped partial prose into an assistant prose message", () => {
    const { handler, state, streamingTextRef } = createHarness();
    streamingTextRef.current = "optimistic local text";

    handler({
      type: "generation_stopped",
      invocation_id: "inv-1",
      partial_prose: "server partial prose",
      sequence: 7,
      reason: "user_stop",
    } as unknown as SessionResponse);

    expect(state().messages).toEqual([
      expect.objectContaining({ role: "assistant", prose: "server partial prose" }),
    ]);
    expect(state().streamingText).toBe("");
    expect(state().isStreaming).toBe(false);
    expect(streamingTextRef.current).toBe("");
  });

  it("restores transcript tail and partial prose when a session is recovered", () => {
    const { handler, state } = createHarness();

    handler({
      type: "session_recovered",
      session_id: "session-1",
      stream_status: "stopped",
      partial_prose: "Recovered partial prose",
      sequence: 8,
      transcript_tail: [{ role: "assistant", content: "Recovered assistant note" }],
    } as unknown as SessionResponse);

    expect(state().recoveryState).toBe("recovered");
    expect(state().isConnected).toBe(true);
    expect(state().messages).toEqual([
      expect.objectContaining({ role: "assistant", content: "Recovered assistant note" }),
      expect.objectContaining({ role: "assistant", prose: "Recovered partial prose" }),
    ]);
  });

  it("marks recovery failure and adds a localized system message", () => {
    const { handler, state } = createHarness();

    handler({
      type: "recovery_failed",
      reason: "session_expired",
    } as unknown as SessionResponse);

    expect(state().recoveryState).toBe("failed");
    expect(state().isConnected).toBe(false);
    expect(state().messages).toEqual([
      expect.objectContaining({ role: "system", content: "Recovery failed" }),
    ]);
  });

  it("marks connection_lost as reconnecting", () => {
    const { handler, state } = createHarness();

    handler({ type: "connection_lost", reason: "idle_timeout" } as unknown as SessionResponse);

    expect(state().recoveryState).toBe("reconnecting");
    expect(state().isConnected).toBe(false);
  });
});
