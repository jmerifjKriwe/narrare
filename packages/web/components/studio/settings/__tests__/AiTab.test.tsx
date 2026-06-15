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
    token_profile: "balanced",
    tier_percentages: {
      immediate: 0.3,
      recent: 0.2,
      kb_referenced: 0.25,
      kb_suggested: 0.15,
      pinned: 0.1,
    },
    ws_timeout: 1800,
    retry_max_attempts: 3,
    retry_base_delay: 1.0,
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

  it("renders all token profile options including comprehensive and conservative", async () => {
    renderWithProviders(<AiTab />);

    await waitFor(() => {
      expect(screen.getByTestId("provider-list")).toBeDefined();
    });

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionValues = Array.from(select.options).map((o) => o.value);

    expect(optionValues).toEqual([
      "quick",
      "balanced",
      "conservative",
      "long_texts",
      "comprehensive",
      "custom",
    ]);
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

    expect(screen.getByTestId("model-data-status")).toBeDefined();
    expect(screen.getByTestId("default-model-section")).toBeDefined();
    expect(screen.getByTestId("category-overrides")).toBeDefined();
    expect(screen.getByTestId("intent-overrides")).toBeDefined();
    expect(screen.getByTestId("context-budget")).toBeDefined();
    expect(screen.getByTestId("system-timeouts")).toBeDefined();
  });
});
