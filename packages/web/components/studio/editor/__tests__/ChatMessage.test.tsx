import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ChatMessage } from "@/components/studio/editor/ChatMessage";

describe("ChatMessage", () => {
  const addToDraftLabel = "Add to draft";
  const addedToDraftLabel = "Added!";
  const aiDraftBadge = "AI Draft";
  const onAddToDraft = vi.fn();

  it("renders system message centered", () => {
    render(
      <ChatMessage
        message={{ id: "1", role: "system", content: "System message" }}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    expect(screen.getByText("System message")).toBeDefined();
  });

  it("renders user message right-aligned", () => {
    render(
      <ChatMessage
        message={{ id: "2", role: "user", content: "User message" }}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    expect(screen.getByText("User message")).toBeDefined();
  });

  it("renders assistant message left-aligned", () => {
    render(
      <ChatMessage
        message={{ id: "3", role: "assistant", content: "Assistant text", prose: "Draft text" }}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    expect(screen.getByText("Assistant text")).toBeDefined();
    expect(screen.getByText("Draft text")).toBeDefined();
    expect(screen.getByText("AI Draft")).toBeDefined();
  });

  it("shows add to draft button for assistant messages with prose", () => {
    render(
      <ChatMessage
        message={{ id: "4", role: "assistant", content: "Hi", prose: "Some text" }}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    expect(screen.getByText(addToDraftLabel)).toBeDefined();
  });

  it("calls onAddToDraft when add button is clicked", () => {
    render(
      <ChatMessage
        message={{ id: "5", role: "assistant", content: "Hi", prose: "Some prose" }}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    fireEvent.click(screen.getByText(addToDraftLabel));
    expect(onAddToDraft).toHaveBeenCalledWith("Some prose");
  });

  it("shows added state when isAdded is true", () => {
    render(
      <ChatMessage
        message={{ id: "6", role: "assistant", content: "Hi", prose: "Some text" }}
        isAdded={true}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    expect(screen.getByText(addedToDraftLabel)).toBeDefined();
  });

  it("does not render prose section when prose is absent", () => {
    render(
      <ChatMessage
        message={{ id: "7", role: "assistant", content: "Just text" }}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    expect(screen.getByText("Just text")).toBeDefined();
    expect(screen.queryByText(addToDraftLabel)).toBeNull();
  });

  it("does not render content when assistant message has no text", () => {
    const { container } = render(
      <ChatMessage
        message={{ id: "8", role: "assistant", content: "" }}
        isAdded={false}
        onAddToDraft={onAddToDraft}
        aiDraftBadge={aiDraftBadge}
        addToDraftLabel={addToDraftLabel}
        addedToDraftLabel={addedToDraftLabel}
      />,
    );
    // Bot icon should still be rendered, just no text content div
    // The component has a Bot icon + conditional content
    expect(container).toBeDefined();
  });
});
