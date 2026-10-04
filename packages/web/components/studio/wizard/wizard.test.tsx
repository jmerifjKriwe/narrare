import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { authApi, importApi, setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { ImportPreviewItem } from "@/types";
import { WizardShell } from "./WizardShell";
import { WizardStep1 } from "./WizardStep1";
import { WizardStep2 } from "./WizardStep2";
import { WizardStep3 } from "./WizardStep3";
import { WizardStep5 } from "./WizardStep5";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@/lib/api/client", () => ({
  authApi: {
    me: vi.fn(),
  },
  setupApi: {
    validateStep1: vi.fn().mockResolvedValue({ valid: true }),
    validateStep2: vi.fn().mockResolvedValue({ valid: true }),
    validateStep3: vi.fn().mockResolvedValue({ valid: true, starter: "blank", demo_info: null }),
    complete: vi.fn().mockResolvedValue({
      novel_id: "new-novel-id",
      redirect_to: "/novel/new-novel-id",
    }),
  },
  importApi: {
    preview: vi.fn(),
    commit: vi.fn(),
  },
}));

// The global setupTests.ts next-intl mock returns i18n KEY STRINGS, which would
// make the copy matchers below tautologies on key names. Resolving against the
// REAL en catalogs instead proves the rendered copy comes from the actual
// message trees — the per-file pattern used by SidebarChapterList.test.tsx and
// ImportPreviewPanel.test.tsx. Namespaces outside the two catalogs ("common")
// fall back to the raw key, which the structural assertions don't depend on.
// useLocale is pinned because next-intl's real hook needs a provider context.
vi.mock("next-intl", async () => {
  const actual = await vi.importActual<typeof import("next-intl")>("next-intl");
  const { default: studio } = await import("../../../../i18n/messages/en/studio.json");
  const { default: importing } = await import("../../../../i18n/messages/en/importing.json");
  const messages: Record<string, unknown> = { studio, importing };
  return {
    ...actual,
    useLocale: () => "en",
    useTranslations: (namespace: string) => (key: string, params?: Record<string, unknown>) => {
      let value: unknown = messages;
      for (const segment of `${namespace}.${key}`.split(".")) {
        if (value && typeof value === "object") {
          value = (value as Record<string, unknown>)[segment];
        }
      }
      let text = typeof value === "string" ? value : `${namespace}.${key}`;
      if (params) {
        for (const [name, replacement] of Object.entries(params)) {
          text = text.replace(`{${name}}`, String(replacement));
        }
      }
      return text;
    },
  };
});

// Hoisted so tests can assert navigation while WizardShell calls useRouter()
// internally (a per-call `vi.fn()` would be unreferenceable from tests).
const routerPush = vi.hoisted(() => vi.fn());

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPush,
  }),
}));

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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("WizardStep1", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(setupApi.validateStep1).mockResolvedValue({ valid: true });

    useWizardStore.setState({
      currentStep: 1,
      state: {
        project_name: "",
        writing_language: "en",
        autosave_interval: 30,
        title: "",
        author: "",
        genre: "",
        logline: "",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        provider: "openai",
        api_key: "",
        model: "gpt-4o",
        ollama_url: "http://localhost:11434",
      },
    });
  });

  describe("rendering", () => {
    it("renders step 1 form", async () => {
      const onNext = vi.fn();
      renderWithProviders(<WizardStep1 onNext={onNext} />);

      await waitFor(() => {
        expect(document.querySelector("form")).toBeInTheDocument();
      });
    });
  });
});

