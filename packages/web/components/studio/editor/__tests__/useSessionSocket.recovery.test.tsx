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
import { HttpResponse, http } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WritingSessionSocket } from "@/lib/api/writing-session-socket";
import { server } from "@/mocks/server";
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

/**
 * Yield enough microtask ticks for the awaited ticket provider to settle
 * before the socket opens (fake-timer safe — microtasks are never faked).
 */
async function flushTicketFetch(): Promise<void> {
  for (let i = 0; i < 8; i++) {
    await Promise.resolve();
  }
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

  it("uses the greeted session id in the reconnect URL and sends recover_session first", async () => {
    const socket = new WritingSessionSocket(
      "chapter-1",
      vi.fn(),
      vi.fn(),
      async () => "ticket-1",
      "novel-1",
      "interactive_session",
    );
    socket.connect();

    // connect() awaits the ticket provider before opening the socket.
    await flushTicketFetch();
    expect(instances).toHaveLength(1);

    latestInstance(instances).onmessage?.({
      data: JSON.stringify({ type: "greeting", session_id: "session-1", message: "Ready" }),
    });
    latestInstance(instances).onclose?.();
    vi.runOnlyPendingTimers();

    await flushTicketFetch();
    const reconnected = latestInstance(instances);
    expect(reconnected.url).toContain("session_id=session-1");
    // ADR-084: every attempt carries a (fresh) ticket, never user_id.
    expect(reconnected.url).toContain("token=ticket-1");
    expect(reconnected.url).not.toContain("user_id");

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

    // The hook fetches a WS ticket (MSW) before opening the socket.
    await waitFor(() => expect(instances).toHaveLength(1));

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

describe("useSessionSocket ticket wiring (ADR-084)", () => {
  let instances: MockWebSocketInstance[];
  let ticketRequests: number;

  beforeEach(() => {
    instances = [];
    ticketRequests = 0;
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
    // Counting mint handler — every POST must yield a DISTINCT token so the
    // tests can prove a reconnect never replays a consumed ticket.
    server.use(
      http.post("*/api/v1/auth/ws-ticket", () => {
        ticketRequests += 1;
        return HttpResponse.json({ token: `ws-ticket-${ticketRequests}`, expires_in: 60 });
      }),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("mints a fresh ticket via authApi per connection attempt (MSW-counted)", async () => {
    renderHook(() => useSessionSocket(hookOptions()));

    await waitFor(() => expect(instances).toHaveLength(1));
    expect(instances[0]?.url).toContain("token=ws-ticket-1");
    expect(instances[0]?.url).not.toContain("user_id");

    // Greet (binds the session), then drop the connection — the reconnect
    // must fetch a NEW ticket (single-use) and carry it in the URL.
    act(() => {
      const first = latestInstance(instances);
      first.onmessage?.({
        data: JSON.stringify({ type: "greeting", session_id: "session-1", message: "Ready" }),
      });
      first.onclose?.();
    });

    await waitFor(() => expect(instances).toHaveLength(2), { timeout: 5_000 });
    expect(instances[1]?.url).toContain("token=ws-ticket-2");
    expect(instances[1]?.url).not.toContain("user_id");
    expect(ticketRequests).toBe(2);
  });
});
