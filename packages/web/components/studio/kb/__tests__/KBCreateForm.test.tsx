/**
 * KBCreateForm tests — KB entry creation form.
 *
 * Tests:
 * 1. Renders entity type selector
 * 2. Pre-selects active type
 * 3. Shows name input
 * 4. Creates entry on submit
 * 5. Validates required fields
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBCreateForm } from "@/components/studio/kb/KBCreateForm";

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
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  novelId: "novel-1",
  onCancel: vi.fn(),
  onCreated: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBCreateForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders entity type selector", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} />);
    expect(screen.getByLabelText("kb.selectType")).toBeDefined();
  });

  it("pre-selects active type when initialEntityType is provided", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} initialEntityType="location" />);
    const select = screen.getByLabelText("kb.selectType") as HTMLSelectElement;
    expect(select.value).toBe("location");
  });

  it("defaults to character type when no initialEntityType", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} />);
    const select = screen.getByLabelText("kb.selectType") as HTMLSelectElement;
    expect(select.value).toBe("character");
  });

  it("shows name input", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} />);
    expect(screen.getByLabelText("worldbuilding.name")).toBeDefined();
  });

  it("creates entry on submit", async () => {
    const onCreated = vi.fn();
    renderWithProviders(<KBCreateForm {...defaultProps} onCreated={onCreated} />);

    // Fill in the name
    const nameInput = screen.getByPlaceholderText("kb.namePlaceholder");
    fireEvent.change(nameInput, { target: { value: "New Character" } });

    // Click create button
    fireEvent.click(screen.getByText("kb.create"));

    // Wait for MSW handler to respond and onCreated callback
    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith("kb-entry-new");
    });
  });

  it("validates required fields — create button disabled when name is empty", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} />);
    const createButton = screen.getByText("kb.create").closest("button");
    expect(createButton).not.toBeNull();
    expect(createButton!.disabled).toBe(true);
  });

  it("enables create button when name is provided", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} />);
    const nameInput = screen.getByPlaceholderText("kb.namePlaceholder");
    fireEvent.change(nameInput, { target: { value: "My Character" } });
    const createButton = screen.getByText("kb.create").closest("button");
    expect(createButton!.disabled).toBe(false);
  });

  it("renders cancel button", () => {
    const onCancel = vi.fn();
    renderWithProviders(<KBCreateForm {...defaultProps} onCancel={onCancel} />);
    fireEvent.click(screen.getByText("kb.cancel"));
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("renders body textarea", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} />);
    expect(screen.getByPlaceholderText("kb.bodyPlaceholder")).toBeDefined();
  });

  it("renders tags input", () => {
    renderWithProviders(<KBCreateForm {...defaultProps} />);
    expect(screen.getByPlaceholderText("kb.tagsPlaceholder")).toBeDefined();
  });
});
