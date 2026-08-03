import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AdaptiveDashboard } from "@/components/studio/settings/AdaptiveDashboard";
import { server } from "@/mocks/server";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

const CTX = {
  project_id: "proj-1",
  enabled: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: {
    preference_text: "terse prose",
    voice_profiles_text: "Alice",
    style_constraints_text: "",
    avoidance_patterns_text: "",
  },
  has_any_signal: true,
};

afterEach(() => server.resetHandlers());

describe("AdaptiveDashboard", () => {
  it("renders toggle, 4 sliders, and sources", async () => {
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)),
      // AdaptiveDashboard also renders AdaptiveSnapshotHistory, which fires
      // GET /snapshots — mock it so no unmocked fetch hits the network
      // (ECONNREFUSED to localhost:3000; Next.js dev isn't running in vitest).
      http.get("*/api/v1/adaptive/proj-1/snapshots*", () =>
        HttpResponse.json({ project_id: "proj-1", items: [] }),
      ),
    );
    render(<AdaptiveDashboard novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    await waitFor(() =>
      expect(screen.getByRole("switch", { name: "enableLabel" })).toBeInTheDocument(),
    );
    expect(screen.getByRole("slider", { name: "weight.preference" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "weight.voice_fidelity" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "weight.style_constraints" })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: "weight.avoidance" })).toBeInTheDocument();
    expect(screen.getByText("terse prose")).toBeInTheDocument();
  });

  it("POSTs weights on slider commit", async () => {
    const spy = vi.fn();
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)),
      http.get("*/api/v1/adaptive/proj-1/snapshots*", () =>
        HttpResponse.json({ project_id: "proj-1", items: [] }),
      ),
      http.post("*/api/v1/adaptive/proj-1/weights", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: true, weights: CTX.weights });
      }),
    );
    render(<AdaptiveDashboard novelId="proj-1" />, { wrapper: wrapper(new QueryClient()) });
    const slider = await screen.findByRole("slider", { name: "weight.preference" });
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    await waitFor(() => expect(spy).toHaveBeenCalled());
  });
});
