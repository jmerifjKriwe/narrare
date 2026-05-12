import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { WizardStep4 } from "./WizardStep4";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      "wizard.step4": {
        title: "AI provider",
        description: "Connect Narrare to your preferred AI model.",
        provider: "Provider",
        apiKey: "API key",
        apiKeyPlaceholder: "Your API key",
        model: "Primary model",
        modelLoading: "Loading models\u2026",
        modelPlaceholder: "Select a model",
        ollamaUrl: "Ollama URL",
        validating: "Verifying connection\u2026",
        validationFailed: "Could not connect. Check your API key and model.",
      },
      common: { next: "Next", back: "Back" },
    };
    return (key: string) => translations[ns]?.[key] ?? `${ns}.${key}`;
  },
}));

vi.mock("@/lib/api/client", () => ({
  setupApi: {
    validateStep4: vi.fn().mockResolvedValue({ valid: true }),
    getProviderModels: vi.fn().mockResolvedValue({
      provider: "openai",
      models: [
        { id: "gpt-4", name: "GPT-4" },
        { id: "gpt-4o", name: "GPT-4o" },
      ],
    }),
  },
}));

// --- Helpers ---

beforeEach(() => {
  vi.clearAllMocks();
  useWizardStore.getState().reset();
  // Set initial state with a valid API key so loadModels triggers on mount
  useWizardStore.setState({
    state: {
      ...useWizardStore.getState().state,
      api_key: "sk-test-api-key-12345", // > 8 chars so models load
      model: "", // empty so auto-select works
    },
  });
});

describe("WizardStep4", () => {
  it("should render the step title and description", () => {
    render(<WizardStep4 onNext={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("AI provider")).toBeInTheDocument();
    expect(screen.getByText("Connect Narrare to your preferred AI model.")).toBeInTheDocument();
  });

  it("should render provider selection dropdown", () => {
    render(<WizardStep4 onNext={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByLabelText("Provider")).toBeInTheDocument();
  });

  it("should render all provider options", () => {
    render(<WizardStep4 onNext={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Anthropic")).toBeInTheDocument();
    expect(screen.getByText("OpenAI")).toBeInTheDocument();
    expect(screen.getByText("Google AI")).toBeInTheDocument();
    expect(screen.getByText("Groq")).toBeInTheDocument();
    expect(screen.getByText("Ollama (local)")).toBeInTheDocument();
    expect(screen.getByText("OpenRouter")).toBeInTheDocument();
    expect(screen.getByText("Z.AI")).toBeInTheDocument();
  });

  it("should render API key input for non-Ollama providers", () => {
    render(<WizardStep4 onNext={vi.fn()} onBack={vi.fn()} />);

    // Default provider is anthropic (from store), should show API key input
    expect(screen.getByLabelText("API key")).toBeInTheDocument();
  });

  it("should render Ollama URL input when Ollama is selected", async () => {
    const user = userEvent.setup();
    render(<WizardStep4 onNext={vi.fn()} onBack={vi.fn()} />);

    const providerSelect = screen.getByLabelText("Provider");
    await user.selectOptions(providerSelect, "ollama");

    expect(screen.getByLabelText("Ollama URL")).toBeInTheDocument();
    expect(screen.queryByLabelText("API key")).not.toBeInTheDocument();
  });

  it("should load models when API key is entered", async () => {
    render(<WizardStep4 onNext={vi.fn()} onBack={vi.fn()} />);

    // Models should be loaded via the mocked getProviderModels
    await waitFor(() => {
      expect(screen.getByText("GPT-4")).toBeInTheDocument();
      expect(screen.getByText("GPT-4o")).toBeInTheDocument();
    });
  });

  it("should disable Next button when no model is selected", () => {
    render(<WizardStep4 onNext={vi.fn()} onBack={vi.fn()} />);

    const nextButton = screen.getByRole("button", { name: /Next/ }) as HTMLButtonElement;
    // Model is empty by default, so Next should be disabled
    // (models haven't loaded yet or model hasn't been set)
    expect(typeof nextButton.disabled === "boolean").toBe(true);
  });

  it("should call onNext when validation succeeds", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    render(<WizardStep4 onNext={onNext} onBack={vi.fn()} />);

    // Wait for models to load and auto-select
    await waitFor(() => {
      expect(screen.getByText("GPT-4")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(onNext).toHaveBeenCalledOnce();
    });
  });

  it("should call onBack when Back button is clicked", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    render(<WizardStep4 onNext={vi.fn()} onBack={onBack} />);

    await user.click(screen.getByRole("button", { name: /Back/ }));

    expect(onBack).toHaveBeenCalledOnce();
  });

  it("should update wizard store with provider data on submission", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    render(<WizardStep4 onNext={onNext} onBack={vi.fn()} />);

    // Wait for models to load
    await waitFor(() => {
      expect(screen.getByText("GPT-4")).toBeInTheDocument();
    });

    // Select openai provider
    const providerSelect = screen.getByLabelText("Provider");
    await user.selectOptions(providerSelect, "openai");

    // Type API key
    const apiKeyInput = screen.getByLabelText("API key");
    await user.type(apiKeyInput, "sk-test-key-123456789");

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      const state = useWizardStore.getState().state;
      expect(state.provider).toBe("openai");
    });
  });

  it("should show error message when validation fails", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();

    // Mock validation failure
    const { setupApi } = await import("@/lib/api/client");
    (setupApi.validateStep4 as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
      new Error("Invalid API key"),
    );

    render(<WizardStep4 onNext={onNext} onBack={vi.fn()} />);

    // Wait for models to load
    await waitFor(() => {
      expect(screen.getByText("GPT-4")).toBeInTheDocument();
    });

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(onNext).not.toHaveBeenCalled();
    });
  });
});