describe("WizardStep2", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(setupApi.validateStep3).mockResolvedValue({
      valid: true,
      starter: "blank",
      demo_info: null,
    });

    useWizardStore.setState({
      currentStep: 2,
      importSelection: null,
      state: {
        project_name: "Test Project",
        writing_language: "en",
        autosave_interval: 30,
        title: "",
        author: "",
        genre: "",
        logline: "",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        provider: "openai",
        api_key: "",
        model: "gpt-4o",
        ollama_url: "http://localhost:11434",
      },
    });
  });

  describe("rendering", () => {
    it("renders step 2 component", async () => {
      const onNext = vi.fn();
      const onBack = vi.fn();

      renderWithProviders(<WizardStep2 onNext={onNext} onBack={onBack} />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });

  describe("import starter", () => {
    it("renders the inline import section with the preview panel when the import card is selected", () => {
      renderWithProviders(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);

      expect(screen.queryByTestId("wizard-import-section")).not.toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: /import manuscript/i }));

      expect(screen.getByTestId("wizard-import-section")).toBeInTheDocument();
      expect(screen.getByTestId("import-preview-panel")).toBeInTheDocument();
    });

    it("publishes picked-file selections into the wizard store", async () => {
      vi.mocked(importApi.preview).mockResolvedValue({
        items: [{ index: 0, suggested_title: "One", word_count: 12, source_file: "a.md" }],
        file_count: 1,
        chapter_count: 1,
        total_word_count: 12,
      });
      renderWithProviders(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);

      fireEvent.click(screen.getByRole("button", { name: /import manuscript/i }));
      const input = screen.getByLabelText(/choose files/i) as HTMLInputElement;
      const file = new File(["# One\nbody"], "a.md", { type: "text/markdown" });
      fireEvent.change(input, { target: { files: [file] } });

      await waitFor(() =>
        expect(useWizardStore.getState().importSelection).toEqual({
          files: [file],
          items: [{ index: 0, suggested_title: "One", word_count: 12, source_file: "a.md" }],
          ops: { splits: {}, merges: [] },
          excludedKeys: [],
          titleByKey: {},
          includedCount: 1,
        }),
      );
    });

    it("clears the import selection when the user toggles away from the import card", async () => {
      // Task-9 review rider: a stale importSelection must not survive a card
      // switch — otherwise a later non-import completion could commit files
      // the user left behind (shell gates on `starter === "import"`, but the
      // store must not carry the desync in the first place).
      useWizardStore.setState({
        state: { ...useWizardStore.getState().state, starter: "import" },
        importSelection: {
          files: [new File(["x"], "a.md")],
          items: [],
          ops: { splits: {}, merges: [] },
          excludedKeys: [],
          titleByKey: {},
          includedCount: 1,
        },
      });
      renderWithProviders(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);

      fireEvent.click(screen.getByRole("button", { name: /blank project/i }));

      await waitFor(() => expect(useWizardStore.getState().importSelection).toBeNull());
    });
  });
});

