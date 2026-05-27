/**
 * DefaultModelSection tests — provider/model selector in settings.
 *
 * Tests:
 * 1. Renders section title
 * 2. Renders provider select with options
 * 3. Renders model select
 * 4. Calls onProviderChange when provider changed
 * 5. Shows loading spinner when modelsLoading
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DefaultModelSection } from "@/components/studio/settings/DefaultModelSection";
import type { UserAiSettings, UserProvider } from "@/types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockProviders: UserProvider[] = [
  {
    id: "prov-1",
    provider_name: "OpenAI",
    has_api_key: true,
    api_key_last4: "abcd",
    base_url: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: "prov-2",
    provider_name: "Anthropic",
    has_api_key: true,
    api_key_last4: "efgh",
    base_url: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

const defaultAiSettings: UserAiSettings = {
  user_id: "user-1",
  default_provider_id: "prov-1",
  default_model: "gpt-4",
  category_overrides: {},
  intent_overrides: {},
  updated_at: "2026-01-01T00:00:00Z",
};

const defaultProps = {
  aiSettings: defaultAiSettings,
  providers: mockProviders,
  modelsData: {
    models: [
      { id: "gpt-4", name: "GPT-4" },
      { id: "gpt-3.5-turbo", name: "GPT-3.5 Turbo" },
    ],
  },
  modelsLoading: false,
  onProviderChange: vi.fn(),
  onModelChange: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("DefaultModelSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders section title", () => {
    render(<DefaultModelSection {...defaultProps} />);

    // "settings.ai.defaultModel" appears both as h3 heading and model label
    const headings = screen.getAllByText("settings.ai.defaultModel");
    expect(headings.length).toBeGreaterThanOrEqual(1);
  });

  it("renders provider label", () => {
    render(<DefaultModelSection {...defaultProps} />);

    expect(screen.getByText("settings.ai.providerName")).toBeDefined();
  });

  it("renders provider select with options", () => {
    render(<DefaultModelSection {...defaultProps} />);

    expect(screen.getByText("OpenAI")).toBeDefined();
    expect(screen.getByText("Anthropic")).toBeDefined();
  });

  it("renders model select with options", () => {
    render(<DefaultModelSection {...defaultProps} />);

    expect(screen.getByText("GPT-4")).toBeDefined();
    expect(screen.getByText("GPT-3.5 Turbo")).toBeDefined();
  });

  it("calls onProviderChange when provider changed", () => {
    const onProviderChange = vi.fn();
    render(<DefaultModelSection {...defaultProps} onProviderChange={onProviderChange} />);

    const select = screen.getByDisplayValue("OpenAI").closest("select")!;
    fireEvent.change(select, { target: { value: "prov-2" } });

    expect(onProviderChange).toHaveBeenCalledWith("prov-2");
  });

  it("calls onModelChange when model changed", () => {
    const onModelChange = vi.fn();
    render(<DefaultModelSection {...defaultProps} onModelChange={onModelChange} />);

    const selects = screen.getAllByRole("combobox");
    const modelSelect = selects[1]; // second select is the model selector
    fireEvent.change(modelSelect, { target: { value: "gpt-3.5-turbo" } });

    expect(onModelChange).toHaveBeenCalledWith("gpt-3.5-turbo");
  });

  it("shows loading spinner when modelsLoading", () => {
    render(<DefaultModelSection {...defaultProps} modelsLoading />);

    // The spinner replaces the model select — verify no model options visible
    expect(screen.queryByText("GPT-4")).toBeNull();
  });

  it("renders none-selected option when no provider", () => {
    render(
      <DefaultModelSection
        {...defaultProps}
        aiSettings={{ ...defaultAiSettings, default_provider_id: "", default_model: "" }}
      />,
    );

    expect(screen.getByText("settings.ai.noneSelected")).toBeDefined();
  });
});
