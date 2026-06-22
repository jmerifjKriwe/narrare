/**
 * ChangeReview rating tests — Co-Author rating adoption (CR-AUFG-07-24 Task 8).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import type { ChangeDetail } from "@/lib/api/coauthor";
import { server } from "@/mocks/server";
import { ChangeReview } from "../ChangeReview";

const change: ChangeDetail = {
  id: "change-7",
  index: 6,
  original_text: "He ran fast.",
  revised_text: "He sprinted.",
  change_type: "rephrase",
};

function renderWithQueryClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

describe("ChangeReview rating (CR-AUFG-07-24)", () => {
  it("renders AIRating for a stable accepted Co-Author change", () => {
    renderWithQueryClient(
      <ChangeReview
        change={change}
        isAccepted={true}
        onToggle={vi.fn()}
        projectId="proj-1"
        chapterId="ch-1"
      />,
    );

    expect(screen.getByRole("radiogroup", { name: "aiActions.rating" })).toBeDefined();
  });

  it("does not render AIRating for legacy callers without projectId", () => {
    render(<ChangeReview change={change} isAccepted={true} onToggle={vi.fn()} />);

    expect(screen.queryByRole("radiogroup", { name: "aiActions.rating" })).toBeNull();
  });

  it("posts co_author_change rating without blocking the toggle action", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    const onToggle = vi.fn();
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" });
      }),
    );

    renderWithQueryClient(
      <ChangeReview
        change={change}
        isAccepted={true}
        onToggle={onToggle}
        projectId="proj-1"
        chapterId="ch-1"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "aiDiff.rejectChange" }));
    expect(onToggle).toHaveBeenCalledWith("change-7");

    fireEvent.click(screen.getAllByRole("radio")[4]);
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));

    await waitFor(() => {
      expect(capturedBody).toMatchObject({
        source_type: "co_author_change",
        source_id: "change-7",
        rating: 5,
        project_id: "proj-1",
        chapter_id: "ch-1",
      });
    });
    // CR-AUFG-07-24: non-UUID surface id must not be forwarded as suggestion_id
    expect(capturedBody).not.toHaveProperty("suggestion_id");
  });
});
