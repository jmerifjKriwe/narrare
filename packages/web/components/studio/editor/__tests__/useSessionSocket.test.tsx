/**
 * useSessionSocket tests — SSE connect / retry defaults (CR-08 C-3).
 *
 * REAL CONTROL: These tests IMPORT the governed defaults from their source
 * modules and assert that (1) the source value matches the Governed Defaults
 * Manifest §4.3, and (2) the consumer (WritingSessionSocket — the class that
 * useSessionSocket instantiates with no socket options) actually uses them.
 *
 * Unlike the previous version of this file, the constants are NOT redefined
 * locally. Changing any source constant value now breaks the value-layer
 * tests, and removing the constants from the consumer breaks the usage-layer
 * test — so the suite enforces the real behavior, not a self-comparison.
 *
 * Governed Defaults Manifest §4.3 — review triggers per value are inlined
 * below. If a default changes, the manifest rationale + review trigger must
 * be updated first.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  DEFAULT_MAX_RECONNECT_ATTEMPTS,
  DEFAULT_RECONNECT_BASE_DELAY_MS,
  WritingSessionSocket,
} from "@/lib/api/generation";
import { DEFAULT_CONNECT_TIMEOUT_MS } from "@/lib/api/streaming";
import { DEFAULT_CONNECTION_LOSS_TIMEOUT } from "@/lib/hooks/ai-operation-execute";

// ---------------------------------------------------------------------------
// (1) Value layer — source constant === manifest value
//
// Each assertion compares the IMPORTED source constant to the manifest value.
// If a source constant drifts from the manifest, the corresponding test fails.
// ---------------------------------------------------------------------------

describe("SSE connect / retry governed defaults (source value enforcement)", () => {
  it("DEFAULT_CONNECT_TIMEOUT_MS matches manifest (30s)", () => {
    /**
     * Rationale: 30s connect timeout is generous for local-first /
     * single-user deployments where AI providers may have cold-start latency.
     *
     * Review trigger: latency_target — re-evaluate if UX latency SLAs are
     * revised (e.g. managed hosting with tighter guarantees).
     *
     * Override: callers can pass connectTimeoutMs to connectSSE().
     *
     * Source: packages/web/lib/api/streaming.ts
     */
    expect(DEFAULT_CONNECT_TIMEOUT_MS).toBe(30_000);
  });

  it("DEFAULT_CONNECTION_LOSS_TIMEOUT matches manifest (15s)", () => {
    /**
     * Rationale: 15s connection-loss timeout allows transient network issues
     * to resolve without showing the user a disconnected state.
     *
     * Review trigger: latency_target + incident_feedback.
     *
     * Override: caller option via useAIOperation hook options
     * (connectionLossTimeout).
     *
     * Source: packages/web/lib/hooks/ai-operation-execute.ts
     */
    expect(DEFAULT_CONNECTION_LOSS_TIMEOUT).toBe(15_000);
  });

  it("DEFAULT_MAX_RECONNECT_ATTEMPTS matches manifest (5)", () => {
    /**
     * Rationale: 5 reconnect attempts with linear backoff handles transient
     * WS failures while preventing infinite reconnect loops.
     *
     * Review trigger: incident_feedback — re-evaluate if users report
     * excessive disconnection or failed reconnections.
     *
     * Override: WritingSessionSocketOptions.maxReconnectAttempts.
     *
     * Source: packages/web/lib/api/generation.ts
     */
    expect(DEFAULT_MAX_RECONNECT_ATTEMPTS).toBe(5);
  });

  it("DEFAULT_RECONNECT_BASE_DELAY_MS matches manifest (1000ms)", () => {
    /**
     * Rationale: 1s base delay with linear backoff (delay = base × attempt)
     * gives: 1s, 2s, 3s, 4s, 5s — reasonable cascade without overwhelming
     * the server.
     *
     * Review trigger: incident_feedback — re-evaluate if users report
     * reconnection taking too long or too fast.
     *
     * Override: WritingSessionSocketOptions.reconnectBaseDelayMs.
     *
     * Source: packages/web/lib/api/generation.ts
     */
    expect(DEFAULT_RECONNECT_BASE_DELAY_MS).toBe(1_000);
  });
});

