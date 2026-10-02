import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { importApi, setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
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

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
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
          excludedIndices: [],
          titleOverrides: {},
          includedCount: 1,
        }),
      );
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
});

// Note: WizardShell is not fully tested because it makes authApi.me call during render
// which requires more complex mocking. This is a known limitation.
