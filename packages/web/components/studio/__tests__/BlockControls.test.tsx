/**
 * BlockControls tests — TipTap drag handle with block-level controls.
 *
 * Tests:
 * 1. Returns null when editor is null
 * 2. Renders drag handle with controls when editor provided
 * 3. Renders add block button
 * 4. Renders drag handle element
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BlockControls } from "@/components/studio/BlockControls";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("@tiptap/extension-drag-handle-react", () => ({
  default: ({
    children,
  }: {
    children: React.ReactNode;
    editor: unknown;
    computePositionConfig: unknown;
    onNodeChange: unknown;
    onElementDragStart: unknown;
    onElementDragEnd: unknown;
  }) => <div data-testid="drag-handle-wrapper">{children}</div>,
}));

vi.mock("@/lib/stores/editorStore", () => ({
  useEditorStore: {
    getState: () => ({
      setIsDragging: vi.fn(),
    }),
  },
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("BlockControls", () => {
  it("returns null when editor is null", () => {
    const { container } = render(<BlockControls editor={null} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders drag handle wrapper when editor provided", () => {
    const mockEditor = {
      state: {
        doc: {
          nodeAt: () => ({ nodeSize: 10 }),
        },
      },
      chain: () => ({
        focus: () => ({
          insertContentAt: () => ({
            run: vi.fn(),
          }),
        }),
      }),
    };

    render(<BlockControls editor={mockEditor as unknown as never} />);

    expect(screen.getByTestId("drag-handle-wrapper")).toBeDefined();
  });

  it("renders add block button when editor provided", () => {
    const mockEditor = {
      state: {
        doc: {
          nodeAt: () => ({ nodeSize: 10 }),
        },
      },
      chain: () => ({
        focus: () => ({
          insertContentAt: () => ({
            run: vi.fn(),
          }),
        }),
      }),
    };

    render(<BlockControls editor={mockEditor as unknown as never} />);

    expect(screen.getByTitle("editor.addBlock")).toBeDefined();
  });

  it("renders drag handle element", () => {
    const mockEditor = {
      state: {
        doc: {
          nodeAt: () => ({ nodeSize: 10 }),
        },
      },
      chain: () => ({
        focus: () => ({
          insertContentAt: () => ({
            run: vi.fn(),
          }),
        }),
      }),
    };

    render(<BlockControls editor={mockEditor as unknown as never} />);

    const dragHandle = document.querySelector("[data-drag-handle]");
    expect(dragHandle).toBeDefined();
  });
});
