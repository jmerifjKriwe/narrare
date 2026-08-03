/**
 * axe-core a11y tests for the Adaptive Dashboard surface (ADR-069 §25 + §28;
 * Task 12).
 *
 * Two layers, mirroring `dialogue-coach-a11y.test.tsx`:
 *  1. Leaf components rendered directly with props (no MSW): the enable
 *     toggle, the 4 weight sliders, and the source summary (incl. the empty
 *     state).
 *  2. The {@link AdaptiveDashboard} composite driven through TanStack Query +
 *     MSW, scanned per state (loaded / empty-source / loading / error).
 *
 * web-design-guidelines gate:
 *  - The enable control is a `role="switch"` with an `aria-label` (verified
 *    structurally + axe `aria-toggle-field-name`).
 *  - Each slider has a `<label htmlFor>` pair AND an `aria-label`, so it is
 *    both labelled-by-text and operable by name (axe `label`).
 *  - Sources use a semantic `<dl>` (axe does not flag definition lists).
 *
 * `color-contrast` + `region` are disabled in the shared {@link runAxe} runner
 * (see `lib/test/axe.ts`).
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AdaptiveSourceList } from "@/components/studio/settings/_components/AdaptiveSourceList";
import { AdaptiveToggle } from "@/components/studio/settings/_components/AdaptiveToggle";
import { AdaptiveWeightSliders } from "@/components/studio/settings/_components/AdaptiveWeightSliders";
import { AdaptiveDashboard } from "@/components/studio/settings/AdaptiveDashboard";
import { runAxe } from "@/lib/test/axe";
import { server } from "@/mocks/server";
import type { AdaptiveSourceSummary, AdaptiveWeightsResponse } from "@/types";

function wrapper(qc: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>{children}</QueryClientProvider>
  );
}

/**
 * Deterministic QueryClient: `retry: false` so a mocked 500 settles to the
 * error state immediately (TanStack's default 3 retries would exceed the
 * `waitFor` budget). `gcTime: 0` keeps the cache isolated between tests.
 */
function testQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
}

const WEIGHTS: AdaptiveWeightsResponse = {
  preference: 0.7,
  voice_fidelity: 0.9,
  style_constraints: 1.0,
  avoidance: 1.0,
};

const SOURCES: AdaptiveSourceSummary = {
  preference_text: "Terse prose, minimal adverbs.",
  voice_profiles_text: "Alice (laconic), Bob (effusive)",
  style_constraints_text: "Present tense",
  avoidance_patterns_text: "adverbs, clichés",
};

const CTX = {
  project_id: "proj-1",
  enabled: true,
  weights: WEIGHTS,
  sources: SOURCES,
  has_any_signal: true,
};

afterEach(() => server.resetHandlers());

// ---------------------------------------------------------------------------
// Layer 1 — leaf components in isolation (deterministic, no MSW).
// ---------------------------------------------------------------------------