describe("WizardStep3", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useWizardStore.setState({
      currentStep: 3,
      state: {
        project_name: "Test Project",
        writing_language: "en",
        autosave_interval: 30,
        title: "My Novel",
        author: "Test Author",
        genre: "fantasy",
        logline: "A test story",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        provider: "openai",
        api_key: "",
        model: "gpt-4o",
        ollama_url: "http://localhost:11434",
      },
    });
  });

  describe("rendering", () => {
    it("renders step 3 component", async () => {
      const onNext = vi.fn();
      const onBack = vi.fn();

      renderWithProviders(<WizardStep3 onNext={onNext} onBack={onBack} />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });
});

describe("WizardStep5", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(setupApi.complete).mockResolvedValue({
      novel_id: "new-novel-id",
      redirect_to: "/novel/new-novel-id",
      message: "Novel created successfully",
    });

    useWizardStore.setState({
      currentStep: 5,
      state: {
        project_name: "Test Project",
        writing_language: "en",
        autosave_interval: 30,
        title: "My Novel",
        author: "Test Author",
        genre: "fantasy",
        logline: "A test story",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        provider: "openai",
        api_key: "test-key",
        model: "gpt-4o",
        ollama_url: "http://localhost:11434",
      },
    });
  });

  describe("rendering", () => {
    it("renders step 5 component", async () => {
      const onComplete = vi.fn();
      const onBack = vi.fn();

      renderWithProviders(<WizardStep5 onComplete={onComplete} onBack={onBack} />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });

  describe("import summary", () => {
    it("shows import summary counts when starter is import", () => {
      useWizardStore.setState({
        state: { ...useWizardStore.getState().state, starter: "import" },
        importSelection: {
          files: [new File(["x"], "a.md"), new File(["x"], "b.md"), new File(["x"], "c.md")],
          items: [],
          ops: { splits: {}, merges: [] },
          excludedKeys: ["2#0"],
          titleByKey: {},
          includedCount: 2,
        },
      });
      renderWithProviders(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

      // Chapters = includedCount (3 picked files, 1 excluded → 2 chapters),
      // files = raw picked count — the two numbers come from different fields.
      expect(screen.getByText("3 files · 2 chapters")).toBeInTheDocument();
    });

    it("falls back to the plain import label when no selection is present", () => {
      useWizardStore.setState({
        state: { ...useWizardStore.getState().state, starter: "import" },
        importSelection: null,
      });
      renderWithProviders(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

      expect(screen.getByText("Import manuscript")).toBeInTheDocument();
    });
  });
});

// WizardShell completion sequence (ADR-091 spec §6.3): complete → (import?)
// commit → reset → navigate, with the documented degrade path on commit
// failure. The shell is driven via the store (currentStep: 5) instead of
// clicking through steps 1–4 — the authApi.me mock below settles the
// provider check that previously made the shell untestable.
describe("WizardShell completion", () => {
  const fullUser = {
    id: "user-1",
    email: "writer@example.com",
    display_name: "Writer",
    is_active: true,
    is_verified: true,
    has_providers: false,
    created_at: "2026-01-01T00:00:00Z",
  };

  const importSelectionFor = (files: File[]) => ({
    files,
    items: [] as ImportPreviewItem[],
    ops: { splits: {}, merges: [] },
    excludedKeys: [] as string[],
    titleByKey: {} as Record<string, string>,
    includedCount: files.length,
  });

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorage.removeItem("narrare:importFailed:novel-9");
    sessionStorage.removeItem("narrare:importSuggestExtract:novel-9");
    vi.mocked(authApi.me).mockResolvedValue(fullUser);
    vi.mocked(setupApi.complete).mockResolvedValue({
      novel_id: "novel-9",
      redirect_to: "/dashboard",
      message: "",
    });

    useWizardStore.setState({
      currentStep: 5,
      importSelection: null,
      state: {
        project_name: "Test Project",
        writing_language: "en",
        autosave_interval: 30,
        title: "My Novel",
        author: "Test Author",
        genre: "fantasy",
        logline: "A test story",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        provider: "openai",
        api_key: "test-key",
        model: "gpt-4o",
        ollama_url: "http://localhost:11434",
      },
    });
  });

  it("commits the import after setup completion and navigates to the new novel", async () => {
    const file = new File(["# A\nb"], "a.md");
    useWizardStore.setState({
      state: { ...useWizardStore.getState().state, starter: "import" },
      importSelection: importSelectionFor([file]),
    });
    vi.mocked(importApi.commit).mockResolvedValue({
      novel_id: "novel-9",
      created_count: 1,
      first_position: 0,
      last_position: 0,
      chapters: [],
    });

    renderWithProviders(<WizardShell />);
    // The shell gates on authApi.me() resolving — wait out the loading state.
    fireEvent.click(await screen.findByTestId("wizard-complete"));

    // Commit receives the picked files + the novel the backend just created.
    await waitFor(() =>
      expect(importApi.commit).toHaveBeenCalledWith([file], "novel-9", {
        splits: [],
        merges: [],
        excluded_indices: [],
        title_overrides: {},
      }),
    );
    // Selection and wizard state are consumed — reset() ran after the commit
    // (capture-before-reset is proven by commit having received the files).
    expect(useWizardStore.getState().importSelection).toBeNull();
    expect(useWizardStore.getState().currentStep).toBe(1);
    expect(routerPush).toHaveBeenCalledWith("/novel/novel-9");
    expect(sessionStorage.getItem("narrare:importFailed:novel-9")).toBeNull();
  });

  it("sets the importFailed flag and still navigates when the commit fails", async () => {
    useWizardStore.setState({
      state: { ...useWizardStore.getState().state, starter: "import" },
      importSelection: importSelectionFor([new File(["x"], "a.md")]),
    });
    vi.mocked(importApi.commit).mockRejectedValue(new Error("boom"));

    renderWithProviders(<WizardShell />);
    // The shell gates on authApi.me() resolving — wait out the loading state.
    fireEvent.click(await screen.findByTestId("wizard-complete"));

    // Documented degrade path: the user still lands in the (empty) novel;
    // the sidebar banner offers a retry via the ImportModal.
    await waitFor(() => expect(sessionStorage.getItem("narrare:importFailed:novel-9")).toBe("1"));
    expect(routerPush).toHaveBeenCalledWith("/novel/novel-9");
    expect(useWizardStore.getState().importSelection).toBeNull();
    // A failed commit must never suggest extraction (F2 T8 flag contract).
    expect(sessionStorage.getItem("narrare:importSuggestExtract:novel-9")).toBeNull();
  });

  it("sets the importSuggestExtract flag with the committed ids + word count on success", async () => {
    const file = new File(["# A\nb"], "a.md");
    useWizardStore.setState({
      state: { ...useWizardStore.getState().state, starter: "import" },
      importSelection: importSelectionFor([file]),
    });
    vi.mocked(importApi.commit).mockResolvedValue({
      novel_id: "novel-9",
      created_count: 2,
      first_position: 0,
      last_position: 1,
      chapters: [
        { id: "c1", title: "One", position: 1, word_count: 20 },
        { id: "c2", title: "Two", position: 2, word_count: 14 },
      ],
    });

    renderWithProviders(<WizardShell />);
    fireEvent.click(await screen.findByTestId("wizard-complete"));

    // Self-contained payload (spec §8.1): the sidebar CTA needs no extra fetch.
    await waitFor(() =>
      expect(sessionStorage.getItem("narrare:importSuggestExtract:novel-9")).toBe(
        JSON.stringify({ chapter_ids: ["c1", "c2"], word_count: 34 }),
      ),
    );
    expect(sessionStorage.getItem("narrare:importFailed:novel-9")).toBeNull();
    expect(routerPush).toHaveBeenCalledWith("/novel/novel-9");
  });

  it("does not set the suggestion flag for an empty commit result", async () => {
    useWizardStore.setState({
      state: { ...useWizardStore.getState().state, starter: "import" },
      importSelection: importSelectionFor([new File(["x"], "a.md")]),
    });
    vi.mocked(importApi.commit).mockResolvedValue({
      novel_id: "novel-9",
      created_count: 0,
      first_position: 0,
      last_position: 0,
      chapters: [],
    });

    renderWithProviders(<WizardShell />);
    fireEvent.click(await screen.findByTestId("wizard-complete"));

    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/novel/novel-9"));
    // Nothing was imported → there is nothing to suggest extracting.
    expect(sessionStorage.getItem("narrare:importSuggestExtract:novel-9")).toBeNull();
  });

  it("bounds the suggestion payload at 100 chapter ids", async () => {
    useWizardStore.setState({
      state: { ...useWizardStore.getState().state, starter: "import" },
      importSelection: importSelectionFor([new File(["x"], "a.md")]),
    });
    const chapters = Array.from({ length: 101 }, (_, i) => ({
      id: `c${i}`,
      title: `Chapter ${i}`,
      position: i,
      word_count: 1,
    }));
    vi.mocked(importApi.commit).mockResolvedValue({
      novel_id: "novel-9",
      created_count: 101,
      first_position: 0,
      last_position: 100,
      chapters,
    });

    renderWithProviders(<WizardShell />);
    fireEvent.click(await screen.findByTestId("wizard-complete"));

    await waitFor(() =>
      expect(sessionStorage.getItem("narrare:importSuggestExtract:novel-9")).not.toBeNull(),
    );
    const parsed = JSON.parse(
      sessionStorage.getItem("narrare:importSuggestExtract:novel-9") ?? "",
    ) as { chapter_ids: string[]; word_count: number };
    expect(parsed.chapter_ids).toHaveLength(100);
    expect(parsed.chapter_ids[0]).toBe("c0");
    expect(parsed.chapter_ids[99]).toBe("c99");
    expect(parsed.word_count).toBe(100); // summed over the BOUNDED id list
  });

  it("does not commit when the starter is not import", async () => {
    // Belt and braces: a stale selection (e.g. left by a card toggle) must
    // never be committed for a non-import starter.
    useWizardStore.setState({
      importSelection: importSelectionFor([new File(["x"], "a.md")]),
    });

    renderWithProviders(<WizardShell />);
    // The shell gates on authApi.me() resolving — wait out the loading state.
    fireEvent.click(await screen.findByTestId("wizard-complete"));

    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/novel/novel-9"));
    expect(importApi.commit).not.toHaveBeenCalled();
    expect(sessionStorage.getItem("narrare:importFailed:novel-9")).toBeNull();
  });
});