// ---------------------------------------------------------------------------
// (2) Usage layer — the consumer actually uses the defaults
//
// useSessionSocket constructs `new WritingSessionSocket(...)` with NO
// socketOptions, so its effective reconnect behavior is governed entirely by
// DEFAULT_MAX_RECONNECT_ATTEMPTS / DEFAULT_RECONNECT_BASE_DELAY_MS. These
// behavioral tests prove the wiring: if WritingSessionSocket ever stops
// consuming the module defaults, they fail.
// ---------------------------------------------------------------------------

type MockWebSocketInstance = {
  onclose: (() => void) | null;
  onerror: (() => void) | null;
  onmessage: ((event: { data: string }) => void) | null;
  close: () => void;
  send: () => void;
};

describe("WritingSessionSocket uses reconnect defaults (behavioral)", () => {
  let instances: MockWebSocketInstance[];

  beforeEach(() => {
    instances = [];
    // Replace the global WebSocket with a no-op mock that records every
    // instance created. happy-dom ships a WebSocket, so stubGlobal is used to
    // save/restore the original cleanly.
    vi.stubGlobal(
      "WebSocket",
      class MockWebSocket {
        onclose: (() => void) | null = null;
        onerror: (() => void) | null = null;
        onmessage: ((event: { data: string }) => void) | null = null;
        close() {}
        send() {}
        constructor() {
          instances.push(this);
        }
      },
    );
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it("reconnects exactly DEFAULT_MAX_RECONNECT_ATTEMPTS times (default options, as used by useSessionSocket)", () => {
    // Constructed without socketOptions — exactly how useSessionSocket does it
    // (see useSessionSocket.ts: `new WritingSessionSocket(chapterId, ...)`).
    const socket = new WritingSessionSocket("ch-1", vi.fn(), vi.fn());
    socket.connect();
    expect(instances).toHaveLength(1); // initial connect

    // Drain reconnects: close the current socket, run the scheduled reconnect
    // timer (which creates a new WS), and repeat until closing no longer
    // schedules a reconnect (the ceiling has been reached).
    for (let guard = 0; guard < 50; guard++) {
      const current = instances[instances.length - 1];
      if (!current) break;
      const before = instances.length;
      current.onclose?.();
      vi.runOnlyPendingTimers();
      // No new instance created ⇒ reconnect ceiling reached, stop draining.
      if (instances.length === before) break;
    }

    // initial connect (1) + exactly DEFAULT_MAX_RECONNECT_ATTEMPTS reconnects.
    expect(instances).toHaveLength(1 + DEFAULT_MAX_RECONNECT_ATTEMPTS);
  });

  it("schedules each reconnect at DEFAULT_RECONNECT_BASE_DELAY_MS × attempt (linear backoff)", () => {
    const setTimeoutSpy = vi.spyOn(globalThis, "setTimeout");

    const socket = new WritingSessionSocket("ch-1", vi.fn(), vi.fn());
    socket.connect();

    // First close schedules reconnect #1 at baseDelay × 1.
    const first = instances[instances.length - 1];
    first?.onclose?.();
    vi.runOnlyPendingTimers(); // fires reconnect #1 → creates second WS

    expect(setTimeoutSpy).toHaveBeenLastCalledWith(
      expect.any(Function),
      DEFAULT_RECONNECT_BASE_DELAY_MS * 1,
    );

    // Second close schedules reconnect #2 at baseDelay × 2.
    const second = instances[instances.length - 1];
    second?.onclose?.();
    vi.runOnlyPendingTimers();

    expect(setTimeoutSpy).toHaveBeenLastCalledWith(
      expect.any(Function),
      DEFAULT_RECONNECT_BASE_DELAY_MS * 2,
    );

    setTimeoutSpy.mockRestore();
  });
});
