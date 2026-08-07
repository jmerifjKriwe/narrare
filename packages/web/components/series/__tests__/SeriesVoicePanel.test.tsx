/**
 * SeriesVoicePanel component tests (Spec 3, Tasks 5–6).
 *
 * The panel is the orchestration layer for the series-voice tab: it loads the
 * voice state, lists novels for the "profile from band" dropdown, and wires the
 * profile trigger + override editor + clear button. These tests isolate the
 * panel by mocking the four `useSeriesVoice*` hooks and `useSeriesNovels`, plus
 * the two pure child components (profile view + override editor).
 *
 * Conventions (mirrors BandSummaryCard.test.tsx): the centralized setupTests.ts
 * mock returns i18n KEY STRINGS verbatim, so assertions check for keys.
 */
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

// --- Per-file mutable mock state (hoisted) -----------------------------------
const mock = vi.hoisted(() => ({
  query: {
    data: undefined as { series_id: string; author_voice: unknown } | undefined,
    isLoading: false,
    isError: false,
  },
  profile: vi.fn(),
  profilePending: false,
  novels: [] as { id: string; title: string }[],
}));

vi.mock("@/lib/hooks/useSeriesVoice", () => ({
  useSeriesVoice: () => mock.query,
  useProfileSeriesVoice: () => ({
    mutate: (...args: unknown[]) => mock.profile(...args),
    isPending: mock.profilePending,
  }),
  useUpdateSeriesVoiceOverride: () => ({ mutate: vi.fn(), isPending: false }),
  useClearSeriesVoiceOverride: () => ({ mutate: vi.fn(), isPending: false }),
}));

vi.mock("@/lib/hooks/useSeriesNovels", () => ({
  useSeriesNovels: () => ({ data: mock.novels, isLoading: false }),
}));

// Stub the pure child components so the panel test stays focused on
// orchestration (status, dropdown, profile trigger). Each has its own suite.
vi.mock("@/components/series/SeriesVoiceProfileView", () => ({
  SeriesVoiceProfileView: ({ profile }: { profile: unknown }) => (
    <div data-testid="series-voice-profile-view" data-profile={JSON.stringify(profile)} />
  ),
}));
vi.mock("@/components/series/SeriesVoiceOverrideEditor", () => ({
  SeriesVoiceOverrideEditor: ({ seriesId }: { seriesId: string }) => (
    <div data-testid="series-voice-override-editor" data-series-id={seriesId} />
  ),
}));

import { SeriesVoicePanel } from "@/components/series/SeriesVoicePanel";

const SERIES_ID = "series-1";

const profileFixture = {
  voice_analysis: { vocabulary_level: "literary" },
  author_examples: ["The rain fell."],
};

function resetMocks(): void {
  mock.query = { data: undefined, isLoading: false, isError: false };
  mock.profile = vi.fn();
  mock.profilePending = false;
  mock.novels = [
    { id: "novel-1", title: "Band I" },
    { id: "novel-2", title: "Band II" },
  ];
}

describe("SeriesVoicePanel", () => {
  beforeEach(() => resetMocks());

  it("shows a loading state while the voice is fetching", () => {
    mock.query = { data: undefined, isLoading: true, isError: false };
    render(<SeriesVoicePanel seriesId={SERIES_ID} />);
    expect(screen.getByTestId("series-voice-loading")).toBeDefined();
  });

  it("shows the empty status when no voice is profiled", () => {
    mock.query = {
      data: { series_id: SERIES_ID, author_voice: null },
      isLoading: false,
      isError: false,
    };
    render(<SeriesVoicePanel seriesId={SERIES_ID} />);
    expect(screen.getByTestId("series-voice-status").textContent).toContain("status.empty");
  });

  it("shows the auto-profiled status when a voice exists", () => {
    mock.query = {
      data: { series_id: SERIES_ID, author_voice: profileFixture },
      isLoading: false,
      isError: false,
    };
    render(<SeriesVoicePanel seriesId={SERIES_ID} />);
    expect(screen.getByTestId("series-voice-status").textContent).toContain("status.autoProfiled");
  });

  it("renders the profile view when a voice exists", () => {
    mock.query = {
      data: { series_id: SERIES_ID, author_voice: profileFixture },
      isLoading: false,
      isError: false,
    };
    render(<SeriesVoicePanel seriesId={SERIES_ID} />);
    const view = screen.getByTestId("series-voice-profile-view");
    expect(JSON.parse(view.getAttribute("data-profile") ?? "null")).toEqual(profileFixture);
  });

  it("profiles a novel when a band is selected and the trigger clicked", async () => {
    mock.query = {
      data: { series_id: SERIES_ID, author_voice: null },
      isLoading: false,
      isError: false,
    };
    const user = userEvent.setup();
    render(<SeriesVoicePanel seriesId={SERIES_ID} />);

    await user.selectOptions(screen.getByTestId("series-voice-profile-select"), "novel-2");
    await user.click(screen.getByTestId("series-voice-profile-trigger"));

    expect(mock.profile).toHaveBeenCalledWith("novel-2");
  });

  it("disables the profile trigger until a band is selected", () => {
    mock.query = {
      data: { series_id: SERIES_ID, author_voice: null },
      isLoading: false,
      isError: false,
    };
    render(<SeriesVoicePanel seriesId={SERIES_ID} />);
    const trigger = screen.getByTestId("series-voice-profile-trigger") as HTMLButtonElement;
    expect(trigger.disabled).toBe(true);
  });
});
