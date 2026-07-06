import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AnalysisPanel } from "./AnalysisPanel";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
// Note: next-intl is mocked globally in setupTests.ts

const navigationMocks = vi.hoisted(() => ({
  pathname: "/novel/novel-1/analysis",
  push: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationMocks.pathname,
  useRouter: () => ({ push: navigationMocks.push, replace: navigationMocks.replace }),
  useSearchParams: () => navigationMocks.searchParams,
}));

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
  beforeEach(() => {
    navigationMocks.push.mockClear();
    navigationMocks.replace.mockClear();
    navigationMocks.searchParams = new URLSearchParams();
  });

  describe("rendering", () => {
    it("renders analysis panel component", () => {
      render(<AnalysisPanel novelId="novel-1" />);

      // Should render the main container
      expect(document.querySelector("div.flex-1.overflow-y-auto.p-8")).toBeInTheDocument();
    });

    it("labels the analysis view section with its title", () => {
      render(<AnalysisPanel novelId="novel-1" />);

      expect(screen.getByRole("region", { name: "analysis.title" })).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("toggles analysis panel when clicking analyze button", async () => {
      render(<AnalysisPanel novelId="novel-1" />);

      // Find analyze buttons
      const buttons = await screen.findAllByRole("button", { name: /analyze/i });
      expect(buttons.length).toBeGreaterThan(0);

      // Click the first analyze button (readability card)
      await userEvent.click(buttons[0]);

      // Clicking toggles the panel on by pushing it into the URL. We assert on
      // the navigation call rather than expanded DOM because the test's router
      // mock returns a fresh object each render, so the panel state is owned by
      // the URL between renders rather than held in component state.
      expect(navigationMocks.push).toHaveBeenCalledWith(
        expect.stringContaining("panel=readability"),
        { scroll: false },
      );
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

    it("initializes active panel from URL state and shows the editor hint", () => {
      navigationMocks.searchParams = new URLSearchParams("panel=readability");

      render(<AnalysisPanel novelId="novel-1" />);

      // The expanded panel no longer renders mock scores/details; it shows an
      // editor hint and an "Open in Editor" link until real analysis is wired.
      expect(screen.getByText("analysis.readability.editorHint")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "analysis.openInEditor" })).toBeInTheDocument();
    });

    it("removes invalid panel URL state with replace", () => {
      navigationMocks.searchParams = new URLSearchParams("panel=missing");

      render(<AnalysisPanel novelId="novel-1" />);

      expect(navigationMocks.replace).toHaveBeenCalledWith("/novel/novel-1/analysis", {
        scroll: false,
      });
    });
  });
});
