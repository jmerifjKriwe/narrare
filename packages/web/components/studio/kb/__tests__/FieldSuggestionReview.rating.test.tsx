/**
 * FieldSuggestionReview rating tests — KB field-suggest rating adoption (CR-AUFG-07-24 Task 11).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { FieldSuggestionReview } from "@/components/studio/kb/_components/FieldSuggestionReview";
import type { KBCreationField } from "@/lib/api/kb-sessions";
import { server } from "@/mocks/server";

const field: KBCreationField = {
  field_key: "personality",
  label: "Personality",
  field_type: "text",
  required: false,
  source: "ai",
  ai_suggested_value: "Brave and cunning",
  ai_reasoning: "adds depth",
  user_value: undefined,
  final_value: undefined,
};

function renderWithQueryClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("FieldSuggestionReview rating (CR-AUFG-07-24)", () => {
  it("renders AIRating after the user accepts a stable suggestion", () => {
    renderWithQueryClient(
      <FieldSuggestionReview
        field={field}
        projectId="proj-1"
        onAcceptSuggestion={vi.fn()}
        onRejectSuggestion={vi.fn()}
      />,
    );

    expect(screen.queryByRole("radiogroup", { name: "aiActions.rating" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "aiActions.accept" }));

    expect(screen.getByRole("radiogroup", { name: "aiActions.rating" })).toBeDefined();
  });

  it("posts kb_field_suggest rating without blocking accept", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    const onAccept = vi.fn();
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" });
      }),
    );

    renderWithQueryClient(
      <FieldSuggestionReview
        field={field}
        projectId="proj-1"
        onAcceptSuggestion={onAccept}
        onRejectSuggestion={vi.fn()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "aiActions.accept" }));
    expect(onAccept).toHaveBeenCalledWith("personality", "Brave and cunning");

    fireEvent.click(screen.getAllByRole("radio")[2]);
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));

    await waitFor(() => {
      expect(capturedBody).toMatchObject({
        source_type: "kb_field_suggest",
        source_id: "personality",
        rating: 3,
        project_id: "proj-1",
      });
    });
    // CR-AUFG-07-24: non-UUID surface id must not be forwarded as suggestion_id
    expect(capturedBody).not.toHaveProperty("suggestion_id");
  });
});
