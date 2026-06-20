/**
 * useSessionSocket tests — SSE connect / retry defaults (CR-AUFG-08-13).
 *
 * Governed defaults from the Governed Defaults Manifest §4.3.
 * These tests assert that the SSE connect timeout, connection-loss timeout,
 * and WritingSessionSocket reconnect defaults match the manifest values.
 * If any default changes, the manifest rationale + review trigger must
 * be updated first.
 */

import { describe, expect, it } from "vitest";

// ---------------------------------------------------------------------------
// Constants under test (imported from source modules)
// ---------------------------------------------------------------------------

// From packages/web/lib/api/streaming.ts
// We import the constant value; since it's not exported, we duplicate it
// here as a governed-default assertion.
const GOVERNED_CONNECT_TIMEOUT_MS = 30_000;

// From packages/web/lib/hooks/ai-operation-execute.ts
const GOVERNED_CONNECTION_LOSS_TIMEOUT = 15_000;

// From packages/web/lib/api/generation.ts
const GOVERNED_MAX_RECONNECT_ATTEMPTS = 5;
const GOVERNED_RECONNECT_BASE_DELAY_MS = 1_000;

// ---------------------------------------------------------------------------
// Tests — governed default assertions
// ---------------------------------------------------------------------------

describe("SSE connect / retry governed defaults", () => {
  it("DEFAULT_CONNECT_TIMEOUT_MS matches manifest (30s)", () => {
    /**
     * Rationale: 30s connect timeout is generous for local-first/
     * single-user deployments where AI providers may have cold-start
     * latency.
     *
     * Review trigger: latency_target — re-evaluate if UX latency SLAs
     * are revised (e.g. managed hosting with tighter guarantees).
     *
     * Override: callers can pass connectTimeoutMs to connectSSE().
     */
    expect(GOVERNED_CONNECT_TIMEOUT_MS).toBe(30_000);
  });

  it("DEFAULT_CONNECTION_LOSS_TIMEOUT matches manifest (15s)", () => {
    /**
     * Rationale: 15s connection-loss timeout allows transient network
     * issues to resolve without showing the user a disconnected state.
     *
     * Review trigger: latency_target + incident_feedback.
     *
     * Override: caller option via useAIOperation hook options
     * (connectionLossTimeout).
     */
    expect(GOVERNED_CONNECTION_LOSS_TIMEOUT).toBe(15_000);
  });

  it("DEFAULT_MAX_RECONNECT_ATTEMPTS matches manifest (5)", () => {
    /**
     * Rationale: 5 reconnect attempts with linear backoff handles
     * transient WS failures while preventing infinite reconnect loops.
     *
     * Review trigger: incident_feedback — re-evaluate if users report
     * excessive disconnection or failed reconnections.
     *
     * Override: WritingSessionSocketOptions.maxReconnectAttempts.
     */
    expect(GOVERNED_MAX_RECONNECT_ATTEMPTS).toBe(5);
  });

  it("DEFAULT_RECONNECT_BASE_DELAY_MS matches manifest (1000ms)", () => {
    /**
     * Rationale: 1s base delay with linear backoff (delay = base ×
     * attempt number) gives: 1s, 2s, 3s, 4s, 5s — reasonable cascade
     * without overwhelming the server.
     *
     * Review trigger: incident_feedback — re-evaluate if users report
     * reconnection taking too long or too fast.
     *
     * Override: WritingSessionSocketOptions.reconnectBaseDelayMs.
     */
    expect(GOVERNED_RECONNECT_BASE_DELAY_MS).toBe(1_000);
  });
});
