import { HttpResponse, http } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";
import { adaptiveApi } from "@/lib/api/adaptive";
import { server } from "@/mocks/server";

const CTX = {
  project_id: "proj-1",
  enabled: true,
  weights: { preference: 0.7, voice_fidelity: 0.9, style_constraints: 1.0, avoidance: 1.0 },
  sources: {
    preference_text: "prefers terse prose",
    voice_profiles_text: "",
    style_constraints_text: "",
    avoidance_patterns_text: "",
  },
  has_any_signal: true,
};

afterEach(() => server.resetHandlers());

describe("adaptiveApi REST client", () => {
  it("GET /context returns AdaptiveContextResponse", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)));
    const res = await adaptiveApi.getContext("proj-1");
    expect(res.has_any_signal).toBe(true);
    expect(res.weights.voice_fidelity).toBe(0.9);
  });

  it("POST /toggle sends {enabled} and returns settings", async () => {
    const spy = vi.fn();
    server.use(
      http.post("*/api/v1/adaptive/proj-1/toggle", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: false, weights: CTX.weights });
      }),
    );
    const res = await adaptiveApi.toggle("proj-1", false);
    expect(spy).toHaveBeenCalledWith({ enabled: false });
    expect(res.enabled).toBe(false);
  });

  it("POST /weights sends 4 weights", async () => {
    const spy = vi.fn();
    server.use(
      http.post("*/api/v1/adaptive/proj-1/weights", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: true, weights: CTX.weights });
      }),
    );
    await adaptiveApi.setWeights("proj-1", {
      preference: 0.5,
      voice_fidelity: 0.5,
      style_constraints: 0.5,
      avoidance: 0.5,
    });
    expect(spy).toHaveBeenCalledWith({
      preference: 0.5,
      voice_fidelity: 0.5,
      style_constraints: 0.5,
      avoidance: 0.5,
    });
  });
});
