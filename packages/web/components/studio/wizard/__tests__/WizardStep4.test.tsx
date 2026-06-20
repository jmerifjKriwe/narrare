import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { WizardStep4 } from "@/components/studio/wizard/WizardStep4";

// --- Hoisted helpers for mock factories (must be above vi.mock) ---

const { mockGetProviderModels, mockValidateStep4, mockUpdateStep4, mockUseWizardStoreFn } =
  vi.hoisted(() => ({
    mockGetProviderModels: vi.fn(),
    mockValidateStep4: vi.fn(),
    mockUpdateStep4: vi.fn(),
    mockUseWizardStoreFn: vi.fn(() => ({
      updateStep4: vi.fn(),
      state: {
        provider: "openai" as const,
        api_key: "",
        model: "",
        ollama_url: "http://localhost:11434",
        zai_endpoint: "general",
      },
    })),
  }));

// --- Mocks (hoisted by vitest automatically) ---

vi.mock("@/lib/api/client", () => ({
  setupApi: {
    getProviderModels: (...args: unknown[]) => mockGetProviderModels(...args),
    validateStep4: (...args: unknown[]) => mockValidateStep4(...args),
  },
}));

vi.mock("@/lib/stores/wizardStore", () => ({
  useWizardStore: mockUseWizardStoreFn,
}));

// --- Helpers ---

/**
 * Returns a store state with a long api_key so that the useEffect triggers
 * loadModels (provider === "ollama" OR key.length > 8).
 */
function makeStoreState(
  overrides: Partial<{
    provider: string;
    api_key: string;
    model: string;
    ollama_url: string;
    zai_endpoint: string;
  }> = {},
) {
  return {
    updateStep4: mockUpdateStep4,
    state: {
      provider: "openai" as const,
      api_key: "abcdefghijklmno",
      model: "",
      ollama_url: "http://localhost:11434",
      zai_endpoint: "general",
      ...overrides,
    },
  } as ReturnType<typeof mockUseWizardStoreFn>;
}

/** Find the "next →" button */
function getNextButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: /next/i });
}

/** Find the "← back" button */
function getBackButton(): HTMLButtonElement {
  return screen.getByRole("button", { name: /back/i });
}

// --- Tests ---

