import { render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AnalysisPanel } from "./AnalysisPanel";
import { BlockControls } from "./BlockControls";
import { CommandPalette } from "./editor/CommandPalette";
import { WorldBuilding } from "./WorldBuilding";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
// Note: next-intl is mocked globally in setupTests.ts

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AnalysisPanel", () => {
  describe("rendering", () => {
    it("renders analysis panel component", async () => {
      render(<AnalysisPanel novelId="novel-1" />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });
});

describe("BlockControls", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("rendering", () => {
    it("renders without editor", async () => {
      render(<BlockControls editor={null} />);

      // Should not render controls without editor
      await waitFor(() => {
        // Just verify it doesn't crash
        expect(document.body).toBeInTheDocument();
      });
    });
  });
});

describe("WorldBuilding", () => {
  describe("rendering", () => {
    it("renders world building component", async () => {
      render(<WorldBuilding novelId="novel-1" />);

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });
  });
});

describe("CommandPalette", () => {
  describe("rendering", () => {
    it("renders command palette when open", async () => {
      render(
        <CommandPalette
          editor={null}
          isOpen={true}
          onClose={vi.fn()}
          context={{
            toggleSidebar: vi.fn(),
            toggleFocusMode: vi.fn(),
            toggleContextPanel: vi.fn(),
            saveChapter: vi.fn(),
            createChapter: vi.fn(),
          }}
        />,
      );

      await waitFor(() => {
        expect(document.querySelector("div")).toBeInTheDocument();
      });
    });

    it("does not render when closed", async () => {
      const { container } = render(
        <CommandPalette
          editor={null}
          isOpen={false}
          onClose={vi.fn()}
          context={{
            toggleSidebar: vi.fn(),
            toggleFocusMode: vi.fn(),
            toggleContextPanel: vi.fn(),
            saveChapter: vi.fn(),
            createChapter: vi.fn(),
          }}
        />,
      );

      // When closed, should not render the modal content
      expect(container.firstChild).toBeNull();
    });
  });
});
