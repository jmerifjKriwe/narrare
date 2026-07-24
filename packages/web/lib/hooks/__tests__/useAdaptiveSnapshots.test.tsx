import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { adaptiveKeys } from "@/lib/hooks/adaptiveKeys";
import { useAdaptiveSnapshots } from "@/lib/hooks/useAdaptiveSnapshots";
import { server } from "@/mocks/server";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

// Mirrors the backend AdaptiveSnapshotsResponse envelope (ADR-070) — items are
// newest-first here, but the hook does NOT assume ordering (component sorts).
const SNAPSHOTS = {
  project_id: "proj-1",
  items: [
    {
      invocation_id: "inv-newest",
      novel_id: "proj-1",
      intent: "dialogue_coach",
      mode: "refine",
      created_at: "2026-07-22T12:00:00Z",
      source_summary: { preference: "values brevity", voice_profiles: "warm tone" },
      weights: { preference: 0.5, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
    },
    {
      invocation_id: "inv-oldest",
      novel_id: null,
      intent: "chapter_writing",
      mode: null,
      created_at: "2026-07-20T10:00:00Z",
      source_summary: null,
      weights: null,
    },
  ],
};

afterEach(() => server.resetHandlers());

describe("useAdaptiveSnapshots", () => {
  it("fetches the snapshots envelope via the canonical snapshots key", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/snapshots*", () => HttpResponse.json(SNAPSHOTS)));
    const qc = new QueryClient();
    const { result } = renderHook(() => useAdaptiveSnapshots("proj-1"), { wrapper: wrapper(qc) });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.project_id).toBe("proj-1");
    expect(result.current.data?.items).toHaveLength(2);
    expect(qc.getQueryData(adaptiveKeys.snapshots("proj-1"))).toBeTruthy();
  });

  it("passes the limit query parameter through to the request", async () => {
    let requestedUrl = "";
    server.use(
      http.get("*/api/v1/adaptive/proj-1/snapshots*", ({ request }) => {
        requestedUrl = request.url;
        return HttpResponse.json({ project_id: "proj-1", items: [] });
      }),
    );
    const qc = new QueryClient();
    renderHook(() => useAdaptiveSnapshots("proj-1", 5), { wrapper: wrapper(qc) });
    await waitFor(() => expect(requestedUrl).toContain("limit=5"));
  });

  it("is disabled when projectId is empty", async () => {
    server.use(
      http.get("*/api/v1/adaptive//snapshots*", () =>
        HttpResponse.json({ project_id: "", items: [] }),
      ),
    );
    const qc = new QueryClient();
    const { result } = renderHook(() => useAdaptiveSnapshots(""), { wrapper: wrapper(qc) });
    expect(result.current.fetchStatus).toBe("idle");
    expect(result.current.data).toBeUndefined();
  });
});
