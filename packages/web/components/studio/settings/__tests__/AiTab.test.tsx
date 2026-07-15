/**
 * AiTab tests — AI settings tab orchestration component.
 *
 * Tests:
 * 1. Renders provider list from API data
 * 2. Shows loading spinner when providers are loading
 * 3. Renders token profile select with default value
 * 4. Token profile change triggers mutation
 * 5. Renders all section child components
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AiTab } from "../AiTab";

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Hoisted mock data
// ---------------------------------------------------------------------------

const { mockProviders, mockAiSettings, mockModelsData, mockTokenLimits } = vi.hoisted(() => ({
  mockProviders: [
    {
      id: "provider-1",
      name: "OpenAI",
      provider_type: "openai",
      is_active: true,
    },
    {
      id: "provider-2",
      name: "Anthropic",
      provider_type: "anthropic",
      is_active: true,
    },
  ],

  mockAiSettings: {
    default_provider_id: "provider-1",
    default_model: "gpt-4",
    token_limit_profile: "balanced",
    category_overrides: {},
    intent_overrides: {},
    token_limit_overrides: {},
  },

  mockModelsData: {
    provider: "openai",
    models: [
      { id: "gpt-4", name: "GPT-4" },
      { id: "gpt-3.5", name: "GPT-3.5" },
    ],
  },

  mockTokenLimits: {
    output_limit: 2000,
    token_profile: "balanced",
    effective_output_limit: 2000,
    tier_percentages: {
      immediate: 0.3,
      recent: 0.2,
      kb_referenced: 0.25,
      kb_suggested: 0.15,
      pinned: 0.1,
    },
    ws_timeout: 1800,
    metadata: {
      catalogue: [
        { value: "quick", preset_output_limit: 500, is_custom: false },
        { value: "balanced", preset_output_limit: 2000, is_custom: false },
        { value: "long_texts", preset_output_limit: 8000, is_custom: false },
        { value: "comprehensive", preset_output_limit: 16000, is_custom: false },
        { value: "custom", preset_output_limit: null, is_custom: true },
      ],
      absolute_max: 131072,
      ux_recommended_max: 16000,
    },
    calibration: null,
    suitability: null,
  },
}));

// ---------------------------------------------------------------------------
// API mocks
// ---------------------------------------------------------------------------

const mockListProviders = vi.fn().mockResolvedValue(mockProviders);
const mockGetUserSettings = vi.fn().mockResolvedValue(mockAiSettings);
const mockGetProviderModels = vi.fn().mockResolvedValue(mockModelsData);
const mockUpdateUserSettings = vi.fn().mockResolvedValue({});
const mockGetResolved = vi.fn().mockResolvedValue(mockTokenLimits);
const mockTokenLimitsUpdateUser = vi.fn().mockResolvedValue({});

vi.mock("@/lib/api/client", () => ({
  aiSettingsApi: {
    listProviders: (...args: unknown[]) => mockListProviders(...args),
    getUserSettings: (...args: unknown[]) => mockGetUserSettings(...args),
    getProviderModels: (...args: unknown[]) => mockGetProviderModels(...args),
    updateUserSettings: (...args: unknown[]) => mockUpdateUserSettings(...args),
  },
  tokenLimitsApi: {
    getResolved: (...args: unknown[]) => mockGetResolved(...args),
    updateUser: (...args: unknown[]) => mockTokenLimitsUpdateUser(...args),
  },
}));

// ---------------------------------------------------------------------------
// Child component mocks
// ---------------------------------------------------------------------------

vi.mock("../ProviderList", () => ({
  ProviderList: vi.fn(({ providers }) => (
    <div data-testid="provider-list">{providers.length} providers</div>
  )),
}));

vi.mock("../ModelDataStatus", () => ({
  ModelDataStatus: vi.fn(() => <div data-testid="model-data-status">model-data-status</div>),
}));

vi.mock("../DefaultModelSection", () => ({
  DefaultModelSection: vi.fn(() => (
    <div data-testid="default-model-section">default-model-section</div>
  )),
}));

vi.mock("../CategoryOverrides", () => ({
  CategoryOverrides: vi.fn(() => <div data-testid="category-overrides">category-overrides</div>),
}));

vi.mock("../IntentOverrides", () => ({
  IntentOverrides: vi.fn(() => <div data-testid="intent-overrides">intent-overrides</div>),
}));

vi.mock("../ContextBudget", () => ({
  ContextBudget: vi.fn(() => <div data-testid="context-budget">context-budget</div>),
}));

vi.mock("../SystemTimeouts", () => ({
  SystemTimeouts: vi.fn(() => <div data-testid="system-timeouts">system-timeouts</div>),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AiTab", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListProviders.mockResolvedValue(mockProviders);
    mockGetUserSettings.mockResolvedValue(mockAiSettings);
    mockGetProviderModels.mockResolvedValue(mockModelsData);
    mockUpdateUserSettings.mockResolvedValue({});
    mockGetResolved.mockResolvedValue(mockTokenLimits);
    mockTokenLimitsUpdateUser.mockResolvedValue({});
  });

  it("renders provider list from API data", async () => {
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });
    expect(screen.getByTestId("provider-list").textContent).toBe("2 providers");
  });

  it("shows loading spinner when providers are loading", () => {
    mockListProviders.mockReturnValue(new Promise(() => {}));

    renderWithProviders(<AiTab />);

    // Loader2 spinner has animate-spin class
    const spinner = document.querySelector(".animate-spin");
    expect(spinner).toBeDefined();
  });

  it("renders token profile select with default value", async () => {
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });

    const select = screen.getByRole("combobox");
    expect(select).toBeDefined();
    expect((select as HTMLSelectElement).value).toBe("balanced");
  });

  it("renders exactly the five public token profile options (no conservative)", async () => {
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);

    expect(optionValues).toEqual(["quick", "balanced", "long_texts", "comprehensive", "custom"]);
    expect(optionValues).not.toContain("conservative");
  });

  it("populates profile options from the API metadata catalogue", async () => {
    mockGetResolved.mockResolvedValue({
      ...mockTokenLimits,
      metadata: {
        ...mockTokenLimits.metadata,
        catalogue: [
          { value: "custom", preset_output_limit: null, is_custom: true },
          { value: "comprehensive", preset_output_limit: 16000, is_custom: false },
          { value: "long_texts", preset_output_limit: 8000, is_custom: false },
          { value: "balanced", preset_output_limit: 2000, is_custom: false },
          { value: "quick", preset_output_limit: 500, is_custom: false },
        ],
      },
    });

    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);

    // Runtime metadata is the source of truth for option order/availability.
    expect(optionValues).toEqual(["custom", "comprehensive", "long_texts", "balanced", "quick"]);
  });

  it("allows custom raw output limits above the 16k recommended slider up to the exposed max", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });

    await user.selectOptions(screen.getByRole("combobox"), "custom");

    const customInput = screen.getByLabelText(
      "settings.ai.tokenLimits.customOutputLimitLabel",
    ) as HTMLInputElement;

    expect(customInput.max).toBe("131072");
    expect(screen.getByText("settings.ai.tokenLimits.recommendedRangeLabel")).toBeDefined();

    await user.clear(customInput);
    await user.type(customInput, "64000");
    await user.tab();

    await waitFor(() => {
      const requestPayloads = mockTokenLimitsUpdateUser.mock.calls.map((call) => call[0]);
      expect(requestPayloads).toContainEqual({ token_profile: "custom", output_limit: 64000 });
    });
  });

  it("renders calibration warnings when the API reports stale metadata", async () => {
    mockGetResolved.mockResolvedValue({
      ...mockTokenLimits,
      calibration: {
        provider: "openai",
        model_id: "gpt-test",
        status: "known_stale",
        source: "models.dev",
        provider_max_output_tokens: 4096,
        context_window_tokens: 128000,
        source_timestamp: 1700000000,
        cache_age_seconds: 999,
        detail: null,
      },
    });

    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByText("tokenWarnings.calibrationStale")).toBeDefined();
    });
    // Stale must not look calibrated.
    expect(screen.queryByTestId("token-calibrated")).toBeNull();
  });

  it("token profile change triggers mutation", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });

    const select = screen.getByRole("combobox");
    await user.selectOptions(select, "quick");

    await waitFor(() => {
      // useMutation.mutate() passes a second argument with context
      const callArgs = mockTokenLimitsUpdateUser.mock.calls[0];
      expect(callArgs[0]).toEqual({ token_profile: "quick" });
    });
  });

  it("renders all section child components", async () => {
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });

    // All sections are present in the DOM — even the advanced ones, which live
    // inside a collapsed <details> disclosure (progressive disclosure, CR-AUFG-07-32).
    expect(screen.getByTestId("model-data-status")).toBeDefined();
    expect(screen.getByTestId("default-model-section")).toBeDefined();
    expect(screen.getByTestId("category-overrides")).toBeDefined();
    expect(screen.getByTestId("intent-overrides")).toBeDefined();
    expect(screen.getByTestId("context-budget")).toBeDefined();
    expect(screen.getByTestId("system-timeouts")).toBeDefined();
  });

  it("keeps basic settings sections always visible without expanding advanced", async () => {
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeVisible();
    });

    // The three essential first-run controls plus the advanced-disclosure
    // toggle are always visible — no progressive disclosure hides them.
    expect(screen.getByTestId("model-data-status")).toBeVisible();
    expect(screen.getByTestId("default-model-section")).toBeVisible();
    expect(screen.getByText("settings.ai.advancedSettings")).toBeVisible();
  });

  it("hides advanced sections by default and reveals them when expanded", async () => {
    const user = userEvent.setup();
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeVisible();
    });

    // Progressive disclosure: advanced controls start collapsed.
    expect(screen.getByTestId("category-overrides")).not.toBeVisible();
    expect(screen.getByTestId("intent-overrides")).not.toBeVisible();
    expect(screen.getByTestId("context-budget")).not.toBeVisible();
    expect(screen.getByTestId("system-timeouts")).not.toBeVisible();

    // Reveal the advanced disclosure by activating its summary toggle.
    await user.click(screen.getByText("settings.ai.advancedSettings"));

    // Advanced controls are now visible.
    expect(screen.getByTestId("category-overrides")).toBeVisible();
    expect(screen.getByTestId("intent-overrides")).toBeVisible();
    expect(screen.getByTestId("context-budget")).toBeVisible();
    expect(screen.getByTestId("system-timeouts")).toBeVisible();
  });
});