describe("WizardStep4", () => {
  const onNext = vi.fn();
  const onBack = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseWizardStoreFn.mockReturnValue(makeStoreState());
    mockGetProviderModels.mockReset();
    mockValidateStep4.mockReset();
  });

  it("renders step title and description", () => {
    render(<WizardStep4 onNext={onNext} onBack={onBack} />);
    expect(screen.getByText("wizard.step4.title")).toBeDefined();
    expect(screen.getByText("wizard.step4.description")).toBeDefined();
  });

  it("renders provider select with options", () => {
    render(<WizardStep4 onNext={onNext} onBack={onBack} />);
    const select = screen.getByLabelText("wizard.step4.provider");
    const options = select.querySelectorAll("option");
    expect(options.length).toBeGreaterThanOrEqual(4);
  });

  it("shows API key input for non-ollama providers", () => {
    render(<WizardStep4 onNext={onNext} onBack={onBack} />);
    expect(screen.getByLabelText("wizard.step4.apiKey")).toBeDefined();
    expect(screen.queryByLabelText("wizard.step4.ollamaUrl")).toBeNull();
  });

  it("shows ollama URL input when provider is ollama", () => {
    mockUseWizardStoreFn.mockReturnValueOnce(makeStoreState({ provider: "ollama" }));
    render(<WizardStep4 onNext={onNext} onBack={onBack} />);
    expect(screen.getByLabelText("wizard.step4.ollamaUrl")).toBeDefined();
    expect(screen.queryByLabelText("wizard.step4.apiKey")).toBeNull();
  });

  it("calls onBack when back button is clicked", () => {
    render(<WizardStep4 onNext={onNext} onBack={onBack} />);
    fireEvent.click(getBackButton());
    expect(onBack).toHaveBeenCalledOnce();
  });

  it("disables next button when no model is selected", () => {
    // Use short api_key so loadModels is NOT triggered → model stays ""
    // Also, we need the mock to not return any models (empty) as fallback
    mockUseWizardStoreFn.mockReturnValueOnce(makeStoreState({ api_key: "", model: "" }));
    render(<WizardStep4 onNext={onNext} onBack={onBack} />);
    expect(getNextButton().disabled).toBe(true);
  });

  it("enables next button when model is auto-selected", async () => {
    mockGetProviderModels.mockResolvedValue({
      models: [{ id: "gpt-4", name: "GPT-4" }],
    });
    render(<WizardStep4 onNext={onNext} onBack={onBack} />);
    await waitFor(() => {
      expect(getNextButton().disabled).toBe(false);
    });
  });

  it("calls validateStep4 and onNext when next is clicked", async () => {
    mockGetProviderModels.mockResolvedValue({
      models: [{ id: "gpt-4", name: "GPT-4" }],
    });
    mockValidateStep4.mockResolvedValue({ valid: true });

    render(<WizardStep4 onNext={onNext} onBack={onBack} />);

    // Wait for button to become enabled (model loaded)
    await waitFor(() => {
      expect(getNextButton().disabled).toBe(false);
    });

    fireEvent.click(getNextButton());

    await waitFor(() => {
      expect(mockValidateStep4).toHaveBeenCalled();
    });

    expect(mockUpdateStep4).toHaveBeenCalled();
    expect(onNext).toHaveBeenCalledOnce();
  });

  it("displays validation error when validateStep4 fails", async () => {
    mockGetProviderModels.mockResolvedValue({
      models: [{ id: "gpt-4", name: "GPT-4" }],
    });
    mockValidateStep4.mockRejectedValue(new Error("API key is required"));

    render(<WizardStep4 onNext={onNext} onBack={onBack} />);

    await waitFor(() => {
      expect(getNextButton().disabled).toBe(false);
    });

    fireEvent.click(getNextButton());

    await waitFor(() => {
      expect(screen.getByText("API key is required")).toBeDefined();
    });

    expect(onNext).not.toHaveBeenCalled();
  });

  it("shows model loading text when models are loading", async () => {
    // Never resolve the promise so modelsLoading stays true
    mockGetProviderModels.mockImplementation(() => new Promise(() => {}));

    render(<WizardStep4 onNext={onNext} onBack={onBack} />);

    await waitFor(() => {
      expect(screen.getByText("wizard.step4.modelLoading")).toBeDefined();
    });
  });

  it("renders model select when models are available", async () => {
    mockGetProviderModels.mockResolvedValue({
      models: [{ id: "gpt-4", name: "GPT-4" }],
    });

    render(<WizardStep4 onNext={onNext} onBack={onBack} />);

    await waitFor(() => {
      const el = screen.getByLabelText("wizard.step4.model");
      expect(el.tagName).toBe("SELECT");
    });
  });

  it("renders model text input when no models are available", async () => {
    mockGetProviderModels.mockResolvedValue({ models: [] });

    render(<WizardStep4 onNext={onNext} onBack={onBack} />);

    await waitFor(() => {
      const el = screen.getByLabelText("wizard.step4.model");
      expect(el.tagName).toBe("INPUT");
    });
  });

  it("renders offline fallback notice with reviewed date when provenance is bundled-fallback", async () => {
    mockGetProviderModels.mockResolvedValue({
      models: [{ id: "gpt-4", name: "GPT-4" }],
      provenance: { source: "bundled-fallback", last_reviewed: "2025-10-01" },
    });

    render(<WizardStep4 onNext={onNext} onBack={onBack} />);

    // Wait for models to load (notice is rendered alongside the loaded list)
    await waitFor(() => {
      expect(getNextButton().disabled).toBe(false);
    });

    const notice = screen.getByTestId("fallback-catalog-notice");
    expect(notice).toBeDefined();

    // The reviewed date must be visible, locale-formatted ("en" → "October 2025")
    const reviewed = screen.getByTestId("fallback-reviewed-date");
    expect(reviewed.textContent).toContain("October 2025");
  });

  it("does not render offline fallback notice when provenance source is live", async () => {
    mockGetProviderModels.mockResolvedValue({
      models: [{ id: "gpt-4", name: "GPT-4" }],
      provenance: { source: "live", last_reviewed: null },
    });

    render(<WizardStep4 onNext={onNext} onBack={onBack} />);

    await waitFor(() => {
      expect(getNextButton().disabled).toBe(false);
    });

    expect(screen.queryByTestId("fallback-catalog-notice")).toBeNull();
    expect(screen.queryByTestId("fallback-reviewed-date")).toBeNull();
  });
});
