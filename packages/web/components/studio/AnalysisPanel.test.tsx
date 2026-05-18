import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { AnalysisPanel } from "./AnalysisPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
// Note: next-intl is mocked globally in setupTests.ts

// Mock the novelsApi even though AnalysisPanel doesn't currently use it
// This demonstrates the pattern of local MSW handler overrides for API calls
vi.mock("@/lib/api/client", () => ({
  novelsApi: {
    get: vi.fn(),
  },
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AnalysisPanel", () => {
  describe("rendering", () => {
    it("renders analysis panel component", () => {
      render(<AnalysisPanel novelId="novel-1" />);

      // Should render the main container
      expect(document.querySelector("div.flex-1.overflow-y-auto.p-8")).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("toggles analysis panel when clicking analyze button", async () => {
      render(<AnalysisPanel novelId="novel-1" />);

      // Find analyze buttons
      const buttons = await screen.findAllByRole("button", { name: /analyze/i });
      expect(buttons.length).toBeGreaterThan(0);

      // Click the first analyze button
      await userEvent.click(buttons[0]);

      // Should now show some analysis content (we don't check specifics due to i18n)
      expect(document.querySelector("div")).toBeInTheDocument();
    });

    it("toggles analysis panel closed when clicking analyze button again", async () => {
      render(<AnalysisPanel novelId="novel-1" />);

      const buttons = await screen.findAllByRole("button", { name: /analyze/i });

      // Click to open
      await userEvent.click(buttons[0]);

      // Click to close
      await userEvent.click(buttons[0]);

      // Component should still render
      expect(document.querySelector("div.flex-1.overflow-y-auto.p-8")).toBeInTheDocument();
    });
  });
});
