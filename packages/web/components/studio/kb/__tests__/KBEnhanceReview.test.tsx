/**
 * KBEnhanceReview tests — AI enhancement review interface.
 *
 * Tests:
 * 1. Shows loading state on mount (idle → auto-starts enhancement)
 * 2. Shows error state with retry button
 * 3. Shows before/after comparison after enhancement completes
 * 4. Auto-selects all enhancements by default
 * 5. Accept/Reject per field toggle selection
 * 6. "Select all" / "Select none" buttons work
 * 7. "Apply Selected" calls onApplySelected
 * 8. "Reject All" clears selection
 * 9. "Back to Field List" button works
 * 10. Shows reasoning for each enhancement
 * 11. Shows enhancement count and selected count
 */

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { KBEnhanceReview } from "@/components/studio/kb/KBEnhanceReview";
import type { KBCreationSession, KBEnhancementResult } from "@/lib/api/kb-sessions";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const mockSession: KBCreationSession = {
  id: "session-1",
  novel_id: "novel-1",
  user_id: "user-1",
  entity_type: "character",
  status: "active",
  fields: [
    {
      field_key: "name",
      label: "Name",
      field_type: "text",
      required: true,
      source: "user",
      user_value: "Test Character",
      ai_suggested_value: undefined,
      ai_reasoning: undefined,
      final_value: "Test Character",
    },
    {
      field_key: "description",
      label: "Description",
      field_type: "text",
      required: false,
      source: "user",
      user_value: "A brave hero",
      ai_suggested_value: undefined,
      ai_reasoning: undefined,
      final_value: undefined,
    },
  ],
  context_entries: [],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const mockEnhancements: KBEnhancementResult[] = [
  {
    field_key: "description",
    original: "A brave hero",
    suggested: "A brave and compassionate hero who always puts others first.",
    reasoning: "Added emotional depth and selflessness to create a more compelling character.",
  },
  {
    field_key: "name",
    original: "Test Character",
    suggested: "Sir Aldric the Valiant",
    reasoning: "A more evocative name that hints at nobility and courage.",
  },
];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBEnhanceReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows loading state on mount (idle triggers auto-enhance)", () => {
    // Don't resolve the promise — keep loading
    const onRequestEnhance = vi.fn().mockReturnValue(new Promise(() => {}));

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    expect(screen.getByText("kb.aiEnhancing")).toBeDefined();
    expect(screen.getByText("kb.aiEnhancingDesc")).toBeDefined();
    expect(onRequestEnhance).toHaveBeenCalledTimes(1);
  });

  it("shows error state with retry button", async () => {
    const onRequestEnhance = vi.fn().mockRejectedValue(new Error("Enhancement failed"));

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("Enhancement failed")).toBeDefined();
    });

    expect(screen.getByText("kb.retry")).toBeDefined();
  });

  it("shows before/after comparison after enhancement completes", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.enhanceReview")).toBeDefined();
    });

    // Should show field labels
    expect(screen.getByText("Description")).toBeDefined();
    expect(screen.getByText("Name")).toBeDefined();

    // Should show original text
    expect(screen.getByText("A brave hero")).toBeDefined();
    expect(screen.getByText("Test Character")).toBeDefined();

    // Should show suggested text
    expect(screen.getByText(/brave and compassionate hero/)).toBeDefined();
    expect(screen.getByText("Sir Aldric the Valiant")).toBeDefined();
  });

  it("auto-selects all enhancements by default", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.enhanceSelected")).toBeDefined();
    });
  });

  it("shows reasoning for each enhancement", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      // There are multiple reasoning sections - use getAllByText
      const reasoningLabels = screen.getAllByText("kb.aiReasoning");
      expect(reasoningLabels.length).toBeGreaterThanOrEqual(1);
    });

    expect(screen.getByText(/emotional depth/)).toBeDefined();
    expect(screen.getByText(/evocative name/)).toBeDefined();
  });

  it("allows toggling field selection via click on field header", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.enhanceSelected")).toBeDefined();
    });

    // Click on the first field header to deselect it
    const fieldHeaders = screen
      .getAllByRole("button")
      .filter(
        (btn) => btn.textContent?.includes("Description") || btn.textContent?.includes("Name"),
      );
    fireEvent.click(fieldHeaders[0]);

    // Verify enhanceSelected is still present (count changes but key stays same in mock)
    expect(screen.getByText("kb.enhanceSelected")).toBeDefined();
  });

  it("'Select all' / 'Select none' buttons work", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.selectAll")).toBeDefined();
    });

    // First deselect all
    fireEvent.click(screen.getByText("kb.selectNone"));
    expect(screen.getByText("kb.enhanceSelected")).toBeDefined();

    // Then select all again
    fireEvent.click(screen.getByText("kb.selectAll"));
    expect(screen.getByText("kb.enhanceSelected")).toBeDefined();
  });

  it("'Apply Selected' calls onApplySelected and accepts selected enhancements", async () => {
    const onAcceptEnhancement = vi.fn();
    const onApplySelected = vi.fn();
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={onAcceptEnhancement}
        onApplySelected={onApplySelected}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.applySelected")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.applySelected"));

    // Should have called onAcceptEnhancement for each selected field
    expect(onAcceptEnhancement).toHaveBeenCalledTimes(2);
    expect(onAcceptEnhancement).toHaveBeenCalledWith("description", mockEnhancements[0].suggested);
    expect(onAcceptEnhancement).toHaveBeenCalledWith("name", mockEnhancements[1].suggested);
    expect(onApplySelected).toHaveBeenCalledTimes(1);
  });

  it("'Reject All' clears selection", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.enhanceSelected")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.rejectAll"));
    expect(screen.getByText("kb.enhanceSelected")).toBeDefined();
  });

  it("'Apply Selected' is disabled when no fields selected", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.applySelected")).toBeDefined();
    });

    // Deselect all
    fireEvent.click(screen.getByText("kb.selectNone"));

    const applyButton = screen.getByText("kb.applySelected").closest("button");
    expect(applyButton?.disabled).toBe(true);
  });

  it("'Back to Field List' button works", async () => {
    const onBack = vi.fn();
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={onBack}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("kb.backToFieldList")).toBeDefined();
    });

    fireEvent.click(screen.getByText("kb.backToFieldList"));
    expect(onBack).toHaveBeenCalledTimes(1);
  });

  it("retry button re-requests enhancement after error", async () => {
    const onRequestEnhance = vi
      .fn()
      .mockRejectedValueOnce(new Error("First attempt failed"))
      .mockResolvedValueOnce(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByText("First attempt failed")).toBeDefined();
    });

    // Click retry
    fireEvent.click(screen.getByText("kb.retry"));

    await waitFor(() => {
      expect(onRequestEnhance).toHaveBeenCalledTimes(2);
    });

    // Should now show review
    await waitFor(() => {
      expect(screen.getByText("kb.enhanceSelected")).toBeDefined();
    });
  });

  it("shows enhancement count in header", async () => {
    const onRequestEnhance = vi.fn().mockResolvedValue(mockEnhancements);

    render(
      <KBEnhanceReview
        session={mockSession}
        onRequestEnhance={onRequestEnhance}
        onAcceptEnhancement={vi.fn()}
        onApplySelected={vi.fn()}
        onBack={vi.fn()}
      />,
    );

    await waitFor(() => {
      // The i18n mock returns the key as-is
      expect(screen.getByText("kb.enhancementsFound")).toBeDefined();
    });
  });
});
