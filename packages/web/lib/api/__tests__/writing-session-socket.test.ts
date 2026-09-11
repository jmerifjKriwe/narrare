/**
 * WritingSessionSocket ticket-authentication tests (ADR-084 T5).
 *
 * Pins the transport-level handshake contract: every connection attempt
 * awaits a FRESH single-use ticket from the injected `ticketProvider` and
 * presents it as the `token` query param; the client-asserted `user_id`
 * param is gone (sanctioned backward break). A ticket-fetch failure
 * surfaces through `onError` (RULE-11 honest — there is no silent
 * unauthenticated fallback).
 *
 * Hook-level wiring (authApi.wsTicket per attempt, MSW-counted) is covered
 * in `components/studio/editor/__tests__/useSessionSocket.recovery.test.tsx`.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { WritingSessionSocket } from "../writing-session-socket";

interface MockWebSocketInstance {
  readonly url: string;
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  close: () => void;
  send: () => void;
}

/** Deterministic provider that hands out `ticket-1`, `ticket-2`, … per call. */
function sequentialTicketProvider(): {
  readonly provider: () => Promise<string>;
  /** Tokens handed out so far, in mint order. */
  readonly minted: string[];
} {
  const minted: string[] = [];
  return {
    minted,
    provider: async () => {
      const token = `ticket-${minted.length + 1}`;
      minted.push(token);
      return token;
    },
  };
}

describe("WritingSessionSocket ticket authentication (ADR-084)", () => {
  let instances: MockWebSocketInstance[];

  beforeEach(() => {
    instances = [];
    vi.stubGlobal(
      "WebSocket",
      class MockWebSocket {
        onclose: (() => void) | null = null;
        onerror: (() => void) | null = null;
        onmessage: ((event: { data: string }) => void) | null = null;
        close() {}
        send() {}
        constructor(readonly url: string) {
          instances.push(this);
        }
      },
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("connects with the awaited ticket as `token` and never sends `user_id`", async () => {
    const { provider, minted } = sequentialTicketProvider();
    const socket = new WritingSessionSocket(
      "ch-1",
      vi.fn(),
      vi.fn(),
      provider,
      "novel-1",
      "interactive_session",
    );
    socket.connect();

    // The socket only opens after the ticket promise resolves.
    await vi.waitFor(() => expect(instances).toHaveLength(1));
    expect(minted).toEqual(["ticket-1"]);

    const url = instances[0]?.url ?? "";
    expect(url).toContain("token=ticket-1");
    expect(url).not.toContain("user_id");
    expect(url).toContain("project_id=novel-1");
    expect(url).toContain("mode=interactive_session");
  });

  it("fetches a fresh ticket per connection attempt (reconnect never replays a ticket)", async () => {
    const { provider, minted } = sequentialTicketProvider();
    const socket = new WritingSessionSocket(
      "ch-1",
      vi.fn(),
      vi.fn(),
      provider,
      "novel-1",
      "interactive_session",
      { reconnectBaseDelayMs: 0 },
    );
    socket.connect();
    await vi.waitFor(() => expect(instances).toHaveLength(1));

    // Drop the connection twice — every reconnect must mint a new ticket
    // and carry it in the URL (single-use tickets are dead after one handshake).
    for (let attempt = 2; attempt <= 3; attempt++) {
      instances[instances.length - 1]?.onclose?.();
      await vi.waitFor(() => expect(instances).toHaveLength(attempt));
      expect(minted).toHaveLength(attempt);
      expect(instances[attempt - 1]?.url).toContain(`token=ticket-${attempt}`);
    }
  });

  it("surfaces a ticket-fetch failure through onError and opens no socket", async () => {
    const onError = vi.fn();
    const provider = vi.fn(async () => {
      throw new Error("HTTP 401");
    });
    const socket = new WritingSessionSocket("ch-1", vi.fn(), onError, provider, "novel-1");
    socket.connect();

    await vi.waitFor(() => expect(onError).toHaveBeenCalledTimes(1));
    expect(instances).toHaveLength(0);
    expect(provider).toHaveBeenCalledTimes(1);
  });

  it("does not open a socket when closed while the ticket is in flight", async () => {
    let releaseTicket: (token: string) => void = () => {};
    const socket = new WritingSessionSocket(
      "ch-1",
      vi.fn(),
      vi.fn(),
      () =>
        new Promise<string>((resolve) => {
          releaseTicket = resolve;
        }),
      "novel-1",
    );
    socket.connect();
    socket.close();
    releaseTicket("ticket-late");

    // Drain the microtask queue — the late ticket must not open a socket.
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(instances).toHaveLength(0);
  });
});
