import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IntentOverrides } from "@/components/studio/settings/IntentOverrides";
import type { ModelOverride, UserProvider } from "@/types";

// --- Mock data ---

const mockProviders: UserProvider[] = [
  {
    id: "p1",
    provider_name: "OpenAI",
    has_api_key: true,
    api_key_last4: "abcd",
    base_url: null,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "p2",
    provider_name: "Anthropic",
    has_api_key: true,
    api_key_last4: "efgh",
    base_url: null,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

const mockModelOptions: Record<string, { value: string; label: string }[]> = {
  p1: [
    { value: "gpt-4", label: "GPT-4" },
    { value: "gpt-3.5", label: "GPT-3.5" },
  ],
};

const emptyOverrides: Record<string, ModelOverride> = {};

const sampleOverrides: Record<string, ModelOverride> = {
  WRITE: { provider_id: "p1", model_id: "gpt-4" },
};

// --- Tests ---

describe("IntentOverrides", () => {
  it("initially shows collapsed state with advanced button", () => {
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={{}}
      />,
    );
    expect(screen.getByText("settings.ai.intentOverrides.advanced")).toBeDefined();
  });

  it("expands to show categories when advanced is clicked", () => {
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={{}}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    // Writing category should be open by default, others collapsed
    expect(screen.getByText("settings.ai.categories.writing")).toBeDefined();
    expect(screen.getByText("settings.ai.categories.analysis")).toBeDefined();
  });

  it("shows intents for open categories", () => {
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={{}}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    // Writing intents should be visible (writing is open by default)
    expect(screen.getByText("settings.ai.intents.write")).toBeDefined();
    expect(screen.getByText("settings.ai.intents.extend")).toBeDefined();
    expect(screen.getByText("settings.ai.intents.rewrite")).toBeDefined();
    expect(screen.getByText("settings.ai.intents.coAuthor")).toBeDefined();
  });

  it("toggles category open/close on click", () => {
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={{}}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    // Click writing category to close it
    fireEvent.click(screen.getByText("settings.ai.categories.writing"));
    expect(screen.queryByText("settings.ai.intents.write")).toBeNull();
  });

  it("calls onChange when toggling an intent on", () => {
    const onChange = vi.fn();
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={onChange}
        modelOptions={{}}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    // Find the toggle switch for WRITE intent
    const switches = screen.getAllByRole("switch");
    expect(switches.length).toBeGreaterThanOrEqual(1);
    fireEvent.click(switches[0]);

    // Should create override with first active provider
    expect(onChange).toHaveBeenCalledWith({
      WRITE: { provider_id: "p1", model_id: "" },
    });
  });

  it("calls onChange when toggling an intent off", () => {
    const onChange = vi.fn();
    render(
      <IntentOverrides
        overrides={sampleOverrides}
        providers={mockProviders}
        onChange={onChange}
        modelOptions={mockModelOptions}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    // Find the WRITE intent switch (should be on)
    const switches = screen.getAllByRole("switch");
    fireEvent.click(switches[0]);

    // Should remove the override
    expect(onChange).toHaveBeenCalledWith({});
  });

  it("shows collapse button when expanded", () => {
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={{}}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    expect(screen.getByText("settings.ai.intentOverrides.collapse")).toBeDefined();
  });

  it("collapses panel when collapse button is clicked", () => {
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={{}}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.collapse"));

    // Should show advanced button again
    expect(screen.getByText("settings.ai.intentOverrides.advanced")).toBeDefined();
  });

  it("renders all 7 category sections when expanded", () => {
    render(
      <IntentOverrides
        overrides={emptyOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={{}}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    const categoryKeys = [
      "settings.ai.categories.writing",
      "settings.ai.categories.analysis",
      "settings.ai.categories.knowledgeBase",
      "settings.ai.categories.planning",
      "settings.ai.categories.extraction",
      "settings.ai.categories.chat",
      "settings.ai.categories.research",
    ];
    for (const key of categoryKeys) {
      expect(screen.getByText(key)).toBeDefined();
    }
  });

  it("shows provider select for active override with model options", () => {
    render(
      <IntentOverrides
        overrides={sampleOverrides}
        providers={mockProviders}
        onChange={vi.fn()}
        modelOptions={mockModelOptions}
      />,
    );
    fireEvent.click(screen.getByText("settings.ai.intentOverrides.advanced"));

    // Provider and model selects should be visible for active override
    expect(
      screen.getByLabelText("settings.ai.intentOverrides.provider", { exact: false }),
    ).toBeDefined();
    expect(
      screen.getByLabelText("settings.ai.intentOverrides.model", { exact: false }),
    ).toBeDefined();
  });
});
