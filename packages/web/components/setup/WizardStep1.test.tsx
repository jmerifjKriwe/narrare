import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { WizardStep1 } from "./WizardStep1";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      "wizard.step1": {
        title: "Your project",
        description: "Choose a name and language for your writing project.",
        projectName: "Project name",
        projectNamePlaceholder: "e.g. My Fantasy Novel",
        language: "Writing language",
        autosave: "Autosave interval",
      },
      common: { next: "Next" },
    };
    return (key: string) => translations[ns]?.[key] ?? `${ns}.${key}`;
  },
}));

vi.mock("@/lib/api/client", () => ({
  setupApi: {
    validateStep1: vi.fn().mockResolvedValue({ valid: true }),
  },
}));

// --- Helpers ---

beforeEach(() => {
  vi.clearAllMocks();
  useWizardStore.getState().reset();
});

describe("WizardStep1", () => {
  it("should render the step title and description", () => {
    const onNext = vi.fn();
    render(<WizardStep1 onNext={onNext} />);

    expect(screen.getByText("Your project")).toBeInTheDocument();
    expect(
      screen.getByText("Choose a name and language for your writing project."),
    ).toBeInTheDocument();
  });

  it("should render project name input field", () => {
    const onNext = vi.fn();
    render(<WizardStep1 onNext={onNext} />);

    expect(screen.getByLabelText("Project name")).toBeInTheDocument();
  });

  it("should render language selector", () => {
    const onNext = vi.fn();
    render(<WizardStep1 onNext={onNext} />);

    expect(screen.getByLabelText("Writing language")).toBeInTheDocument();
  });

  it("should render autosave interval input", () => {
    const onNext = vi.fn();
    render(<WizardStep1 onNext={onNext} />);

    expect(screen.getByLabelText("Autosave interval")).toBeInTheDocument();
  });

  it("should render a Next button", () => {
    const onNext = vi.fn();
    render(<WizardStep1 onNext={onNext} />);

    expect(screen.getByRole("button", { name: /Next/ })).toBeInTheDocument();
  });

  it("should show validation error when project name is empty on submit", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();

    render(<WizardStep1 onNext={onNext} />);

    // Clear the default value (if any) and submit
    const nameInput = screen.getByLabelText("Project name");
    await user.clear(nameInput);
    await user.click(screen.getByRole("button", { name: /Next/ }));

    // Zod validation should show "Project name is required"
    await waitFor(() => {
      expect(screen.getByText("Project name is required")).toBeInTheDocument();
    });

    expect(onNext).not.toHaveBeenCalled();
  });

  it("should show validation error for invalid characters in project name", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();

    render(<WizardStep1 onNext={onNext} />);

    const nameInput = screen.getByLabelText("Project name");
    await user.clear(nameInput);
    await user.type(nameInput, "invalid/name");
    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(screen.getByText("Project name contains invalid characters")).toBeInTheDocument();
    });

    expect(onNext).not.toHaveBeenCalled();
  });

  it("should call onNext after valid submission", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();

    render(<WizardStep1 onNext={onNext} />);

    const nameInput = screen.getByLabelText("Project name");
    await user.clear(nameInput);
    await user.type(nameInput, "My Novel");

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(onNext).toHaveBeenCalledOnce();
    });
  });

  it("should update wizard store with form data on valid submission", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();

    render(<WizardStep1 onNext={onNext} />);

    const nameInput = screen.getByLabelText("Project name");
    await user.clear(nameInput);
    await user.type(nameInput, "Test Project");

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(useWizardStore.getState().state.project_name).toBe("Test Project");
    });
  });

  it("should have language options: English, Deutsch, Français", () => {
    const onNext = vi.fn();
    render(<WizardStep1 onNext={onNext} />);

    expect(screen.getByText("English")).toBeInTheDocument();
    expect(screen.getByText("Deutsch")).toBeInTheDocument();
    expect(screen.getByText("Français")).toBeInTheDocument();
  });

  it("should have default language set to 'en'", () => {
    const onNext = vi.fn();
    render(<WizardStep1 onNext={onNext} />);

    const langSelect = screen.getByLabelText("Writing language") as HTMLSelectElement;
    expect(langSelect.value).toBe("en");
  });
});
