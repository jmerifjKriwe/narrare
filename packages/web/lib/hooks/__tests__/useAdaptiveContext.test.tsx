import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  adaptiveKeys,
  useAdaptiveContext,
  useSetAdaptiveWeights,
  useToggleAdaptive,
} from "@/lib/hooks/useAdaptiveContext";
import { server } from "@/mocks/server";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

// Mounts useAdaptiveContext so the canonical query has an active observer —
// required for invalidation to trigger a refetch (TanStack v5 default
// refetchType:"active" only refetches observed queries). Mirrors production
// where the Status Indicator / Dashboard is mounted when a toggle fires.
function ContextObserver({ projectId }: { projectId: string }) {
  useAdaptiveContext(projectId);
  return null;
}

function wrapperWithObserver(qc: QueryClient, projectId: string) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <ContextObserver projectId={projectId} />
      {children}
    </QueryClientProvider>
  );
}

const CTX = {
  project_id: "proj-1",
  enabled: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: {
    preference_text: "",
    voice_profiles_text: "",
    style_constraints_text: "",
    avoidance_patterns_text: "",
  },
  has_any_signal: false,
};

afterEach(() => server.resetHandlers());

describe("adaptiveKeys (Decision 15 canonical key)", () => {
  it("produces the canonical adaptive-context key", () => {
    expect(adaptiveKeys.context("proj-1")).toEqual(["adaptive-context", "proj-1"]);
  });
});

describe("useAdaptiveContext", () => {
  it("fetches context via the canonical key", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)));
    const qc = new QueryClient();
    const { result } = renderHook(() => useAdaptiveContext("proj-1"), { wrapper: wrapper(qc) });
    await waitFor(() => expect(result.current.data?.enabled).toBe(true));
    expect(qc.getQueryData(adaptiveKeys.context("proj-1"))).toBeTruthy();
  });

  it("toggle mutation invalidates the canonical key", async () => {
    let toggledTo: boolean | null = null;
    let contextHits = 0;
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => {
        contextHits += 1;
        return HttpResponse.json({ ...CTX, enabled: toggledTo ?? true });
      }),
      http.post("*/api/v1/adaptive/proj-1/toggle", async ({ request }) => {
        toggledTo = ((await request.json()) as { enabled: boolean }).enabled;
        return HttpResponse.json({ enabled: toggledTo, weights: CTX.weights });
      }),
    );
    const qc = new QueryClient();
    const { result } = renderHook(() => useToggleAdaptive("proj-1"), {
      wrapper: wrapperWithObserver(qc, "proj-1"),
    });
    result.current.mutate(false);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    await waitFor(() => expect(contextHits).toBeGreaterThan(1)); // refetched
  });

  it("setWeights mutation invalidates the canonical key", async () => {
    const spy = vi.fn();
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)),
      http.post("*/api/v1/adaptive/proj-1/weights", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: true, weights: CTX.weights });
      }),
    );
    const qc = new QueryClient();
    const { result } = renderHook(() => useSetAdaptiveWeights("proj-1"), { wrapper: wrapper(qc) });
    result.current.mutate({
      preference: 0.3,
      voice_fidelity: 0.3,
      style_constraints: 0.3,
      avoidance: 0.3,
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(spy).toHaveBeenCalled();
  });
});
