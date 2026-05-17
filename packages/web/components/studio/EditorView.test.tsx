import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { chaptersApi, volumesApi } from "@/lib/api/client";
import { useEditorStore } from "@/lib/stores/editorStore";
import type { Chapter, ChapterSummary } from "@/types";
import { EditorView } from "./EditorView";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock next-intl
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

// Mock API client — individual tests override return values
vi.mock("@/lib/api/client", () => ({
  chaptersApi: {
    get: vi.fn(),
    list: vi.fn(),
    updateMeta: vi.fn(),
    updateContent: vi.fn(),
  },
  volumesApi: {
    getStats: vi.fn(),
  },
}));

// Mock child components to isolate EditorView logic
vi.mock("./editor/CommandPalette", () => ({
  CommandPalette: () => null,
}));

vi.mock("./editor/MetadataSidebar", () => ({
  MetadataSidebar: () => null,
}));

vi.mock("./generation/NameGeneratorModal", () => ({
  NameGeneratorModal: () => null,
}));

vi.mock("./TipTapEditor", () => ({
  TipTapEditor: () => null,
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

/**
 * Build a Chapter-like object with a potentially null/undefined title.
 *
 * The TypeScript `Chapter` type declares `title: string`, but at runtime the
 * API may return `null` or `undefined` for newly created or partially-seeded
 * chapters. We use `as unknown as Chapter` to simulate this real-world edge
 * case in the regression test.
 */
function createChapterWithNullableTitle(
  titleOverride: string | null | undefined,
  overrides: Record<string, unknown> = {},
): Chapter {
  const base: Record<string, unknown> = {
    id: "ch-1",
    novel_id: "novel-1",
    volume_id: null,
    content: "<p>Some content</p>",
    summary: "",
    position: 0,
    word_count: 42,
    status: "draft",
    pov_character_id: "",
    timeline_position: "",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
    // Intentionally set title last to allow null/undefined values from API
    title: titleOverride,
  };
  return base as unknown as Chapter;
}

const mockChapters: ChapterSummary[] = [
  {
    id: "ch-1",
    novel_id: "novel-1",
    volume_id: null,
    title: "Chapter One",
    position: 0,
    word_count: 42,
    status: "draft",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = createQueryClient();
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

/**
 * Spy on console.error to capture React controlled/uncontrolled warnings.
 * These warnings are logged asynchronously (after useEffect runs), so we need
 * a persistent spy that stays active across render + waitFor lifecycle.
 */
class ConsoleErrorSpy {
  private errors: string[] = [];
  private original: typeof console.error;

  constructor() {
    this.original = console.error;
    console.error = (...args: unknown[]) => {
      this.errors.push(args.map(String).join(" "));
    };
  }

  /** Return all captured error messages. */
  getErrors(): string[] {
    return [...this.errors];
  }

  /** Return only messages containing controlled/uncontrolled warnings. */
  getControlledWarnings(): string[] {
    return this.errors.filter((e) => e.includes("controlled") && e.includes("uncontrolled"));
  }

  /** Restore original console.error. */
  restore() {
    console.error = this.original;
  }
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("EditorView — title controlled/uncontrolled regression", () => {
  let errorSpy: ConsoleErrorSpy;

  beforeEach(() => {
    errorSpy = new ConsoleErrorSpy();

    // Reset editor store with an active chapter so the component renders
    useEditorStore.setState({
      activeChapterId: "ch-1",
      activeVolumeId: null,
      editor: null,
      contextPanelOpen: false,
      saveStatus: "idle",
      lastSavedAt: null,
      sidebarOpen: true,
      focusMode: false,
      isDragging: false,
    });

    // Default mocks for secondary queries
    vi.mocked(chaptersApi.list).mockResolvedValue(mockChapters);
    vi.mocked(volumesApi.getStats).mockResolvedValue({
      word_count: 42,
      chapter_count: 1,
      word_count_target: null,
      completion_percentage: null,
    });
  });

  afterEach(() => {
    errorSpy.restore();
  });

  it("renders without React warning when chapter.title is null", async () => {
    const chapterWithNullTitle = createChapterWithNullableTitle(null);
    vi.mocked(chaptersApi.get).mockResolvedValue(chapterWithNullTitle);

    renderWithProviders(<EditorView novelId="novel-1" />);

    // Wait for the query to resolve and the title input to appear
    await waitFor(() => {
      const titleInput = screen.getByPlaceholderText("editor.chapterTitlePlaceholder");
      expect(titleInput).toBeInTheDocument();
      // The title input must always have a string value — never null/undefined
      expect(typeof (titleInput as HTMLInputElement).value).toBe("string");
      expect((titleInput as HTMLInputElement).value).toBe("");
    });

    // Must NOT produce a "controlled/uncontrolled" React warning
    expect(errorSpy.getControlledWarnings()).toHaveLength(0);
  });

  it("renders without React warning when chapter.title is undefined", async () => {
    const chapterWithUndefinedTitle = createChapterWithNullableTitle(undefined);
    vi.mocked(chaptersApi.get).mockResolvedValue(chapterWithUndefinedTitle);

    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      const titleInput = screen.getByPlaceholderText("editor.chapterTitlePlaceholder");
      expect(titleInput).toBeInTheDocument();
      expect(typeof (titleInput as HTMLInputElement).value).toBe("string");
      expect((titleInput as HTMLInputElement).value).toBe("");
    });

    expect(errorSpy.getControlledWarnings()).toHaveLength(0);
  });

  it("renders the title input with the actual string when chapter.title is a normal string", async () => {
    const chapterWithNormalTitle = createChapterWithNullableTitle("My Great Chapter");
    vi.mocked(chaptersApi.get).mockResolvedValue(chapterWithNormalTitle);

    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      const titleInput = screen.getByDisplayValue("My Great Chapter");
      expect(titleInput).toBeInTheDocument();
      expect((titleInput as HTMLInputElement).value).toBe("My Great Chapter");
    });

    expect(errorSpy.getControlledWarnings()).toHaveLength(0);
  });

  it("renders the title input as empty string when chapter.title is an empty string", async () => {
    const chapterWithEmptyTitle = createChapterWithNullableTitle("");
    vi.mocked(chaptersApi.get).mockResolvedValue(chapterWithEmptyTitle);

    renderWithProviders(<EditorView novelId="novel-1" />);

    await waitFor(() => {
      const titleInput = screen.getByPlaceholderText("editor.chapterTitlePlaceholder");
      expect(titleInput).toBeInTheDocument();
      expect((titleInput as HTMLInputElement).value).toBe("");
    });

    expect(errorSpy.getControlledWarnings()).toHaveLength(0);
  });
});
