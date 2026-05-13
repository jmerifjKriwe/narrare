import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { WizardShell } from "./WizardShell";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      wizard: {
        title: "Set up Narrare",
        "step1.title": "Your project",
        "step2.title": "Your novel",
        "step3.title": "Starter content",
        "step4.title": "AI provider",
        "step5.title": "Confirm",
      },
      common: { next: "Next", back: "Back", finish: "Finish" },
    };
    return (key: string) => translations[ns]?.[key] ?? `${ns}.${key}`;
  },
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    back: vi.fn(),
  }),
}));

// Mock setupApi to avoid actual API calls during wizard shell tests
vi.mock("@/lib/api/client", () => ({
  setupApi: {
    complete: vi.fn().mockResolvedValue({
      novel_id: "new-novel-id",
      redirect_to: "/novels/new-novel-id",
      message: "Setup complete",
    }),
  },
}));

// Mock all wizard step components to isolate WizardShell behavior
vi.mock("./WizardStep1", () => ({
  WizardStep1: ({ onNext }: { onNext: () => void }) => (
    <div data-testid="step-1">
      Step 1 Content
      <button type="button" onClick={onNext}>
        Next Step
      </button>
    </div>
  ),
}));

vi.mock("./WizardStep2", () => ({
  WizardStep2: ({ onNext, onBack }: { onNext: () => void; onBack: () => void }) => (
    <div data-testid="step-2">
      Step 2 Content
      <button type="button" onClick={onNext}>
        Next Step
      </button>
      <button type="button" onClick={onBack}>
        Back
      </button>
    </div>
  ),
}));

vi.mock("./WizardStep3", () => ({
  WizardStep3: ({ onNext, onBack }: { onNext: () => void; onBack: () => void }) => (
    <div data-testid="step-3">
      Step 3 Content
      <button type="button" onClick={onNext}>
        Next Step
      </button>
      <button type="button" onClick={onBack}>
        Back
      </button>
    </div>
  ),
}));

vi.mock("./WizardStep4", () => ({
  WizardStep4: ({ onNext, onBack }: { onNext: () => void; onBack: () => void }) => (
    <div data-testid="step-4">
      Step 4 Content
      <button type="button" onClick={onNext}>
        Next Step
      </button>
      <button type="button" onClick={onBack}>
        Back
      </button>
    </div>
  ),
}));

vi.mock("./WizardStep5", () => ({
  WizardStep5: ({
    onComplete,
    onBack,
  }: {
    onComplete: () => Promise<void>;
    onBack: () => void;
  }) => (
    <div data-testid="step-5">
      Step 5 Content
      <button type="button" onClick={onComplete}>
        Complete Setup
      </button>
      <button type="button" onClick={onBack}>
        Back
      </button>
    </div>
  ),
}));

// --- Tests ---

beforeEach(() => {
  useWizardStore.getState().reset();
});

describe("WizardShell", () => {
  it("should render the wizard shell with step indicators", () => {
    render(<WizardShell />);
    // Verify step indicators are rendered (no heading — that comes from app layout)
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByTestId("step-1")).toBeInTheDocument();
  });

  it("should render step indicator with 5 steps", () => {
    render(<WizardShell />);

    const stepNumbers = ["1", "2", "3", "4", "5"];
    for (const num of stepNumbers) {
      expect(screen.getByText(num)).toBeInTheDocument();
    }
  });

  it("should show current step indicator (aria-current=step)", () => {
    render(<WizardShell />);

    // Step 1 is active by default — the div containing "1" has aria-current
    const step1 = screen.getByText("1");
    expect(step1).toHaveAttribute("aria-current", "step");

    // Other steps should not have aria-current
    const step2 = screen.getByText("2");
    expect(step2).not.toHaveAttribute("aria-current");
  });

  it("should show Step 1 content on initial render", () => {
    render(<WizardShell />);

    expect(screen.getByTestId("step-1")).toBeInTheDocument();
    expect(screen.queryByTestId("step-2")).not.toBeInTheDocument();
  });

  it("should transition to next step when nextStep is called", async () => {
    const user = userEvent.setup();
    render(<WizardShell />);

    // Click "Next Step" in Step 1 mock
    await user.click(screen.getByText("Next Step"));

    expect(screen.getByTestId("step-2")).toBeInTheDocument();
    expect(screen.queryByTestId("step-1")).not.toBeInTheDocument();
  });

  it("should transition back to previous step", async () => {
    const user = userEvent.setup();
    render(<WizardShell />);

    // Go to step 2
    await user.click(screen.getByText("Next Step"));
    expect(screen.getByTestId("step-2")).toBeInTheDocument();

    // Go back to step 1
    await user.click(screen.getByText("Back"));
    expect(screen.getByTestId("step-1")).toBeInTheDocument();
  });

  it("should mark completed steps with checkmark", async () => {
    const user = userEvent.setup();
    render(<WizardShell />);

    // Step 1 shows "1" initially
    expect(screen.getByText("1")).toBeInTheDocument();

    // Advance to step 2
    await user.click(screen.getByText("Next Step"));

    // Step 1 should now show checkmark
    expect(screen.getByText("\u2713")).toBeInTheDocument();
  });

  it("should update step indicator when navigating forward", async () => {
    const user = userEvent.setup();
    render(<WizardShell />);

    // Initially step 1 is current
    expect(screen.getByText("1")).toHaveAttribute("aria-current", "step");

    // Advance to step 2
    await user.click(screen.getByText("Next Step"));

    // Now step 2 should be current, step 1 shows checkmark
    expect(screen.getByText("2")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("\u2713")).not.toHaveAttribute("aria-current");
  });

  it("should show Step 5 content on the last step", async () => {
    const user = userEvent.setup();
    render(<WizardShell />);

    // Navigate through all steps
    await user.click(screen.getByText("Next Step")); // → step 2
    await user.click(screen.getByText("Next Step")); // → step 3
    await user.click(screen.getByText("Next Step")); // → step 4
    await user.click(screen.getByText("Next Step")); // → step 5

    expect(screen.getByTestId("step-5")).toBeInTheDocument();
  });

  it("should show Step 5 with Complete Setup button on last step", () => {
    // Set step to 5 before rendering
    useWizardStore.getState().setStep(5);

    render(<WizardShell />);

    expect(screen.getByText("Complete Setup")).toBeInTheDocument();
  });
});
