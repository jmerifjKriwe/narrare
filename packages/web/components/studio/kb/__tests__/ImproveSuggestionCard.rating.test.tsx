/**
 * ImproveSuggestionCard rating tests — KB improve rating adoption (CR-AUFG-07-24 Task 10).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { ImproveSuggestionCard } from "@/components/studio/kb/_components/ImproveSuggestionCard";
import type { ImproveSuggestion } from "@/lib/api/kb-improve";
import { server } from "@/mocks/server";

const suggestion: ImproveSuggestion = {
  suggestion_id: 12,
  type: "expand",
  target: "backstory",
  description: "Add a motivation for the antagonist.",
  proposed_content: "She wants revenge.",
  confidence: 0.82,
  reasoning: "current text lacks stakes",
  related_entity_id: null,
  related_entity_name: null,
};

function renderWithQueryClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("ImproveSuggestionCard rating (CR-AUFG-07-24)", () => {
  it("renders AIRating when projectId is supplied", () => {
    renderWithQueryClient(
      <ImproveSuggestionCard
        suggestion={suggestion}
        isSelected={true}
        onToggle={vi.fn()}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        projectId="proj-1"
      />,
    );

    expect(screen.getByRole("radiogroup", { name: "aiActions.rating" })).toBeDefined();
  });

  it("posts kb_improve_suggestion rating without blocking reject", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    const onReject = vi.fn();
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "evt-1", action: "reject", created_at: "x" });
      }),
    );

    renderWithQueryClient(
      <ImproveSuggestionCard
        suggestion={suggestion}
        isSelected={false}
        onToggle={vi.fn()}
        onAccept={vi.fn()}
        onReject={onReject}
        projectId="proj-1"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "aiActions.reject" }));
    expect(onReject).toHaveBeenCalledWith(12);

    fireEvent.click(screen.getAllByRole("radio")[4]);
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));

    await waitFor(() => {
      expect(capturedBody).toMatchObject({
        source_type: "kb_improve_suggestion",
        source_id: "12",
        rating: 5,
        project_id: "proj-1",
      });
    });
    // CR-AUFG-07-24: non-UUID surface id must not be forwarded as suggestion_id
    expect(capturedBody).not.toHaveProperty("suggestion_id");
  });
});
