/**
 * SeriesVoiceOverrideEditor component tests (Spec 3, Tasks 5–6).
 *
 * The editor is a JSON-textarea that PATCHes a full author-voice profile dict
 * (validated server-side) and offers a clear button. Tests isolate it by
 * mocking the two override hooks.
 */
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const mock = vi.hoisted(() => ({
  update: vi.fn(),
  updatePending: false,
  clear: vi.fn(),
  clearPending: false,
}));

vi.mock("@/lib/hooks/useSeriesVoice", () => ({
  useUpdateSeriesVoiceOverride: () => ({
    mutate: (...args: unknown[]) => mock.update(...args),
    isPending: mock.updatePending,
  }),
  useClearSeriesVoiceOverride: () => ({
    mutate: (...args: unknown[]) => mock.clear(...args),
    isPending: mock.clearPending,
  }),
}));

import { SeriesVoiceOverrideEditor } from "@/components/series/SeriesVoiceOverrideEditor";

const SERIES_ID = "series-1";

const profileFixture = {
  voice_analysis: { vocabulary_level: "literary" },
  author_examples: ["The rain fell."],
};

function resetMocks(): void {
  mock.update = vi.fn();
  mock.clear = vi.fn();
  mock.updatePending = false;
  mock.clearPending = false;
}

describe("SeriesVoiceOverrideEditor", () => {
  beforeEach(() => resetMocks());

  it("prefills the textarea with the current voice as JSON", () => {
    render(<SeriesVoiceOverrideEditor seriesId={SERIES_ID} initialVoice={profileFixture} />);
    const textarea = screen.getByTestId("series-voice-override-input") as HTMLTextAreaElement;
    expect(JSON.parse(textarea.value)).toEqual(profileFixture);
  });

  it("shows an empty textarea when there is no voice", () => {
    render(<SeriesVoiceOverrideEditor seriesId={SERIES_ID} initialVoice={null} />);
    const textarea = screen.getByTestId("series-voice-override-input") as HTMLTextAreaElement;
    expect(textarea.value).toBe("");
  });

  it("saves the parsed JSON via PATCH when valid", async () => {
    const user = userEvent.setup();
    render(<SeriesVoiceOverrideEditor seriesId={SERIES_ID} initialVoice={null} />);

    const textarea = screen.getByTestId("series-voice-override-input") as HTMLTextAreaElement;
    // fireEvent.change (not userEvent.type) — userEvent treats `{`/`}` as
    // special-key syntax, which would corrupt JSON entry.
    fireEvent.change(textarea, {
      target: { value: '{"voice_analysis":{"vocabulary_level":"plain"}}' },
    });

    await user.click(screen.getByTestId("series-voice-save-override"));

    expect(mock.update).toHaveBeenCalledTimes(1);
    const payload = mock.update.mock.calls[0][0] as { author_voice: Record<string, unknown> };
    expect(payload.author_voice).toEqual({ voice_analysis: { vocabulary_level: "plain" } });
  });

  it("shows an error and does not save when the JSON is invalid", async () => {
    const user = userEvent.setup();
    render(<SeriesVoiceOverrideEditor seriesId={SERIES_ID} initialVoice={null} />);

    const textarea = screen.getByTestId("series-voice-override-input") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "{not valid json" } });

    await user.click(screen.getByTestId("series-voice-save-override"));

    expect(mock.update).not.toHaveBeenCalled();
    expect(screen.getByTestId("series-voice-override-error")).toBeDefined();
  });

  it("clears the override via DELETE when the clear button is clicked", async () => {
    const user = userEvent.setup();
    render(<SeriesVoiceOverrideEditor seriesId={SERIES_ID} initialVoice={profileFixture} />);

    await user.click(screen.getByTestId("series-voice-clear-override"));

    // The clear hook captures seriesId in its closure (mirrors
    // BandOverrideEditor) — mutate() takes no args.
    expect(mock.clear).toHaveBeenCalledTimes(1);
  });
});
