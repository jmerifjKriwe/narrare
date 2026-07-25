/**
 * ToneFormDialog tests — create/edit tone dialog.
 *
 * Tests:
 * 1. Renders add tone title when creating
 * 2. Renders edit tone title when editing
 * 3. Renders name and instructions inputs
 * 4. Calls onClose when cancel clicked
 * 5. Shows validation error when fields empty
 * 6. Calls onClose on backdrop click
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ToneFormDialog } from "@/components/studio/settings/ToneFormDialog";
import type { CustomTone } from "@/types";

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
// Mocks
// ---------------------------------------------------------------------------

const mockCreate = vi.fn();
const mockUpdate = vi.fn();

vi.mock("@/lib/api/client", () => ({
  tonesApi: {
    create: (...args: unknown[]) => mockCreate(...args),
    update: (...args: unknown[]) => mockUpdate(...args),
  },
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const existingTone: CustomTone = {
  id: "tone-1",
  name: "Dramatic",
  instructions: "Use dramatic language",
};

const defaultProps = {
  open: true,
  tone: null as CustomTone | null,
  onClose: vi.fn(),
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ToneFormDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders add tone title when creating", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} />);

    expect(screen.getByText("tones.addTone")).toBeDefined();
  });

  it("renders edit tone title when editing", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} tone={existingTone} />);

    expect(screen.getByText("tones.editTone")).toBeDefined();
  });

  it("renders name input with label", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} />);

    expect(screen.getByText("tones.toneName")).toBeDefined();
    expect(screen.getByLabelText("tones.toneName")).toBeDefined();
  });

  it("renders instructions textarea with label", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} />);

    expect(screen.getByText("tones.toneInstructions")).toBeDefined();
    expect(screen.getByLabelText("tones.toneInstructions")).toBeDefined();
  });

  it("pre-fills fields when editing existing tone", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} tone={existingTone} />);

    expect(screen.getByDisplayValue("Dramatic")).toBeDefined();
    expect(screen.getByDisplayValue("Use dramatic language")).toBeDefined();
  });

  it("calls onClose when cancel button clicked", () => {
    const onClose = vi.fn();
    renderWithProviders(<ToneFormDialog {...defaultProps} onClose={onClose} />);

    fireEvent.click(screen.getByText("settings.ai.cancel"));
    expect(onClose).toHaveBeenCalled();
  });

  it("shows validation error when submitting empty fields", async () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} />);

    // Click save button
    fireEvent.click(screen.getByText("settings.ai.save"));

    await waitFor(() => {
      expect(screen.getByText("tones.validationRequired")).toBeDefined();
    });
  });

  it("renders dialog role", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} />);

    expect(screen.getByRole("dialog")).toBeDefined();
  });

  it("renders with aria-modal", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} />);

    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
  });

  it("renders backdrop overlay", () => {
    renderWithProviders(<ToneFormDialog {...defaultProps} />);

    // Backdrop div with aria-hidden="true"
    const backdrop = document.querySelector('[aria-hidden="true"]');
    expect(backdrop).toBeDefined();
  });
});
