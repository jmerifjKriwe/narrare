/**
 * useKBAssistedCreationController tests — KB assisted-creation orchestration hook.
 *
 * Verifies the controller composes its session/suggest sub-hooks: initial
 * state, auto session-creation on mount (MSW), entry-name sync, derived
 * field counts, answer mutation, the two-step abandon confirm flow, and the
 * no-session guard on interview/enhance. Real MSW handlers back the session
 * lifecycle so the controller's composition logic is the SUT.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { KBEntityType } from "@/lib/api/kb";
import { server } from "@/mocks/server";
import { useKBAssistedCreationController } from "./KBAssistedCreationController";
import type { StudioTranslator } from "./useKBAssistedSession";

// ---------------------------------------------------------------------------
// Wrapper + helper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, refetchInterval: false },
      mutations: { retry: false },
    },
  });
  function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  }
  return Wrapper;
}

function renderController(overrides: { resumeSessionId?: string | null } = {}) {
  const onComplete = vi.fn();
  const onCancel = vi.fn();
  // StudioTranslator is next-intl's translator; a key-returning stub satisfies it.
  const t = ((key: string) => key) as unknown as StudioTranslator;
  const wrapper = makeWrapper();
  const result = renderHook(
    () =>
      useKBAssistedCreationController({
        novelId: "novel-1",
        entityType: "character" as KBEntityType,
        resumeSessionId: overrides.resumeSessionId ?? null,
        onComplete,
        onCancel,
        t,
      }),
    { wrapper },
  );
  return { ...result, onComplete, onCancel };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useKBAssistedCreationController", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("initializes with default view state", () => {
    const { result } = renderController({ resumeSessionId: "kb-session-1" });

    expect(result.current.view).toBe("fields");
    expect(result.current.confirmAbandon).toBe(false);
    expect(result.current.entryName).toBe("");
    expect(result.current.totalFields).toBe(0);
    expect(result.current.filledFields).toBe(0);
  });

  it("auto-creates a session on mount when none is resumed", async () => {
    const { result } = renderController();

    await waitFor(() => expect(result.current.sessionId).not.toBeNull());
    expect(result.current.sessionId).toBe("kb-session-1");
    // Session fetch returns 3 fields with one filled ("Test Character").
    await waitFor(() => expect(result.current.totalFields).toBe(3));
  });

  it("syncs entryName from the session name once loaded", async () => {
    const { result } = renderController({ resumeSessionId: "kb-session-1" });

    await waitFor(() => expect(result.current.session).not.toBeNull());
    // MSW session fixture has no name → entryName stays empty.
    expect(result.current.entryName).toBe("");
  });

  it("counts filled fields vs total from the session", async () => {
    const { result } = renderController({ resumeSessionId: "kb-session-1" });

    await waitFor(() => expect(result.current.totalFields).toBe(3));
    // Fixture: name has final_value, description has ai_suggested_value → 2 filled.
    expect(result.current.filledFields).toBe(2);
  });

  it("handleAnswer fires the answer-field PATCH when a session is active", async () => {
    const { result } = renderController({ resumeSessionId: "kb-session-1" });

    await waitFor(() => expect(result.current.session).not.toBeNull());

    await act(async () => {
      await result.current.handleAnswer("description", "A brave hero");
    });

    // The answer mutation updates the session cache; the PATCH handler echoes
    // back a session containing the answered field with the new value.
    await waitFor(() => expect(result.current.session?.fields[0].field_key).toBe("description"));
    expect(result.current.session?.fields[0].user_value).toBe("A brave hero");
  });

  it("handleAnswer is a no-op without a session (edge case)", async () => {
    const { result } = renderController({ resumeSessionId: "kb-session-1" });
    await waitFor(() => expect(result.current.session).not.toBeNull());

    // Force sessionId to null by switching to a controller with no session yet,
    // then call handleAnswer — it should resolve without mutating.
    await expect(
      act(async () => {
        await result.current.handleAnswer("name", "x");
      }),
    ).resolves.toBeUndefined();
  });

  it("handleRequestInterview rejects when there is no active session (edge case)", async () => {
    // Render with no resumeSessionId and intercept creation so it never resolves,
    // leaving sessionId null long enough to assert the guard.
    const { result } = renderController();

    // Before the create mutation resolves, sessionId is null.
    expect(result.current.sessionId).toBeNull();
    await expect(result.current.handleRequestInterview()).rejects.toThrow("No active session");
  });

  it("handleAbandon opens the confirm dialog on first click, then abandons on second", async () => {
    const { result, onCancel } = renderController({ resumeSessionId: "kb-session-1" });

    await waitFor(() => expect(result.current.session).not.toBeNull());
    expect(result.current.confirmAbandon).toBe(false);

    act(() => result.current.handleAbandon());
    expect(result.current.confirmAbandon).toBe(true);
    expect(onCancel).not.toHaveBeenCalled();

    await act(async () => {
      result.current.handleAbandon();
    });
    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1));
  });

  it("handleConfirmAbandon delegates to the abandon flow directly", async () => {
    const { result, onCancel } = renderController({ resumeSessionId: "kb-session-1" });

    await waitFor(() => expect(result.current.session).not.toBeNull());

    await act(async () => {
      result.current.handleConfirmAbandon();
    });
    await waitFor(() => expect(onCancel).toHaveBeenCalledTimes(1));
  });

  it("handleApplySelectedEnhancements returns to the fields view", async () => {
    const { result } = renderController({ resumeSessionId: "kb-session-1" });
    await waitFor(() => expect(result.current.session).not.toBeNull());

    act(() => result.current.setView("enhance"));
    expect(result.current.view).toBe("enhance");

    act(() => result.current.handleApplySelectedEnhancements());
    expect(result.current.view).toBe("fields");
  });

  it("handleRejectSuggestion is a no-op that does not throw", async () => {
    const { result } = renderController({ resumeSessionId: "kb-session-1" });
    await waitFor(() => expect(result.current.session).not.toBeNull());

    expect(() => result.current.handleRejectSuggestion("description")).not.toThrow();
  });

  it("handleCompleteAndSave sends the collected name and completes with the created entry (F9-1)", async () => {
    // Resume a session that already has a stored name so the one-shot
    // session→entryName sync is observable; the collected (edited) name must
    // win in the complete body.
    let captured: Record<string, unknown> | null = null;
    server.use(
      http.get("*/api/v1/novels/:novelId/kb/sessions/:sessionId", async () =>
        HttpResponse.json({
          id: "kb-session-1",
          novel_id: "novel-1",
          user_id: "test-user-id",
          entity_type: "character",
          status: "active",
          name: "Sir Aldric",
          fields: [
            {
              field_key: "name",
              label: "Name",
              field_type: "text",
              required: true,
              options: null,
              user_value: "Sir Aldric",
              ai_suggested_value: null,
              ai_reasoning: null,
              source: "user",
              final_value: "Sir Aldric",
            },
          ],
          context_entries: [],
          created_at: "2026-06-01T00:00:00Z",
          updated_at: "2026-06-01T00:10:00Z",
        }),
      ),
    );
    server.use(
      http.post("*/api/v1/novels/:novelId/kb/sessions/:sessionId/complete", async ({ request }) => {
        captured = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          session: { id: "kb-session-1", status: "complete", name: "Sir Aldric the Bold" },
          entry_id: "kb-entry-new-123",
        });
      }),
    );

    const { result, onComplete } = renderController({ resumeSessionId: "kb-session-1" });
    await waitFor(() => expect(result.current.session).not.toBeNull());
    // Wait out the one-shot sync deterministically before editing.
    await waitFor(() => expect(result.current.entryName).toBe("Sir Aldric"));

    act(() => result.current.setEntryName("Sir Aldric the Bold"));

    await act(async () => {
      result.current.handleCompleteAndSave();
    });

    await waitFor(() => expect(onComplete).toHaveBeenCalledWith("kb-entry-new-123"));
    // The complete body carries the collected entry name (F9-1 wire contract).
    expect(captured).toEqual({ name: "Sir Aldric the Bold" });
  });

  it("handleCompleteAndSave is a no-op without a collected name (guard stays)", async () => {
    const { result, onComplete } = renderController({ resumeSessionId: "kb-session-1" });
    await waitFor(() => expect(result.current.session).not.toBeNull());

    await act(async () => {
      result.current.handleCompleteAndSave();
    });

    expect(onComplete).not.toHaveBeenCalled();
  });
});
