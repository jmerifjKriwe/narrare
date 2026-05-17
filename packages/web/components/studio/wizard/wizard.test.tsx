import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { WizardStep1 } from "./WizardStep1";
import { WizardStep2 } from "./WizardStep2";
import { WizardStep3 } from "./WizardStep3";
import { WizardStep5 } from "./WizardStep5";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
  useLocale: () => "en",
}));

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
}));

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
        language: "en",
        autosave_interval: 30,
        title: "",
        author: "",
        genre: "",
        logline: "",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        import_path: null,
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
      state: {
        project_name: "Test Project",
        language: "en",
        autosave_interval: 30,
        title: "",
        author: "",
        genre: "",
        logline: "",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        import_path: null,
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
});

describe("WizardStep3", () => {
  beforeEach(() => {
    vi.clearAllMocks();

    useWizardStore.setState({
      currentStep: 3,
      state: {
        project_name: "Test Project",
        language: "en",
        autosave_interval: 30,
        title: "My Novel",
        author: "Test Author",
        genre: "fantasy",
        logline: "A test story",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        import_path: null,
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
        language: "en",
        autosave_interval: 30,
        title: "My Novel",
        author: "Test Author",
        genre: "fantasy",
        logline: "A test story",
        story_structure: "three_act",
        tone: "dramatic",
        starter: "blank",
        import_path: null,
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
