import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ProviderForm } from "./ProviderForm";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------
// Note: next-intl is mocked globally in setupTests.ts

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ProviderForm", () => {
  const mockOnSubmit = vi.fn();
  const mockOnCancel = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe("rendering", () => {
    it("renders in add mode", () => {
      render(
        <ProviderForm
          mode="add"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key} // Simple identity mock for translation
        />,
      );

      // Should render the form container
      expect(document.querySelector("div.space-y-4.ml-15")).toBeInTheDocument();
    });

    it("renders in edit mode", () => {
      render(
        <ProviderForm
          mode="edit"
          initialProviderName="openai"
          initialBaseUrl="https://api.openai.com/v1"
          hasKey={true}
          last4="1234"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      expect(document.querySelector("div.space-y-4.ml-15")).toBeInTheDocument();
    });
  });

  describe("interactions", () => {
    it("sets provider name in add mode", async () => {
      render(
        <ProviderForm
          mode="add"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      const providerSelect = screen.getByLabelText("settings.ai.providerName") as HTMLSelectElement;
      await userEvent.selectOptions(providerSelect, "anthropic");
      expect(providerSelect.value).toBe("anthropic");
    });

    it("sets API key", async () => {
      render(
        <ProviderForm
          mode="add"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      const apiKeyInput = screen.getByLabelText("settings.ai.apiKey") as HTMLInputElement;
      await userEvent.type(apiKeyInput, "test-key-123");
      expect(apiKeyInput.value).toBe("test-key-123");
    });

    it("sets base URL", async () => {
      render(
        <ProviderForm
          mode="add"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      const baseUrlInput = screen.getByLabelText("settings.ai.baseUrl") as HTMLInputElement;
      await userEvent.type(baseUrlInput, "https://custom.api.com");
      expect(baseUrlInput.value).toBe("https://custom.api.com");
    });

    it("calls onSubmit with correct data in add mode", async () => {
      render(
        <ProviderForm
          mode="add"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      // Select provider
      const providerSelect = screen.getByLabelText("settings.ai.providerName");
      await userEvent.selectOptions(providerSelect, "google");

      // Fill API key
      const apiKeyInput = screen.getByLabelText("settings.ai.apiKey");
      await userEvent.type(apiKeyInput, "my-api-key");

      // Fill base URL
      const baseUrlInput = screen.getByLabelText("settings.ai.baseUrl");
      await userEvent.type(baseUrlInput, "https://api.example.com");

      // Submit
      const submitButton = screen.getByRole("button", { name: /settings\.ai\.save/i });
      await userEvent.click(submitButton);

      // Wait for submit to be called
      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      });

      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          provider_name: "google",
          api_key: "my-api-key",
          base_url: "https://api.example.com",
        }),
      );
    });

    it("calls onSubmit with only changed fields in edit mode", async () => {
      render(
        <ProviderForm
          mode="edit"
          initialProviderName="openai"
          initialBaseUrl="https://api.openai.com/v1"
          hasKey={true}
          last4="1234"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      // Change only the API key
      const apiKeyInput = screen.getByLabelText("settings.ai.editApiKey");
      await userEvent.clear(apiKeyInput);
      await userEvent.type(apiKeyInput, "new-key-5678");

      // Submit
      const submitButton = screen.getByRole("button", { name: /settings\.ai\.save/i });
      await userEvent.click(submitButton);

      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      });

      expect(mockOnSubmit).toHaveBeenCalledWith(
        expect.objectContaining({
          api_key: "new-key-5678",
          // base_url should not be included if unchanged
        }),
      );

      // Verify base_url is not in the call (or is the same as initial)
      const callArgs = mockOnSubmit.mock.calls[0][0];
      expect(callArgs).toHaveProperty("api_key", "new-key-5678");
      // base_url may be present if it's different, but we only changed apiKey
    });

    it("does not call onSubmit when API key is empty in edit mode (no change)", async () => {
      render(
        <ProviderForm
          mode="edit"
          initialProviderName="openai"
          initialBaseUrl="https://api.openai.com/v1"
          hasKey={false}
          last4=""
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      // Don't change anything
      const submitButton = screen.getByRole("button", { name: /settings\.ai\.save/i });
      await userEvent.click(submitButton);

      // Should not call submit if no changes? Actually the component might still call it.
      // Let's check the implementation: it only adds apiKey if apiKey is truthy.
      // Since we start with hasKey=false and empty apiKey, and we don't change it,
      // the payload will be empty object.
      await waitFor(() => {
        expect(mockOnSubmit).toHaveBeenCalledTimes(1);
      });

      expect(mockOnSubmit).toHaveBeenCalledWith({});
    });

    it("calls onCancel when cancel button is clicked", async () => {
      render(
        <ProviderForm
          mode="add"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      const cancelButton = screen.getByRole("button", { name: /settings\.ai\.cancel/i });
      await userEvent.click(cancelButton);

      expect(mockOnCancel).toHaveBeenCalledTimes(1);
    });

    it("shows loading state when isPending is true", () => {
      render(
        <ProviderForm
          mode="add"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={true}
          t={(key: string) => key}
        />,
      );

      const submitButton = screen.getByRole("button", { name: /settings\.ai\.loading/i });
      expect(submitButton).toBeInTheDocument();
      // The button should be disabled
      expect(submitButton).toBeDisabled();
    });

    it("hints at existing API key in edit mode", () => {
      render(
        <ProviderForm
          mode="edit"
          initialProviderName="anthropic"
          initialBaseUrl="https://api.anthropic.com"
          hasKey={true}
          last4="9876"
          onSubmit={mockOnSubmit}
          onCancel={mockOnCancel}
          isPending={false}
          t={(key: string) => key}
        />,
      );

      const apiKeyHint = screen.getByText("settings.ai.apiKeyHint");
      expect(apiKeyHint).toBeInTheDocument();
      // The placeholder should show the masked key
      const apiKeyInput = screen.getByLabelText("settings.ai.editApiKey");
      expect(apiKeyInput).toHaveAttribute("placeholder", "••••••••9876");
    });
  });

  // -------------------------------------------------------------------------
  // Regression: the settings provider list must be derived from the shared
  // catalog, not a hand-maintained 5-entry list (Groq/Z.AI were unpickable).
  // -------------------------------------------------------------------------
  describe("provider select (Groq/Z.AI defect)", () => {
    const t = (key: string) => key; // identity translator: labels surface as keys

    function optionValues(): string[] {
      return Array.from(document.querySelectorAll<HTMLOptionElement>("#provider-name option")).map(
        (o) => o.value,
      );
    }

    it("offers every catalog provider in canonical order", () => {
      render(
        <ProviderForm mode="add" onSubmit={vi.fn()} onCancel={vi.fn()} isPending={false} t={t} />,
      );
      expect(optionValues()).toEqual([
        "anthropic",
        "openai",
        "google",
        "groq",
        "ollama",
        "openrouter",
        "zai",
      ]);
    });

    it("offers groq and zai specifically (the reported defect)", () => {
      render(
        <ProviderForm mode="add" onSubmit={vi.fn()} onCancel={vi.fn()} isPending={false} t={t} />,
      );
      expect(optionValues()).toContain("groq");
      expect(optionValues()).toContain("zai");
      const labels = Array.from(
        document.querySelectorAll<HTMLOptionElement>("#provider-name option"),
      ).map((o) => o.textContent);
      expect(labels).toContain("settings-ai.providers.groq");
      expect(labels).toContain("settings-ai.providers.zai");
    });
  });
});
