import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { WizardStep3 } from "./WizardStep3";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      "wizard.step3": {
        title: "Starter content",
        description: "Start fresh or explore with ready-made content.",
        blank: "Blank project",
        blankDescription: "Start with an empty editor.",
        import: "Import existing",
        importDescription: "Import from an existing directory.",
        importPath: "Directory path",
      },
      common: { next: "Next", back: "Back" },
    };
    return (key: string) => translations[ns]?.[key] ?? `${ns}.${key}`;
  },
}));

vi.mock("@/lib/api/client", () => ({
  setupApi: {
    validateStep3: vi.fn().mockResolvedValue({ valid: true, starter: "blank", demo_info: null }),
  },
}));

// --- Helpers ---

beforeEach(() => {
  vi.clearAllMocks();
  useWizardStore.getState().reset();
});

describe("WizardStep3", () => {
  it("should render the step title and description", () => {
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Starter content")).toBeInTheDocument();
    expect(screen.getByText("Start fresh or explore with ready-made content.")).toBeInTheDocument();
  });

  it("should render 'Blank project' option", () => {
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Blank project")).toBeInTheDocument();
    expect(screen.getByText("Start with an empty editor.")).toBeInTheDocument();
  });

  it("should render demo content options", () => {
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    // Demo options show as "Demo fantasy", "Demo scifi", "Demo german" from fallback logic
    expect(screen.getByText("Demo fantasy")).toBeInTheDocument();
    expect(screen.getByText("Demo scifi")).toBeInTheDocument();
    expect(screen.getByText("Demo german")).toBeInTheDocument();
  });

  it("should render 'Import existing' option", () => {
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Import existing")).toBeInTheDocument();
  });

  it("should select blank project by default", () => {
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    const blankCard = screen.getByText("Blank project").closest("button");
    expect(blankCard).toHaveAttribute("aria-pressed", "true");
  });

  it("should update selection when a demo option is clicked", async () => {
    const user = userEvent.setup();
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    await user.click(screen.getByText("Demo fantasy"));

    const blankCard = screen.getByText("Blank project").closest("button");
    expect(blankCard).toHaveAttribute("aria-pressed", "false");

    const fantasyCard = screen.getByText("Demo fantasy").closest("button");
    expect(fantasyCard).toHaveAttribute("aria-pressed", "true");
  });

  it("should call onNext when Next is clicked with a valid selection", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();

    render(<WizardStep3 onNext={onNext} onBack={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(onNext).toHaveBeenCalledOnce();
    });
  });

  it("should update wizard store with selected starter content", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();

    render(<WizardStep3 onNext={onNext} onBack={vi.fn()} />);

    await user.click(screen.getByText("Demo fantasy"));
    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(useWizardStore.getState().state.starter).toBe("demo_fantasy");
    });
  });

  it("should call onBack when Back button is clicked", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();

    render(<WizardStep3 onNext={vi.fn()} onBack={onBack} />);

    await user.click(screen.getByRole("button", { name: /Back/ }));

    expect(onBack).toHaveBeenCalledOnce();
  });

  it("should show import path input when 'Import existing' is selected", async () => {
    const user = userEvent.setup();
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    expect(screen.queryByLabelText("Directory path")).not.toBeInTheDocument();

    await user.click(screen.getByText("Import existing"));

    expect(screen.getByLabelText("Directory path")).toBeInTheDocument();
  });

  it("should render 5 starter card options (blank + 3 demos + import)", () => {
    render(<WizardStep3 onNext={vi.fn()} onBack={vi.fn()} />);

    const cards = screen.getAllByRole("button").filter((btn) => btn.hasAttribute("aria-pressed"));
    expect(cards).toHaveLength(5);
  });
});
