/**
 * ChatInputArea tests — clear-conversation confirmation dialog.
 *
 * Clearing a conversation is destructive (removes all messages), so it must
 * be guarded by a ConfirmDialog. Clicking the trigger only opens the dialog;
 * only confirming actually calls onClearConversation.
 *
 * Note: setupTests.ts provides a global next-intl mock that returns the
 * translation key as the string, and the component is rendered with a
 * `t` prop that returns the key as well. So labels appear as their keys.
 */
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentProps } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatInputArea } from "@/components/studio/editor/ChatInputArea";

type ChatInputAreaProps = ComponentProps<typeof ChatInputArea>;

function renderInputArea(overrides: Partial<ChatInputAreaProps> = {}) {
  const props: ChatInputAreaProps = {
    inputRef: { current: null },
    input: "",
    onInputChange: () => {},
    onKeyDown: () => {},
    isStreaming: false,
    onSend: () => {},
    onCancelStream: () => {},
    onClearConversation: vi.fn(),
    hasMessages: true,
    t: (key: string) => key,
    ...overrides,
  };
  return render(<ChatInputArea {...props} />);
}

describe("ChatInputArea — clear conversation confirmation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });
  afterEach(() => {
    cleanup();
  });

  it("does not call onClearConversation immediately when the trigger is clicked", () => {
    const onClearConversation = vi.fn();
    renderInputArea({ onClearConversation });

    fireEvent.click(screen.getByText("chatPanel.clearConversation"));

    expect(onClearConversation).not.toHaveBeenCalled();
  });

  it("opens a confirmation dialog when the trigger is clicked", () => {
    renderInputArea();

    fireEvent.click(screen.getByText("chatPanel.clearConversation"));

    expect(screen.getByRole("alertdialog")).toBeDefined();
    expect(screen.getByText("chatPanel.clearConversationConfirm")).toBeDefined();
  });

  it("calls onClearConversation once when the dialog is confirmed", () => {
    const onClearConversation = vi.fn();
    renderInputArea({ onClearConversation });

    fireEvent.click(screen.getByText("chatPanel.clearConversation"));
    const dialog = screen.getByRole("alertdialog");
    // Confirm by button role — the title shares the same label text, so a
    // text query would be ambiguous. The confirm button is the destructive
    // action inside the dialog.
    fireEvent.click(within(dialog).getByRole("button", { name: "chatPanel.clearConversation" }));

    expect(onClearConversation).toHaveBeenCalledOnce();
  });

  it("does not call onClearConversation when the dialog is canceled and closes the dialog", () => {
    const onClearConversation = vi.fn();
    renderInputArea({ onClearConversation });

    fireEvent.click(screen.getByText("chatPanel.clearConversation"));
    const dialog = screen.getByRole("alertdialog");
    fireEvent.click(within(dialog).getByText("cancel"));

    expect(onClearConversation).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("does not render the clear trigger when there are no messages", () => {
    renderInputArea({ hasMessages: false });

    expect(screen.queryByText("chatPanel.clearConversation")).toBeNull();
  });
});