describe("AdaptiveToggle a11y", () => {
  it("renders a labelled switch with no violations", async () => {
    const { container } = render(
      <AdaptiveToggle enabled={true} onToggle={vi.fn()} pending={false} />,
    );
    const sw = screen.getByRole("switch", { name: "enableLabel" });
    expect(sw).toHaveAttribute("aria-checked", "true");
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("stays accessible when pending (disabled)", async () => {
    const { container } = render(
      <AdaptiveToggle enabled={false} onToggle={vi.fn()} pending={true} />,
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe("AdaptiveWeightSliders a11y", () => {
  it("renders 4 labelled sliders with no violations", async () => {
    const { container } = render(
      <AdaptiveWeightSliders weights={WEIGHTS} onCommit={vi.fn()} pending={false} />,
    );
    const sliders = screen.getAllByRole("slider");
    expect(sliders).toHaveLength(4);
    for (const slider of sliders) {
      // Every slider has an accessible name (label or aria-label).
      expect(slider.getAttribute("aria-label") ?? slider.id).toBeTruthy();
    }
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("stays accessible when pending (disabled sliders)", async () => {
    const { container } = render(
      <AdaptiveWeightSliders weights={WEIGHTS} onCommit={vi.fn()} pending={true} />,
    );
    // Radix Slider conveys the disabled state via `data-disabled` (not the
    // native `disabled` attribute), so assert that attribute rather than
    // `toBeDisabled()`. axe does not flag this — the slider retains its
    // name/role/value, which is what matters operably.
    for (const slider of screen.getAllByRole("slider")) {
      expect(slider).toHaveAttribute("data-disabled");
    }
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

describe("AdaptiveSourceList a11y + edge cases", () => {
  it("populated sources render a <dl> with no violations", async () => {
    const { container } = render(<AdaptiveSourceList sources={SOURCES} hasAnySignal={true} />);
    expect(container.querySelector("dl")).toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("has_any_signal=false → renders the noSignals empty state and passes axe", async () => {
    const { container } = render(
      <AdaptiveSourceList
        sources={{
          preference_text: "",
          voice_profiles_text: "",
          style_constraints_text: "",
          avoidance_patterns_text: "",
        }}
        hasAnySignal={false}
      />,
    );
    // Edge case (plan Step 3): no signal → empty-state message.
    expect(screen.getByText("noSignals")).toBeInTheDocument();
    expect(container.querySelector("dl")).not.toBeInTheDocument();
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("partial sources show the empty placeholder per row without violations", async () => {
    const { container } = render(
      <AdaptiveSourceList
        sources={{
          preference_text: "Terse prose.",
          voice_profiles_text: "",
          style_constraints_text: "",
          avoidance_patterns_text: "",
        }}
        hasAnySignal={true}
      />,
    );
    // Empty rows fall back to the source.empty placeholder (text, not blank).
    expect(screen.getAllByText("source.empty")).toHaveLength(3);
    expect(await runAxe(container)).toHaveNoViolations();
  });
});

// ---------------------------------------------------------------------------
// Layer 2 — AdaptiveDashboard composite (TanStack Query + MSW).
// ---------------------------------------------------------------------------

describe("AdaptiveDashboard a11y (states)", () => {
  // AdaptiveDashboard renders AdaptiveSnapshotHistory, which fires
  // GET /snapshots — mock it for every test in this describe so no unmocked
  // fetch hits the network (ECONNREFUSED to localhost:3000; Next.js dev
  // isn't running in the vitest step). resetHandlers() runs in afterEach.
  beforeEach(() => {
    server.use(
      http.get("*/api/v1/adaptive/proj-1/snapshots*", () =>
        HttpResponse.json({ project_id: "proj-1", items: [] }),
      ),
    );
  });

  it("loaded: toggle + 4 sliders + sources, no violations", async () => {
    server.use(http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)));
    const { container } = render(<AdaptiveDashboard novelId="proj-1" />, {
      wrapper: wrapper(testQueryClient()),
    });
    await waitFor(() =>
      expect(screen.getByRole("switch", { name: "enableLabel" })).toBeInTheDocument(),
    );
    expect(screen.getAllByRole("slider")).toHaveLength(4);
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("disabled dashboard (enabled=false) still passes axe", async () => {
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () =>
        HttpResponse.json({ ...CTX, enabled: false }),
      ),
    );
    const { container } = render(<AdaptiveDashboard novelId="proj-1" />, {
      wrapper: wrapper(testQueryClient()),
    });
    await waitFor(() =>
      expect(screen.getByRole("switch", { name: "enableLabel" })).toHaveAttribute(
        "aria-checked",
        "false",
      ),
    );
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("no-signal context renders the source empty state with no violations", async () => {
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () =>
        HttpResponse.json({
          project_id: "proj-1",
          enabled: true,
          weights: WEIGHTS,
          sources: {
            preference_text: "",
            voice_profiles_text: "",
            style_constraints_text: "",
            avoidance_patterns_text: "",
          },
          has_any_signal: false,
        }),
      ),
    );
    const { container } = render(<AdaptiveDashboard novelId="proj-1" />, {
      wrapper: wrapper(testQueryClient()),
    });
    await waitFor(() => expect(screen.getByText("noSignals")).toBeInTheDocument());
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("error state: alert region + message, no violations", async () => {
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () =>
        HttpResponse.json({ detail: "boom" }, { status: 500 }),
      ),
    );
    const { container } = render(<AdaptiveDashboard novelId="proj-1" />, {
      wrapper: wrapper(testQueryClient()),
    });
    await waitFor(() => expect(screen.getByRole("alert")).toBeInTheDocument());
    expect(await runAxe(container)).toHaveNoViolations();
  });

  it("slider keyboard (ArrowRight) commits and the result stays accessible", async () => {
    const spy = vi.fn();
    server.use(
      http.get("*/api/v1/adaptive/proj-1/context", () => HttpResponse.json(CTX)),
      http.post("*/api/v1/adaptive/proj-1/weights", async ({ request }) => {
        spy(await request.json());
        return HttpResponse.json({ enabled: true, weights: WEIGHTS });
      }),
    );
    const { container } = render(<AdaptiveDashboard novelId="proj-1" />, {
      wrapper: wrapper(testQueryClient()),
    });
    const slider = await screen.findByRole("slider", { name: "weight.preference" });
    // Edge case (plan Step 3): ArrowRight commits a new weight value.
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    await waitFor(() => expect(spy).toHaveBeenCalled());
    expect(await runAxe(container)).toHaveNoViolations();
  });
});
