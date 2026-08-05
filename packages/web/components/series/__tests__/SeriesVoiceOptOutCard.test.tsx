/**
 * SeriesVoiceOptOutCard component tests (Spec 3, Task 6).
 *
 * The per-novel opt-out toggle ("Use series voice as base") persists
 * ``use_series_voice`` via PATCH /settings/novels/{id}. It is only visible when
 * the novel belongs to a series. Tests isolate it by mocking the settings API.
 */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mock = vi.hoisted(() => ({
  getProject: vi.fn(),
  updateProject: vi.fn(),
}));

vi.mock("@/lib/api/settings", () => ({
  settingsApi: {
    getProject: (...args: unknown[]) => mock.getProject(...args),
    updateProject: (...args: unknown[]) => mock.updateProject(...args),
  },
}));

import { SeriesVoiceOptOutCard } from "@/components/series/SeriesVoiceOptOutCard";

const NOVEL_ID = "novel-1";

function renderWithClient(node: ReactNode) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{node}</QueryClientProvider>);
}

function resetMocks(): void {
  mock.getProject = vi.fn();
  mock.updateProject = vi.fn();
  mock.getProject.mockResolvedValue({
    novel_id: NOVEL_ID,
    autosave_interval: 5,
    default_language: "en",
    ai_provider: "openai",
    ai_model: "gpt-4",
    model_overrides: "",
    use_series_voice: true,
    updated_at: "2026-08-04T10:00:00Z",
  });
}

describe("SeriesVoiceOptOutCard", () => {
  beforeEach(() => resetMocks());

  it("renders nothing when the novel is standalone (no seriesId)", async () => {
    const { container } = renderWithClient(
      <SeriesVoiceOptOutCard novelId={NOVEL_ID} seriesId={null} />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renders the toggle when the novel is in a series", async () => {
    renderWithClient(<SeriesVoiceOptOutCard novelId={NOVEL_ID} seriesId="series-1" />);
    expect(await screen.findByTestId("series-voice-opt-out")).toBeDefined();
  });

  it("reflects the stored use_series_voice flag as checked", async () => {
    renderWithClient(<SeriesVoiceOptOutCard novelId={NOVEL_ID} seriesId="series-1" />);
    const toggle = (await screen.findByTestId("series-voice-opt-out-toggle")) as HTMLInputElement;
    expect(toggle.checked).toBe(true);
  });

  it("PATCHes use_series_voice=false when toggled off", async () => {
    const user = userEvent.setup();
    renderWithClient(<SeriesVoiceOptOutCard novelId={NOVEL_ID} seriesId="series-1" />);
    const toggle = (await screen.findByTestId("series-voice-opt-out-toggle")) as HTMLInputElement;
    await user.click(toggle);
    expect(mock.updateProject).toHaveBeenCalledWith(NOVEL_ID, { use_series_voice: false });
  });

  it("PATCHes use_series_voice=true when toggled on from off", async () => {
    mock.getProject.mockResolvedValueOnce({
      novel_id: NOVEL_ID,
      autosave_interval: 5,
      default_language: "en",
      ai_provider: "openai",
      ai_model: "gpt-4",
      model_overrides: "",
      use_series_voice: false,
      updated_at: "2026-08-04T10:00:00Z",
    });
    const user = userEvent.setup();
    renderWithClient(<SeriesVoiceOptOutCard novelId={NOVEL_ID} seriesId="series-1" />);
    const toggle = (await screen.findByTestId("series-voice-opt-out-toggle")) as HTMLInputElement;
    await user.click(toggle);
    expect(mock.updateProject).toHaveBeenCalledWith(NOVEL_ID, { use_series_voice: true });
  });
});
