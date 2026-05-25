import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
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

// Shared command context mock with all required fields
const mockCommandContext = {
  toggleSidebar: vi.fn(),
  toggleFocusMode: vi.fn(),
  toggleContextPanel: vi.fn(),
  toggleStoryboard: vi.fn(),
  saveChapter: vi.fn(),
  createChapter: vi.fn(),
  startGeneration: vi.fn(),
  stopGeneration: vi.fn(),
  acceptDraft: vi.fn(),
  rejectDraft: vi.fn(),
  toggleGenerationPanel: vi.fn(),
  startExtend: vi.fn(),
  startRewrite: vi.fn(),
};

const mockCommandState = {
  isGenerating: false,
  hasDraft: false,
  hasPendingAnnotation: false,
  hasSelection: false,
  selectionLength: 0,
};

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
      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: 0 } },
      });
      render(
        <QueryClientProvider client={queryClient}>
          <WorldBuilding novelId="novel-1" />
        </QueryClientProvider>,
      );

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
          context={mockCommandContext}
          commandState={mockCommandState}
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
          context={mockCommandContext}
          commandState={mockCommandState}
        />,
      );

      // When closed, should not render the modal content
      expect(container.firstChild).toBeNull();
    });
  });
});
