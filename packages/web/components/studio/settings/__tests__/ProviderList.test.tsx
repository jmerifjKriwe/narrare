import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ProviderList } from "@/components/studio/settings/ProviderList";
import type { UserProvider } from "@/types";

// --- Mock react-query ---

vi.mock("@tanstack/react-query", () => ({
  useMutation: vi.fn(() => ({ mutate: vi.fn(), isPending: false })),
  useQueryClient: vi.fn(() => ({ invalidateQueries: vi.fn() })),
}));

// --- Mock data ---

const mockProviders: UserProvider[] = [
  {
    id: "prov-1",
    provider_name: "OpenAI",
    has_api_key: true,
    api_key_last4: "abcd",
    base_url: null,
    is_active: true,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
  {
    id: "prov-2",
    provider_name: "Anthropic",
    has_api_key: false,
    api_key_last4: "efgh",
    base_url: null,
    is_active: false,
    created_at: "2024-01-01T00:00:00Z",
    updated_at: "2024-01-01T00:00:00Z",
  },
];

// --- Tests ---

describe("ProviderList", () => {
  it("renders section title from translation", () => {
    render(<ProviderList providers={mockProviders} isLoading={false} />);
    expect(screen.getByText("settings.ai.provider")).toBeDefined();
    expect(screen.getByText("settings.ai.providerDescription")).toBeDefined();
  });

  it("renders provider names", () => {
    render(<ProviderList providers={mockProviders} isLoading={false} />);
    expect(screen.getByText("OpenAI")).toBeDefined();
    expect(screen.getByText("Anthropic")).toBeDefined();
  });

  it("shows add provider button", () => {
    render(<ProviderList providers={mockProviders} isLoading={false} />);
    expect(screen.getByText("settings.ai.addProvider")).toBeDefined();
  });

  it("shows edit buttons for each provider", () => {
    render(<ProviderList providers={mockProviders} isLoading={false} />);
    const editBtns = screen.getAllByText("settings.ai.editApiKey");
    expect(editBtns).toHaveLength(2);
  });

  it("shows masked api key for providers with has_api_key", () => {
    render(<ProviderList providers={mockProviders} isLoading={false} />);
    expect(screen.getByText("••••abcd")).toBeDefined();
  });

  it("shows ProviderForm when add button is clicked", () => {
    render(<ProviderList providers={mockProviders} isLoading={false} />);
    const addBtn = screen.getByText("settings.ai.addProvider");
    fireEvent.click(addBtn);
    // ProviderForm renders the provider name select and api key input
    expect(screen.getByLabelText("settings.ai.providerName", { exact: false })).toBeDefined();
    expect(screen.getByLabelText("settings.ai.apiKey", { exact: false })).toBeDefined();
    expect(screen.getByLabelText("settings.ai.baseUrl", { exact: false })).toBeDefined();
  });

  it("shows empty state when no providers", () => {
    render(<ProviderList providers={[]} isLoading={false} />);
    expect(screen.getByText("settings.ai.noProviders")).toBeDefined();
    expect(screen.getByText("settings.ai.noProvidersDescription")).toBeDefined();
  });

  it("still shows add provider button in empty state", () => {
    render(<ProviderList providers={[]} isLoading={false} />);
    expect(screen.getByText("settings.ai.addProvider")).toBeDefined();
  });

  it("opens ProviderForm when add button is clicked in empty state", () => {
    render(<ProviderList providers={[]} isLoading={false} />);
    const addBtn = screen.getByText("settings.ai.addProvider");
    fireEvent.click(addBtn);
    expect(screen.getByLabelText("settings.ai.providerName", { exact: false })).toBeDefined();
  });
});
