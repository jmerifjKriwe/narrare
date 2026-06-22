/**
 * EnhanceReviewCard rating tests — KB enhance rating adoption (CR-AUFG-07-24 Task 9).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { EnhanceReviewCard } from "@/components/studio/kb/_components/EnhanceReviewCard";
import type { KBEnhancementResult } from "@/lib/api/kb-sessions";
import { server } from "@/mocks/server";

const enhancement: KBEnhancementResult = {
  field_key: "role",
  original: "Mentor",
  suggested: "Wise mentor",
  reasoning: "more evocative",
};

function renderWithQueryClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("EnhanceReviewCard rating (CR-AUFG-07-24)", () => {
  it("renders AIRating when projectId is supplied", () => {
    renderWithQueryClient(
      <EnhanceReviewCard
        enhancement={enhancement}
        isSelected={true}
        onToggle={vi.fn()}
        onAccept={vi.fn()}
        onReject={vi.fn()}
        fieldLabel="Role"
        projectId="proj-1"
        t={(key: string) => key}
      />,
    );

    expect(screen.getByRole("radiogroup", { name: "aiActions.rating" })).toBeDefined();
  });

  it("posts kb_enhance_field rating without blocking accept", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    const onAccept = vi.fn();
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" });
      }),
    );

    renderWithQueryClient(
      <EnhanceReviewCard
        enhancement={enhancement}
        isSelected={true}
        onToggle={vi.fn()}
        onAccept={onAccept}
        onReject={vi.fn()}
        fieldLabel="Role"
        projectId="proj-1"
        t={(key: string) => key}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "aiActions.accept" }));
    expect(onAccept).toHaveBeenCalledWith("role");

    fireEvent.click(screen.getAllByRole("radio")[3]);
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));

    await waitFor(() => {
      expect(capturedBody).toMatchObject({
        source_type: "kb_enhance_field",
        source_id: "role",
        rating: 4,
        project_id: "proj-1",
      });
    });
    // CR-AUFG-07-24: non-UUID surface id must not be forwarded as suggestion_id
    expect(capturedBody).not.toHaveProperty("suggestion_id");
  });
});
