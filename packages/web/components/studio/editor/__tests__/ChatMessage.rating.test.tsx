/**
 * ChatMessage rating tests — completed assistant prose rating adoption (CR-AUFG-07-24 Task 12).
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import type { ReactElement } from "react";
import { describe, expect, it, vi } from "vitest";
import { ChatMessage, type Message } from "@/components/studio/editor/ChatMessage";
import { server } from "@/mocks/server";

const message: Message = {
  id: "msg-42",
  role: "assistant",
  content: "Here you go.",
  prose: "A polished paragraph.",
};

function renderWithQueryClient(ui: ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

function renderChatMessage(overrides: Partial<Message> = {}, props?: { isStreaming?: boolean }) {
  return renderWithQueryClient(
    <ChatMessage
      message={{ ...message, ...overrides }}
      isAdded={false}
      onAddToDraft={vi.fn()}
      aiDraftBadge="sessionPanel.aiDraftBadge"
      addToDraftLabel="aiActions.addToDraft"
      addedToDraftLabel="sessionPanel.addedToDraft"
      projectId="proj-1"
      isStreaming={props?.isStreaming ?? false}
    />,
  );
}

describe("ChatMessage rating (CR-AUFG-07-24)", () => {
  it("renders AIRating for a completed assistant prose message", () => {
    renderChatMessage();

    expect(screen.getByRole("radiogroup", { name: "aiActions.rating" })).toBeDefined();
  });

  it("does not render AIRating for streaming assistant chunks", () => {
    renderChatMessage({}, { isStreaming: true });

    expect(screen.queryByRole("radiogroup", { name: "aiActions.rating" })).toBeNull();
  });

  it("does not render AIRating without prose or projectId", () => {
    renderWithQueryClient(
      <ChatMessage
        message={{ id: "msg-43", role: "assistant", content: "Only chat text" }}
        isAdded={false}
        onAddToDraft={vi.fn()}
        aiDraftBadge="sessionPanel.aiDraftBadge"
        addToDraftLabel="aiActions.addToDraft"
        addedToDraftLabel="sessionPanel.addedToDraft"
      />,
    );

    expect(screen.queryByRole("radiogroup", { name: "aiActions.rating" })).toBeNull();
  });

  it("posts chat_message rating without blocking add-to-draft", async () => {
    let capturedBody: Record<string, unknown> | null = null;
    const onAddToDraft = vi.fn();
    server.use(
      http.post("*/api/v1/memory/feedback", async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ id: "evt-1", action: "accept", created_at: "x" });
      }),
    );

    renderWithQueryClient(
      <ChatMessage
        message={message}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge="sessionPanel.aiDraftBadge"
        addToDraftLabel="aiActions.addToDraft"
        addedToDraftLabel="sessionPanel.addedToDraft"
        projectId="proj-1"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "aiActions.addToDraft" }));
    expect(onAddToDraft).toHaveBeenCalledWith("A polished paragraph.");

    fireEvent.click(screen.getAllByRole("radio")[4]);
    fireEvent.click(screen.getByRole("button", { name: "aiActions.submitRating" }));

    await waitFor(() => {
      expect(capturedBody).toMatchObject({
        source_type: "chat_message",
        source_id: "msg-42",
        rating: 5,
        project_id: "proj-1",
      });
    });
    // CR-AUFG-07-24: non-UUID surface id must not be forwarded as suggestion_id
    expect(capturedBody).not.toHaveProperty("suggestion_id");
  });
});
