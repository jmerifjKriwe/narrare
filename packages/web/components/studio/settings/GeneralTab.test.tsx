import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { GeneralTab } from "./GeneralTab";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
// Note: next-intl is mocked globally in setupTests.ts

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: vi.fn(),
  }),
}));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("GeneralTab", () => {
  const mockSave = vi.fn();
  const defaultProps = {
    displayName: "Test User",
    uiLanguage: "en",
    isLoading: false,
    onSaveProfile: mockSave,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("rendering", () => {
    it("renders title and description", () => {
      render(<GeneralTab {...defaultProps} />);

      expect(screen.getByText("settings.generalSection.title")).toBeInTheDocument();
      expect(screen.getByText("settings.generalSection.description")).toBeInTheDocument();
    });

    it("renders loading state", () => {
      render(<GeneralTab {...defaultProps} isLoading={true} />);

      const spinner = document.querySelector(".animate-spin");
      expect(spinner).toBeInTheDocument();
    });

    it("renders display name input with value", () => {
      render(<GeneralTab {...defaultProps} />);

      const input = screen.getByDisplayValue("Test User");
      expect(input).toBeInTheDocument();
      expect(input).toHaveValue("Test User");
    });

    it("renders language selector", () => {
      render(<GeneralTab {...defaultProps} />);

      const languageSelect = screen.getByDisplayValue("settings.generalSection.langEn");
      expect(languageSelect).toBeInTheDocument();
    });

    it("renders color mode buttons", () => {
      render(<GeneralTab {...defaultProps} />);

      expect(screen.getByLabelText("settings.generalSection.themeLight")).toBeInTheDocument();
      expect(screen.getByLabelText("settings.generalSection.themeDark")).toBeInTheDocument();
      expect(screen.getByLabelText("settings.generalSection.themeSystem")).toBeInTheDocument();
    });

    it("renders theme buttons", () => {
      render(<GeneralTab {...defaultProps} />);

      expect(screen.getByText("Neutral")).toBeInTheDocument();
      expect(screen.getByText("Narrare")).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("updates display name on input change", async () => {
      render(<GeneralTab {...defaultProps} />);

      const input = screen.getByDisplayValue("Test User");
      await userEvent.clear(input);
      await userEvent.type(input, "New Name");

      expect(input).toHaveValue("New Name");
    });

    it("shows save button when form is dirty", async () => {
      render(<GeneralTab {...defaultProps} />);

      // Save button should not be visible initially
      expect(screen.queryByText("settings.ai.save")).not.toBeInTheDocument();

      // Change display name
      const input = screen.getByDisplayValue("Test User");
      await userEvent.clear(input);
      await userEvent.type(input, "New Name");

      // Save button should now appear
      expect(screen.getByText("settings.ai.save")).toBeInTheDocument();
    });

    it("calls onSaveProfile on save", async () => {
      render(<GeneralTab {...defaultProps} />);

      // Make form dirty
      const input = screen.getByDisplayValue("Test User");
      await userEvent.clear(input);
      await userEvent.type(input, "Updated Name");

      // Click save
      await userEvent.click(screen.getByText("settings.ai.save"));

      // Verify save was called with updated values
      expect(mockSave).toHaveBeenCalledWith({
        display_name: "Updated Name",
        ui_language: "en",
      });
    });

    it("hides save button after save", async () => {
      render(<GeneralTab {...defaultProps} />);

      // Make form dirty
      const input = screen.getByDisplayValue("Test User");
      await userEvent.clear(input);
      await userEvent.type(input, "Updated Name");

      // Click save
      await userEvent.click(screen.getByText("settings.ai.save"));

      // Save button should disappear
      expect(screen.queryByText("settings.ai.save")).not.toBeInTheDocument();
    });
  });
});
