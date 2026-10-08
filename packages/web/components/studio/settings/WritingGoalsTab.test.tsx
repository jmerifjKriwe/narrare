/**
 * WritingGoalsTab tests — STATS-001 (Task E8). The "Project progress" target
 * persists as ProjectSettings.writing_goals via the shared project-settings
 * PATCH. Both API modules are mocked (hooks themselves are exercised at the
 * api-client level in their own suites); next-intl is mocked globally in
 * setupTests.ts, so assertions reference message keys.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WritingGoalsTab } from "./WritingGoalsTab";
import { parseTargetWords } from "./writingGoalRead";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api/client", () => ({
  chaptersApi: {
    list: vi.fn().mockResolvedValue([
      { id: "ch-1", novel_id: "novel-1", word_count: 1500 },
      { id: "ch-2", novel_id: "novel-1", word_count: 2500 },
    ]),
  },
}));

const getProject = vi.fn();
const updateProject = vi.fn();

vi.mock("@/lib/api/settings", () => ({
  settingsApi: {
    getProject: (novelId: string) => getProject(novelId),
    updateProject: (novelId: string, payload: unknown) => updateProject(novelId, payload),
  },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function settingsResponse(writing_goals: unknown) {
  return { novel_id: "novel-1", writing_goals, use_series_voice: true };
}

function createQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
}

function renderTab() {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <WritingGoalsTab novelId="novel-1" />
    </QueryClientProvider>,
  );
}

const SAVE_KEY = "settings.ai.save";

/** Types `text` into the writing-goal input (label comes from the i18n key). */
async function typeGoal(text: string) {
  const user = userEvent.setup();
  const input = await screen.findByLabelText("settings.writing.targetLabel");
  await user.clear(input);
  if (text) await user.type(input, text);
  return user;
}

beforeEach(() => {
  vi.clearAllMocks();
  getProject.mockResolvedValue(settingsResponse({ target_words: 80000 }));
  updateProject.mockResolvedValue(settingsResponse({ target_words: 80000 }));
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WritingGoalsTab", () => {
  describe("rendering", () => {
    it("renders title and description", async () => {
      renderTab();

      await waitFor(() => {
        expect(screen.getByText("settings.writing.title")).toBeInTheDocument();
        expect(screen.getByText("settings.writing.description")).toBeInTheDocument();
      });
    });

    it("renders daily goal input", async () => {
      renderTab();

      await waitFor(() => {
        expect(screen.getByText("settings.writing.dailyGoalDescription")).toBeInTheDocument();
        expect(screen.getByText("settings.writing.wordsPerDay")).toBeInTheDocument();
      });
    });

    it("renders project progress section", async () => {
      renderTab();

      await waitFor(() => {
        expect(screen.getByText("settings.writing.projectProgress")).toBeInTheDocument();
        expect(screen.getByText("settings.writing.projectProgressDescription")).toBeInTheDocument();
      });
    });

    it("shows word count against the stored goal", async () => {
      renderTab();

      // 1500 + 2500 = 4000 words vs the stored 80,000 target — toLocaleString()
      // varies by Node.js locale, so match loosely.
      await waitFor(() => {
        expect(screen.getByText(/4[.,]000/)).toBeInTheDocument();
        expect(screen.getByText(/80[.,]000/)).toBeInTheDocument();
      });
    });
  });

  describe("writing goal field (STATS-001 E8)", () => {
    it("renders the current target from a shaped writing_goals object", async () => {
      renderTab();

      await waitFor(() => {
        expect(screen.getByLabelText("settings.writing.targetLabel")).toHaveValue("80000");
      });
    });

    it("shows an empty (unset) field when no goal is stored", async () => {
      getProject.mockResolvedValue(settingsResponse(null));
      renderTab();

      await waitFor(() => {
        expect(screen.getByLabelText("settings.writing.targetLabel")).toHaveValue("");
      });
    });

    it("saves an edited target via the project-settings PATCH", async () => {
      renderTab();
      const user = await typeGoal("90000");
      await user.click(screen.getByRole("button", { name: SAVE_KEY }));

      await waitFor(() => {
        expect(updateProject).toHaveBeenCalledWith("novel-1", {
          writing_goals: { target_words: 90000 },
        });
      });
    });

    it("saves an explicit null when the field is cleared (unset)", async () => {
      renderTab();
      const user = await typeGoal("");
      await user.click(screen.getByRole("button", { name: SAVE_KEY }));

      await waitFor(() => {
        expect(updateProject).toHaveBeenCalledWith("novel-1", {
          writing_goals: { target_words: null },
        });
      });
    });

    it("blocks garbage drafts with a validation message and no API call", async () => {
      renderTab();

      // Negative and fractional drafts are typeable; letters are plain garbage.
      for (const garbage of ["-500", "12.5", "abc"]) {
        await typeGoal(garbage);
        expect(screen.getByText("settings.writing.targetInvalid")).toBeInTheDocument();
        expect(screen.queryByRole("button", { name: SAVE_KEY })).not.toBeInTheDocument();
      }
      expect(updateProject).not.toHaveBeenCalled();
    });

    it("treats corrupt stored goals (scalars, arrays, wrong-typed target) as unset", async () => {
      for (const corrupt of [50000, "50000", [1], true, { target_words: "80000" }]) {
        getProject.mockResolvedValue(settingsResponse(corrupt));
        const { unmount } = renderTab();

        await waitFor(() => {
          expect(screen.getByLabelText("settings.writing.targetLabel")).toHaveValue("");
        });
        expect(screen.getByText(/4[.,]000/)).toBeInTheDocument();
        unmount();
      }
    });

    it("shows a save error message when the PATCH fails", async () => {
      updateProject.mockRejectedValue(new Error("500"));
      renderTab();
      const user = await typeGoal("90000");
      await user.click(screen.getByRole("button", { name: SAVE_KEY }));

      expect(await screen.findByText("settings.writing.targetSaveError")).toBeInTheDocument();
    });
  });

  describe("parseTargetWords (defensive read narrowing)", () => {
    it("mirrors the backend parse: only a shaped int target passes through", () => {
      expect(parseTargetWords(undefined)).toBeNull();
      expect(parseTargetWords(null)).toBeNull();
      expect(parseTargetWords(50000)).toBeNull();
      expect(parseTargetWords("50000")).toBeNull();
      expect(parseTargetWords([1])).toBeNull();
      expect(parseTargetWords(true)).toBeNull();
      expect(parseTargetWords({})).toBeNull();
      expect(parseTargetWords({ target_words: null })).toBeNull();
      expect(parseTargetWords({ target_words: "80000" })).toBeNull();
      expect(parseTargetWords({ target_words: true })).toBeNull();
      expect(parseTargetWords({ target_words: 80.5 })).toBeNull();
      expect(parseTargetWords({ target_words: 80000 })).toBe(80000);
      expect(parseTargetWords({ target_words: 0 })).toBe(0);
    });
  });
});
