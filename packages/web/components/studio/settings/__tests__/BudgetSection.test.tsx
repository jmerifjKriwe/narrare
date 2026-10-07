/**
 * BudgetSection tests (STATS-002 budgets, ADR-094).
 *
 * The global next-intl mock returns raw keys, so label/error assertions read
 * like i18n keys. Handlers are mocks — the useAiTabData wiring is covered by
 * AiTab.test and the api layer by lib/api tests.
 */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { UserAiSettings } from "@/types";
import { BudgetSection } from "../BudgetSection";

function makeSettings(overrides: Partial<UserAiSettings> = {}): UserAiSettings {
  return {
    user_id: "u1",
    default_provider_id: null,
    default_model: "",
    category_overrides: {},
    intent_overrides: {},
    monthly_budget_usd: null,
    budget_mode: "warn",
    updated_at: "2026-10-01T00:00:00Z",
    ...overrides,
  };
}

describe("BudgetSection", () => {
  const onBudgetChange = vi.fn();
  const onBudgetModeChange = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders the amount input and mode select from the persisted settings", () => {
    render(
      <BudgetSection
        aiSettings={makeSettings({ monthly_budget_usd: "25.00", budget_mode: "block" })}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    const amount = screen.getByLabelText("settings.ai.budget.amountLabel") as HTMLInputElement;
    expect(amount.value).toBe("25.00");

    const mode = screen.getByLabelText("settings.ai.budget.modeLabel") as HTMLSelectElement;
    expect(mode.value).toBe("block");
  });

  it("falls back to an empty amount and warn mode when settings are not loaded yet", () => {
    render(
      <BudgetSection
        aiSettings={undefined}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    const amount = screen.getByLabelText("settings.ai.budget.amountLabel") as HTMLInputElement;
    expect(amount.value).toBe("");
    const mode = screen.getByLabelText("settings.ai.budget.modeLabel") as HTMLSelectElement;
    expect(mode.value).toBe("warn");
  });

  it("commits a valid amount on blur as a number", async () => {
    const user = userEvent.setup();
    render(
      <BudgetSection
        aiSettings={makeSettings()}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    const amount = screen.getByLabelText("settings.ai.budget.amountLabel");
    await user.clear(amount);
    await user.type(amount, "30.5");
    await user.tab();

    expect(onBudgetChange).toHaveBeenCalledOnce();
    expect(onBudgetChange).toHaveBeenCalledWith(30.5);
  });

  it("commits on Enter without firing blur twice", async () => {
    const user = userEvent.setup();
    render(
      <BudgetSection
        aiSettings={makeSettings()}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    const amount = screen.getByLabelText("settings.ai.budget.amountLabel");
    await user.type(amount, "12{Enter}");

    expect(onBudgetChange).toHaveBeenCalledOnce();
    expect(onBudgetChange).toHaveBeenCalledWith(12);
  });

  it("commits an empty field as null (clearing the budget)", async () => {
    const user = userEvent.setup();
    render(
      <BudgetSection
        aiSettings={makeSettings({ monthly_budget_usd: "25.00" })}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    const amount = screen.getByLabelText("settings.ai.budget.amountLabel");
    await user.clear(amount);
    await user.tab();

    expect(onBudgetChange).toHaveBeenCalledOnce();
    expect(onBudgetChange).toHaveBeenCalledWith(null);
  });

  it.each(["-5", "abc", "1.234"])(
    "rejects %s and shows the validation hint without saving",
    async (raw) => {
      const user = userEvent.setup();
      render(
        <BudgetSection
          aiSettings={makeSettings()}
          onBudgetChange={onBudgetChange}
          onBudgetModeChange={onBudgetModeChange}
        />,
      );

      const amount = screen.getByLabelText("settings.ai.budget.amountLabel");
      await user.type(amount, raw);
      await user.tab();

      expect(onBudgetChange).not.toHaveBeenCalled();
      expect(screen.getByText("settings.ai.budget.amountInvalid")).toBeInTheDocument();
    },
  );

  it("clears the validation hint once a valid amount is committed", async () => {
    const user = userEvent.setup();
    render(
      <BudgetSection
        aiSettings={makeSettings()}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    const amount = screen.getByLabelText("settings.ai.budget.amountLabel");
    await user.type(amount, "-5");
    await user.tab();
    expect(screen.getByText("settings.ai.budget.amountInvalid")).toBeInTheDocument();

    await user.clear(amount);
    await user.type(amount, "10");
    await user.tab();

    expect(onBudgetChange).toHaveBeenLastCalledWith(10);
    expect(screen.queryByText("settings.ai.budget.amountInvalid")).not.toBeInTheDocument();
  });

  it("does not fire the mutation when blurring without changes (no phantom PATCH / accidental clear)", async () => {
    const user = userEvent.setup();
    render(
      <BudgetSection
        aiSettings={makeSettings({ monthly_budget_usd: "25.00" })}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    const amount = screen.getByLabelText("settings.ai.budget.amountLabel");
    await user.click(amount);
    await user.tab();

    expect(onBudgetChange).not.toHaveBeenCalled();
    expect(onBudgetModeChange).not.toHaveBeenCalled();
  });

  it.each(["warn", "block"] as const)("mode select reports %s changes", async (mode) => {
    const user = userEvent.setup();
    render(
      <BudgetSection
        aiSettings={makeSettings()}
        onBudgetChange={onBudgetChange}
        onBudgetModeChange={onBudgetModeChange}
      />,
    );

    await user.selectOptions(screen.getByLabelText("settings.ai.budget.modeLabel"), mode);

    expect(onBudgetModeChange).toHaveBeenCalledOnce();
    expect(onBudgetModeChange).toHaveBeenCalledWith(mode);
  });
});
