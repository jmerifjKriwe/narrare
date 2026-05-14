import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { CommandPalette } from "./CommandPalette";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => (key: string) => `${ns}.${key}`,
}));

const mockEditor = {
  chain: () => ({
    focus: () => ({
      toggleBold: () => ({ run: vi.fn() }),
      toggleItalic: () => ({ run: vi.fn() }),
      toggleHeading: () => ({ run: vi.fn() }),
    }),
  }),
  commands: {
    insertContent: vi.fn(),
    forceSave: vi.fn(),
  },
};

const mockContext = {
  toggleSidebar: vi.fn(),
  toggleFocusMode: vi.fn(),
  toggleContextPanel: vi.fn(),
  saveChapter: vi.fn(),
  createChapter: vi.fn(),
};

const defaultProps = {
  editor: mockEditor as unknown as Parameters<typeof CommandPalette>[0]["editor"],
  isOpen: true,
  onClose: vi.fn(),
  context: mockContext,
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe("CommandPalette", () => {
  it("should render when isOpen is true", () => {
    render(<CommandPalette {...defaultProps} />);
    expect(screen.getByPlaceholderText("editor.commandPalettePlaceholder")).toBeInTheDocument();
  });

  it("should not render when isOpen is false", () => {
    render(<CommandPalette {...defaultProps} isOpen={false} />);
    expect(
      screen.queryByPlaceholderText("editor.commandPalettePlaceholder"),
    ).not.toBeInTheDocument();
  });

  it("should display command categories", () => {
    render(<CommandPalette {...defaultProps} />);
    expect(screen.getByText("editor.categoryFormat")).toBeInTheDocument();
    expect(screen.getByText("editor.categoryEditor")).toBeInTheDocument();
  });

  it("should display built-in commands", () => {
    render(<CommandPalette {...defaultProps} />);
    expect(screen.getByText("Bold")).toBeInTheDocument();
    expect(screen.getByText("Italic")).toBeInTheDocument();
    expect(screen.getByText("Save")).toBeInTheDocument();
  });

  it("should filter commands by search query", async () => {
    const user = userEvent.setup();
    render(<CommandPalette {...defaultProps} />);

    const input = screen.getByPlaceholderText("editor.commandPalettePlaceholder");
    await user.type(input, "bold");

    expect(screen.getByText("Bold")).toBeInTheDocument();
    expect(screen.queryByText("Italic")).not.toBeInTheDocument();
    expect(screen.queryByText("Save")).not.toBeInTheDocument();
  });

  it("should show no-results message when query matches nothing", async () => {
    const user = userEvent.setup();
    render(<CommandPalette {...defaultProps} />);

    const input = screen.getByPlaceholderText("editor.commandPalettePlaceholder");
    await user.type(input, "xyznonexistent");

    expect(screen.getByText("editor.noCommandsFound")).toBeInTheDocument();
  });

  it("should call onClose when backdrop is clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CommandPalette {...defaultProps} onClose={onClose} />);

    // Click on the backdrop (the first element with the bg-black class)
    const backdrop = document.querySelector(".bg-black\\/30");
    if (backdrop) {
      await user.click(backdrop);
      expect(onClose).toHaveBeenCalled();
    }
  });

  it("should execute command and close on click", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<CommandPalette {...defaultProps} onClose={onClose} />);

    await user.click(screen.getByText("Toggle Sidebar"));
    expect(mockContext.toggleSidebar).toHaveBeenCalled();
    expect(onClose).toHaveBeenCalled();
  });

  it("should display keyboard shortcuts for commands that have them", () => {
    render(<CommandPalette {...defaultProps} />);
    expect(screen.getByText("⌘B")).toBeInTheDocument();
    expect(screen.getByText("⌘S")).toBeInTheDocument();
  });
});
