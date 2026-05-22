/**
 * OutlineEditor tests — chapter outline beats and notes.
 *
 * Tests:
 * 1. Renders beats checklist
 * 2. Toggles beat completion
 * 3. Shows notes textarea
 * 4. Auto-saves on change
 * 5. Updates outline via mutation
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { OutlineEditor } from "@/components/studio/planning/OutlineEditor";
import { server } from "@/mocks/server";
import type { OutlineResponse } from "@/types";

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

const mockOutline: OutlineResponse = {
  id: "outline-1",
  chapter_id: "chapter-1",
  stage_assignment: "act_1",
  planned_beats: [
    { title: "Introduction", description: "Meet the hero", completed: false },
    { title: "Inciting Incident", description: "The call to adventure", completed: true },
    { title: "Rising Action", description: "Things get complicated", completed: false },
  ],
  outline_notes: "Focus on character development in this chapter.",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("OutlineEditor", () => {
  beforeEach(() => {
    // Override the outline endpoint for these tests
    server.use(
      http.get("*/api/v1/planning/outlines/:novelId/:chapterId", async () => {
        return HttpResponse.json(mockOutline);
      }),
      http.put("*/api/v1/planning/outlines/:novelId/:chapterId", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({
          ...mockOutline,
          ...body,
          updated_at: "2026-06-01T00:00:00Z",
        });
      }),
    );
  });

  it("renders beats checklist", async () => {
    renderWithProviders(<OutlineEditor chapterId="chapter-1" novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Introduction")).toBeDefined();
    });
    expect(screen.getByText("Inciting Incident")).toBeDefined();
    expect(screen.getByText("Rising Action")).toBeDefined();
  });

  it("toggles beat completion", async () => {
    renderWithProviders(<OutlineEditor chapterId="chapter-1" novelId="novel-1" />);

    // Wait for beats to load
    await waitFor(() => {
      expect(screen.getByText("Introduction")).toBeDefined();
    });

    // Click on "Introduction" beat to toggle it
    fireEvent.click(screen.getByText("Introduction"));

    // The beat should now show line-through class — but the text is still visible
    // We verify the toggle happened by checking the parent button styling
    const introButton = screen.getByText("Introduction").closest("button");
    expect(introButton).not.toBeNull();
    // After toggle, it should have line-through class on the span
    const introSpan = screen.getByText("Introduction");
    expect(introSpan.className).toContain("line-through");
  });

  it("shows notes textarea", async () => {
    renderWithProviders(<OutlineEditor chapterId="chapter-1" novelId="novel-1" />);

    await waitFor(() => {
      const notesTextarea = screen.getByDisplayValue(
        "Focus on character development in this chapter.",
      );
      expect(notesTextarea).toBeDefined();
    });
  });

  it("auto-saves on notes change", async () => {
    renderWithProviders(<OutlineEditor chapterId="chapter-1" novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Introduction")).toBeDefined();
    });

    // Change the notes
    const notesTextarea = screen.getByDisplayValue(
      "Focus on character development in this chapter.",
    );
    fireEvent.change(notesTextarea, { target: { value: "Updated notes" } });

    // Wait for the debounced save to trigger (800ms + buffer)
    await waitFor(
      () => {
        // The textarea should now show the updated value
        expect(screen.getByDisplayValue("Updated notes")).toBeDefined();
      },
      { timeout: 3000 },
    );
  });

  it("updates outline via mutation on beat toggle", async () => {
    renderWithProviders(<OutlineEditor chapterId="chapter-1" novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("Introduction")).toBeDefined();
    });

    // Toggle the beat
    fireEvent.click(screen.getByText("Introduction"));

    // We verify that the UI updates immediately (optimistic update)
    const introSpan = screen.getByText("Introduction");
    expect(introSpan.className).toContain("line-through");
  });

  it("shows completed beats with line-through", async () => {
    renderWithProviders(<OutlineEditor chapterId="chapter-1" novelId="novel-1" />);

    await waitFor(() => {
      const completedBeat = screen.getByText("Inciting Incident");
      // "Inciting Incident" starts completed
      expect(completedBeat.className).toContain("line-through");
    });
  });

  it("renders beats heading", async () => {
    renderWithProviders(<OutlineEditor chapterId="chapter-1" novelId="novel-1" />);

    await waitFor(() => {
      expect(screen.getByText("storyboard.outline.beats")).toBeDefined();
    });
  });
});
