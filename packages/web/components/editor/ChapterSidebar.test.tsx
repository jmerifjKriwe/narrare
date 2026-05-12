import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChapterSummary } from "@/types";
import { ChapterSidebar } from "./ChapterSidebar";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => (key: string) => {
    const translations: Record<string, string> = {
      "editor.sidebar": "Chapters",
      "editor.addChapter": "Add chapter",
      "editor.untitled": "Untitled chapter",
      "editor.wordCount": "words",
    };
    return translations[`${ns}.${key}`] ?? `${ns}.${key}`;
  },
}));

// Mock @dnd-kit to avoid jsdom issues
vi.mock("@dnd-kit/core", () => ({
  DndContext: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  closestCenter: {},
  KeyboardSensor: {},
  PointerSensor: {},
  useSensor: () => ({}),
  useSensors: () => [],
}));

vi.mock("@dnd-kit/sortable", () => ({
  SortableContext: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  sortableKeyboardCoordinates: {},
  useSortable: () => ({
    attributes: {},
    listeners: {},
    setNodeRef: (el: HTMLElement | null) => el,
    transform: null,
    transition: null,
    isDragging: false,
  }),
  verticalListSortingStrategy: {},
}));

vi.mock("@dnd-kit/utilities", () => ({
  CSS: { Transform: { toString: () => "" } },
}));

// Mock @tanstack/react-query
const mockInvalidateQueries = vi.fn();
const mockSetQueryData = vi.fn();
vi.mock("@tanstack/react-query", () => ({
  useMutation: (options: Record<string, unknown>) => ({
    mutate: () => {
      const onSuccess = options.onSuccess as ((data: unknown) => void) | undefined;
      if (onSuccess) {
        onSuccess({ id: "new-ch", title: "", position: 0, word_count: 0 });
      }
    },
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
    setQueryData: mockSetQueryData,
  }),
}));

// Mock lucide-react icons
vi.mock("lucide-react", () => ({
  Plus: () => <span data-testid="plus-icon">+</span>,
  GripVertical: () => <span data-testid="grip-icon">&#8942;</span>,
}));

// --- Helpers ---

const sampleChapters: ChapterSummary[] = [
  {
    id: "ch-1",
    novel_id: "novel-1",
    volume_id: null,
    title: "The Beginning",
    position: 0,
    word_count: 1500,
    status: "draft",
    updated_at: "2026-01-15T10:30:00Z",
  },
  {
    id: "ch-2",
    novel_id: "novel-1",
    volume_id: null,
    title: "The Middle",
    position: 1,
    word_count: 2300,
    status: "reviewed",
    updated_at: "2026-01-20T14:00:00Z",
  },
  {
    id: "ch-3",
    novel_id: "novel-1",
    volume_id: null,
    title: "", // Untitled chapter
    position: 2,
    word_count: 0,
    status: "draft",
    updated_at: "2026-02-01T08:00:00Z",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ChapterSidebar", () => {
  it("should render chapter titles from props", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("The Beginning")).toBeInTheDocument();
    expect(screen.getByText("The Middle")).toBeInTheDocument();
  });

  it("should show 'Untitled chapter' for chapters with empty title", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    // The mock translates "editor.untitled" → "Untitled chapter"
    expect(screen.getByText("Untitled chapter")).toBeInTheDocument();
  });

  it("should display word count for chapters with words", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    // Word count text appears for chapters with word_count > 0
    // Our mock translates the key to "words"
    const wordCountElements = screen.getAllByText("words");
    expect(wordCountElements).toHaveLength(2); // ch-1 and ch-2 have word counts
  });

  it("should not display word count for chapters with 0 words", () => {
    const chaptersWithNoWords: ChapterSummary[] = [
      {
        id: "ch-1",
        novel_id: "novel-1",
        volume_id: null,
        title: "Empty Chapter",
        position: 0,
        word_count: 0,
        status: "draft",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ];

    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={chaptersWithNoWords}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Empty Chapter")).toBeInTheDocument();
    // No word count text should be present
    expect(screen.queryByText("words")).not.toBeInTheDocument();
  });

  it("should call onChapterSelect when a chapter is clicked", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();

    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId={null}
        onChapterSelect={handleSelect}
      />,
    );

    // Click on "The Beginning" chapter — it's inside a button with onClick
    const chapterButtons = screen.getAllByRole("button");
    const beginningButton = chapterButtons.find((btn) =>
      btn.textContent?.includes("The Beginning"),
    );
    expect(beginningButton).toBeTruthy();
    await user.click(beginningButton!);

    expect(handleSelect).toHaveBeenCalledWith("ch-1");
  });

  it("should distinguish active chapter with aria-current attribute", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId="ch-2"
        onChapterSelect={vi.fn()}
      />,
    );

    // The active chapter button should have aria-current="true"
    const activeButton = screen.getByText("The Middle").closest("button");
    expect(activeButton).toHaveAttribute("aria-current", "true");

    // Non-active chapter should NOT have aria-current
    const inactiveButton = screen.getByText("The Beginning").closest("button");
    expect(inactiveButton).not.toHaveAttribute("aria-current");
  });

  it("should render sidebar header with 'Chapters' label", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    expect(screen.getByText("Chapters")).toBeInTheDocument();
  });

  it("should render add chapter button in header", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    const addButtons = screen.getAllByRole("button", { name: "Add chapter" });
    expect(addButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("should render empty state with add chapter button when no chapters", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={[]}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    // Should show the add chapter button for empty state
    const addButtons = screen.getAllByRole("button");
    const addChapterButton = addButtons.find((btn) => btn.textContent?.includes("Add chapter"));
    expect(addChapterButton).toBeTruthy();
  });

  it("should render all chapters", () => {
    render(
      <ChapterSidebar
        novelId="novel-1"
        chapters={sampleChapters}
        activeChapterId={null}
        onChapterSelect={vi.fn()}
      />,
    );

    // Verify all three chapter titles are rendered
    expect(screen.getByText("The Beginning")).toBeInTheDocument();
    expect(screen.getByText("The Middle")).toBeInTheDocument();
    expect(screen.getByText("Untitled chapter")).toBeInTheDocument();
  });
});
