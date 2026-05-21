import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const { mockAuthApi, mockSetupApi } = vi.hoisted(() => ({
  mockAuthApi: { me: vi.fn() },
  mockSetupApi: { complete: vi.fn() },
}));

vi.mock("@/lib/api/client", () => ({
  authApi: mockAuthApi,
  setupApi: mockSetupApi,
}));

vi.mock("@/lib/stores/wizardStore", () => ({
  useWizardStore: vi.fn((selector?: (s: Record<string, unknown>) => unknown) => {
    const state = {
      currentStep: 1,
      nextStep: vi.fn(),
      prevStep: vi.fn(),
      reset: vi.fn(),
      setStep: vi.fn(),
      state: { locale: "en", theme: "neutral", writing_language: "en" },
    };
    return selector ? selector(state) : state;
  }),
}));

import { WizardShell } from "@/components/studio/wizard/WizardShell";

describe("WizardShell", () => {
  it("shows loading state while checking providers", () => {
    // Make authApi.me() return a promise that never resolves to keep loading state
    mockAuthApi.me.mockReturnValue(new Promise(() => {}));
    render(<WizardShell />);
    expect(screen.getByText(/loading/i)).toBeDefined();
  });
});
