import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ChapterSummary } from "@/types";
import { WorkspaceSidebar } from "./WorkspaceSidebar";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => (key: string) => {
    const translations: Record<string, string> = {
      "editor.sidebar": "Chapters",
      "editor.addChapter": "Add chapter",
      "editor.untitled": "Untitled chapter",
      "editor.wordCount": "{count} words",
      "editor.romanStudio": "Roman Studio",
      "editor.romanStudioSubtitle": "AI-assisted writing",
      "editor.editor": "Editor",
      "editor.worldbuilding": "World & Characters",
      "editor.analysis": "Analysis",
      "editor.settings": "Settings",
      "editor.chapters": "CHAPTERS",
      "editor.newChapter": "New Chapter",
    };
    return translations[`${ns}.${key}`] ?? `${ns}.${key}`;
  },
}));

// Mock next/link
vi.mock("next/link", () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
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
const mockMutate = vi.fn();

vi.mock("@tanstack/react-query", () => ({
  useMutation: (options: Record<string, unknown>) => ({
    mutate: () => {
      mockMutate();
      const onSuccess = options.onSuccess as ((data: unknown) => void) | undefined;
      if (onSuccess) {
        onSuccess({ id: "new-ch", title: "", position: 0, word_count: 0 });
      }
    },
    mutateAsync: vi.fn(),
    isPending: false,
  }),
  useQuery: (options: { queryKey: string[] }) => {
    if (options.queryKey[0] === "auth" && options.queryKey[1] === "me") {
      return {
        data: { display_name: "Test User", email: "test@test.com" },
      };
    }
    // chapters query
    return {
      data: sampleChapters,
    };
  },
  useQueryClient: () => ({
    invalidateQueries: mockInvalidateQueries,
    setQueryData: mockSetQueryData,
  }),
}));

// Mock lucide-react icons — use aria-hidden spans to avoid text collisions
vi.mock("lucide-react", () => ({
  BookOpen: () => <span data-testid="book-icon" aria-hidden="true">BookIcon</span>,
  FileText: () => <span data-testid="file-icon" aria-hidden="true">FileIcon</span>,
  Package: () => <span data-testid="package-icon" aria-hidden="true">PackageIcon</span>,
  BarChart3: () => <span data-testid="chart-icon" aria-hidden="true">ChartIcon</span>,
  Settings: () => <span data-testid="settings-icon" aria-hidden="true">SettingsIcon</span>,
  Plus: () => <span data-testid="plus-icon" aria-hidden="true">PlusIcon</span>,
}));

// Mock editor store — supports both useEditorStore() and useEditorStore(selector)
const mockStoreState = {
  activeChapterId: null,
  setActiveChapterId: vi.fn(),
};
vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: (selector?: (s: typeof mockStoreState) => unknown) => {
    if (selector) return selector(mockStoreState);
    return mockStoreState;
  },
}));

// Mock API client
vi.mock("@/lib/api/client", () => ({
  authApi: { me: vi.fn() },
  chaptersApi: {
    list: vi.fn(),
    create: vi.fn(),
    reorder: vi.fn(),
  },
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
    title: "",
    position: 2,
    word_count: 0,
    status: "draft",
    updated_at: "2026-02-01T08:00:00Z",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("WorkspaceSidebar", () => {
  it("should render the branding section with link to dashboard", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    expect(screen.getByText("Roman Studio")).toBeInTheDocument();
    expect(screen.getByText("AI-assisted writing")).toBeInTheDocument();
    // Dashboard link exists
    const dashboardLink = screen.getByRole("link", { name: /Roman Studio/i });
    expect(dashboardLink).toHaveAttribute("href", "/dashboard");
  });

  it("should render all four navigation tabs", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    expect(screen.getByText("Editor")).toBeInTheDocument();
    expect(screen.getByText("World & Characters")).toBeInTheDocument();
    expect(screen.getByText("Analysis")).toBeInTheDocument();
    expect(screen.getByText("Settings")).toBeInTheDocument();
  });

  it("should highlight the active navigation tab", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    const editorLink = screen.getByText("Editor").closest("a");
    expect(editorLink).toHaveAttribute("aria-current", "page");
  });

  it("should not highlight inactive tabs", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    const analysisLink = screen.getByText("Analysis").closest("a");
    expect(analysisLink).not.toHaveAttribute("aria-current");
  });

  it("should generate correct nav links with novelId", () => {
    render(<WorkspaceSidebar novelId="novel-42" activeTab="editor" />);

    const editorLink = screen.getByText("Editor").closest("a");
    expect(editorLink).toHaveAttribute("href", "/novel/novel-42/editor");

    const worldbuildingLink = screen.getByText("World & Characters").closest("a");
    expect(worldbuildingLink).toHaveAttribute("href", "/novel/novel-42/worldbuilding");
  });

  it("should show chapter list when activeTab is editor", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    expect(screen.getByText("CHAPTERS")).toBeInTheDocument();
    expect(screen.getByText("The Beginning")).toBeInTheDocument();
    expect(screen.getByText("The Middle")).toBeInTheDocument();
  });

  it("should show 'Untitled chapter' for chapters with empty title", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    expect(screen.getByText("Untitled chapter")).toBeInTheDocument();
  });

  it("should hide chapter list when activeTab is not editor", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="worldbuilding" />);

    expect(screen.queryByText("CHAPTERS")).not.toBeInTheDocument();
    expect(screen.queryByText("The Beginning")).not.toBeInTheDocument();
  });

  it("should show the new chapter button when in editor view", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    expect(screen.getByText("New Chapter")).toBeInTheDocument();
  });

  it("should hide the new chapter button when not in editor view", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="analysis" />);

    expect(screen.queryByText("New Chapter")).not.toBeInTheDocument();
  });

  it("should call createChapter mutation when new chapter button is clicked", async () => {
    const user = userEvent.setup();
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    const newChapterButton = screen.getByRole("button", { name: /New Chapter/i });
    await user.click(newChapterButton);

    expect(mockMutate).toHaveBeenCalled();
  });

  it("should render user avatar section with display name", () => {
    render(<WorkspaceSidebar novelId="novel-1" activeTab="editor" />);

    expect(screen.getByText("Test User")).toBeInTheDocument();
    // Avatar initial
    expect(screen.getByText("T")).toBeInTheDocument();
  });
});
