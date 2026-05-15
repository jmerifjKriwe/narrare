import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { WizardShell } from "./WizardShell";

// --- Mocks ---

// Control whether authApi.me() returns has_providers=true or false
let mockHasProviders = false;

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
      common: { next: "Next", back: "Back", finish: "Finish", loading: "Loading\u2026" },
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

// Mock API client — authApi.me() is configurable via mockHasProviders
vi.mock("@/lib/api/client", () => ({
  authApi: {
    me: () =>
      Promise.resolve({
        id: "user-1",
        email: "test@example.com",
        display_name: "Test User",
        is_active: true,
        is_verified: true,
        has_providers: mockHasProviders,
        created_at: "2025-01-01T00:00:00Z",
      }),
  },
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

// --- Helpers ---

/** Render WizardShell and wait for the async provider check to complete. */
async function renderWizard() {
  const user = userEvent.setup();
  const result = render(<WizardShell />);
  // Wait for loading state to resolve and step content to appear
  await waitFor(() => {
    expect(screen.queryByText("Loading\u2026")).not.toBeInTheDocument();
  });
  return { ...result, user };
}

// --- Tests ---

beforeEach(() => {
  useWizardStore.getState().reset();
  mockHasProviders = false;
});

describe("WizardShell", () => {
  it("should render the wizard shell with step indicators", async () => {
    await renderWizard();
    // Verify step indicators are rendered (no heading — that comes from app layout)
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByTestId("step-1")).toBeInTheDocument();
  });

  it("should render step indicator with 5 steps when no providers", async () => {
    await renderWizard();

    const stepNumbers = ["1", "2", "3", "4", "5"];
    for (const num of stepNumbers) {
      expect(screen.getByText(num)).toBeInTheDocument();
    }
  });

  it("should show current step indicator (aria-current=step)", async () => {
    await renderWizard();

    // Step 1 is active by default — the div containing "1" has aria-current
    const step1 = screen.getByText("1");
    expect(step1).toHaveAttribute("aria-current", "step");

    // Other steps should not have aria-current
    const step2 = screen.getByText("2");
    expect(step2).not.toHaveAttribute("aria-current");
  });

  it("should show Step 1 content on initial render", async () => {
    await renderWizard();

    expect(screen.getByTestId("step-1")).toBeInTheDocument();
    expect(screen.queryByTestId("step-2")).not.toBeInTheDocument();
  });

  it("should transition to next step when nextStep is called", async () => {
    const { user } = await renderWizard();

    // Click "Next Step" in Step 1 mock
    await user.click(screen.getByText("Next Step"));

    // Steps 2 and 3 are swapped: step 2 now renders WizardStep3
    expect(screen.getByTestId("step-3")).toBeInTheDocument();
    expect(screen.queryByTestId("step-1")).not.toBeInTheDocument();
  });

  it("should transition back to previous step", async () => {
    const { user } = await renderWizard();

    // Go to step 2 (now renders WizardStep3)
    await user.click(screen.getByText("Next Step"));
    expect(screen.getByTestId("step-3")).toBeInTheDocument();

    // Go back to step 1
    await user.click(screen.getByText("Back"));
    expect(screen.getByTestId("step-1")).toBeInTheDocument();
  });

  it("should mark completed steps with checkmark", async () => {
    const { user } = await renderWizard();

    // Step 1 shows "1" initially
    expect(screen.getByText("1")).toBeInTheDocument();

    // Advance to step 2
    await user.click(screen.getByText("Next Step"));

    // Step 1 should now show checkmark
    expect(screen.getByText("\u2713")).toBeInTheDocument();
  });

  it("should update step indicator when navigating forward", async () => {
    const { user } = await renderWizard();

    // Initially step 1 is current
    expect(screen.getByText("1")).toHaveAttribute("aria-current", "step");

    // Advance to step 2 (now renders WizardStep3)
    await user.click(screen.getByText("Next Step"));

    // Now step 2 should be current, step 1 shows checkmark
    expect(screen.getByText("2")).toHaveAttribute("aria-current", "step");
    expect(screen.getByText("\u2713")).not.toHaveAttribute("aria-current");
  });

  it("should show Step 5 content on the last step", async () => {
    const { user } = await renderWizard();

    // Navigate through all steps
    await user.click(screen.getByText("Next Step")); // → step 2
    await user.click(screen.getByText("Next Step")); // → step 3
    await user.click(screen.getByText("Next Step")); // → step 4
    await user.click(screen.getByText("Next Step")); // → step 5

    expect(screen.getByTestId("step-5")).toBeInTheDocument();
  });

  it("should show Step 5 with Complete Setup button on last step", async () => {
    // Set step to 5 before rendering
    useWizardStore.getState().setStep(5);
    await renderWizard();

    expect(screen.getByText("Complete Setup")).toBeInTheDocument();
  });
});

// --- Tests for provider-skip behaviour (hasProviders=true) ---

describe("WizardShell — skip Step 4 when providers configured", () => {
  beforeEach(() => {
    mockHasProviders = true;
  });

  it("should render only 4 step indicators when hasProviders=true", async () => {
    await renderWizard();

    // Should see step labels 1-4, NOT 5
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();

    // Label "5" should NOT exist — only 4 visual steps
    expect(screen.queryByText("5")).not.toBeInTheDocument();
  });

  it("should skip from Step 3 to Step 5 when hasProviders=true", async () => {
    const { user } = await renderWizard();

    // Step 1 → Step 2 (WizardStep3)
    await user.click(screen.getByText("Next Step"));
    expect(screen.getByTestId("step-3")).toBeInTheDocument();

    // Step 2 → Step 3 (WizardStep2)
    await user.click(screen.getByText("Next Step"));
    expect(screen.getByTestId("step-2")).toBeInTheDocument();

    // Step 3 → Step 5 (skips Step 4 entirely)
    await user.click(screen.getByText("Next Step"));
    expect(screen.getByTestId("step-5")).toBeInTheDocument();
    expect(screen.queryByTestId("step-4")).not.toBeInTheDocument();
  });

  it("should skip from Step 5 back to Step 3 when hasProviders=true", async () => {
    useWizardStore.getState().setStep(5);
    const { user } = await renderWizard();

    expect(screen.getByTestId("step-5")).toBeInTheDocument();

    // Click Back — should skip Step 4 and go directly to Step 3
    await user.click(screen.getByText("Back"));
    expect(screen.getByTestId("step-2")).toBeInTheDocument();
    expect(screen.queryByTestId("step-4")).not.toBeInTheDocument();
    expect(screen.queryByTestId("step-5")).not.toBeInTheDocument();
  });

  it("should show loading state while checking providers", () => {
    render(<WizardShell />);
    // Initially shows loading text
    expect(screen.getByText("Loading\u2026")).toBeInTheDocument();
  });

  it("should mark all steps as completed when on last step with providers", async () => {
    const { user } = await renderWizard();

    // Navigate through all 4 visual steps
    await user.click(screen.getByText("Next Step")); // → step 2
    await user.click(screen.getByText("Next Step")); // → step 3
    await user.click(screen.getByText("Next Step")); // → step 5 (skip 4)

    // All 3 previous steps should show checkmarks
    const checkmarks = screen.getAllByText("\u2713");
    expect(checkmarks).toHaveLength(3);

    // The 4th visual step (Confirm) should be active, not a checkmark
    expect(screen.getByText("Complete Setup")).toBeInTheDocument();
  });
});
