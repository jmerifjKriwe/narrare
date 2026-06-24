/**
 * useSessionSocket recovery tests — WebSocket session recovery handshake
 * (CR-AUFG-07-21).
 *
 * Pins the transport-level recovery contract enforced by ADR-052 (Session
 * Stop and WebSocket Recovery): after a drop the socket reattaches with
 * `?session_id=` and sends `recover_session` first, and the hook surfaces
 * the recovery-state transitions (idle -> reconnecting -> recovered |
 * failed). This is a deliberately separate lifecycle from the SSE
 * operation path (ADR-043 Review-Trigger #1); WritingSessionSocket lives in
 * its own non-SSE module (`@/lib/api/writing-session-socket`, RULE-06), so
 * importing the class no longer trips the `check_1_use_ai_operation`
 * SSE-module pattern and no governance entry is required.
 */
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WritingSessionSocket } from "@/lib/api/writing-session-socket";
import { useSessionSocket } from "../useSessionSocket";

interface MockWebSocketInstance {
  readonly url: string;
  readonly sent: string[];
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  onopen: (() => void) | null;
  close: () => void;
  send: (message: string) => void;
}

type RecoveryHookResult = ReturnType<typeof useSessionSocket> & {
  readonly recoveryState?: "idle" | "reconnecting" | "recovered" | "failed";
};

function latestInstance(instances: readonly MockWebSocketInstance[]): MockWebSocketInstance {
  const instance = instances[instances.length - 1];
  if (!instance) {
    throw new Error("Expected a WebSocket instance");
  }
  return instance;
}

function hookOptions() {
  return {
    chapterId: "chapter-1",
    novelId: "novel-1",
    mode: "interactive_session" as const,
    userId: "user-1",
    sessionEndedLabel: "Session ended",
    errorConnectingLabel: "Connection failed",
    savedLabel: "Saved",
    recoveryFailedLabel: "Recovery failed",
  };
}

describe("WritingSessionSocket recovery handshake", () => {
  let instances: MockWebSocketInstance[];

  beforeEach(() => {
    instances = [];
    vi.stubGlobal(
      "WebSocket",
      class MockWebSocket implements MockWebSocketInstance {
        readonly sent: string[] = [];
        onclose: (() => void) | null = null;
        onerror: (() => void) | null = null;
        onmessage: ((event: { data: string }) => void) | null = null;
        onopen: (() => void) | null = null;

        constructor(readonly url: string) {
          instances.push(this);
        }

        close(): void {}

        send(message: string): void {
          this.sent.push(message);
        }
      },
    );
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("uses the greeted session id in the reconnect URL and sends recover_session first", () => {
    const socket = new WritingSessionSocket(
      "chapter-1",
      vi.fn(),
      vi.fn(),
      "user-1",
      "novel-1",
      "interactive_session",
    );
    socket.connect();

    latestInstance(instances).onmessage?.({
      data: JSON.stringify({ type: "greeting", session_id: "session-1", message: "Ready" }),
    });
    latestInstance(instances).onclose?.();
    vi.runOnlyPendingTimers();

    const reconnected = latestInstance(instances);
    expect(reconnected.url).toContain("session_id=session-1");

    reconnected.onopen?.();

    expect(reconnected.sent[0]).toBe(
      JSON.stringify({ type: "recover_session", session_id: "session-1" }),
    );
  });
});

describe("useSessionSocket recovery state", () => {
  let instances: MockWebSocketInstance[];

  beforeEach(() => {
    instances = [];
    vi.stubGlobal(
      "WebSocket",
      class MockWebSocket implements MockWebSocketInstance {
        readonly sent: string[] = [];
        onclose: (() => void) | null = null;
        onerror: (() => void) | null = null;
        onmessage: ((event: { data: string }) => void) | null = null;
        onopen: (() => void) | null = null;

        constructor(readonly url: string) {
          instances.push(this);
        }

        close(): void {}

        send(message: string): void {
          this.sent.push(message);
        }
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("moves from reconnecting to recovered and failed from socket messages", async () => {
    const { result } = renderHook(() => useSessionSocket(hookOptions()));

    act(() => {
      latestInstance(instances).onmessage?.({
        data: JSON.stringify({ type: "greeting", session_id: "session-1", message: "Ready" }),
      });
      latestInstance(instances).onerror?.();
    });

    await waitFor(() => {
      expect((result.current as RecoveryHookResult).recoveryState).toBe("reconnecting");
    });

    act(() => {
      latestInstance(instances).onmessage?.({
        data: JSON.stringify({
          type: "session_recovered",
          session_id: "session-1",
          stream_status: "stopped",
          partial_prose: "Recovered prose",
          sequence: 2,
          transcript_tail: [],
        }),
      });
    });

    await waitFor(() => {
      expect((result.current as RecoveryHookResult).recoveryState).toBe("recovered");
    });

    act(() => {
      latestInstance(instances).onmessage?.({
        data: JSON.stringify({ type: "recovery_failed", reason: "session_expired" }),
      });
    });

    await waitFor(() => {
      expect((result.current as RecoveryHookResult).recoveryState).toBe("failed");
    });
  });
});
