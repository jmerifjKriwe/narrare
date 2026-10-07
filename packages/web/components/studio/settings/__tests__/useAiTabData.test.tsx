/**
 * useAiTabData tests — budget handler payload contract (STATS-002 budgets,
 * ADR-094; review fix round 1 #6).
 *
 * Pins the PATCH payload shapes that the backend contract depends on:
 * clearing the budget must send an EXPLICIT null (`monthly_budget_usd: null`
 * — the key present, not omitted), because the pydantic contract uses
 * `number | null` with the null meaning "unset"; an omitted key would be a
 * no-op instead of a clear. Mode changes never send null (backend 422s).
 *
 * The global next-intl mock is not needed — the hook uses no translations.
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAiTabData } from "../useAiTabData";

const mockGetUserSettings = vi.fn().mockResolvedValue({
  default_provider_id: null,
  default_model: "",
  category_overrides: {},
  intent_overrides: {},
  monthly_budget_usd: "25.00",
  budget_mode: "warn",
});
const mockUpdateUserSettings = vi.fn().mockResolvedValue({});
const mockListProviders = vi.fn().mockResolvedValue([]);
const mockGetProviderModels = vi.fn().mockResolvedValue({ models: [] });
const mockGetResolved = vi.fn().mockResolvedValue({});
const mockTokenLimitsUpdateUser = vi.fn().mockResolvedValue({});

vi.mock("@/lib/api/client", () => ({
  aiSettingsApi: {
    listProviders: (...args: unknown[]) => mockListProviders(...args),
    getUserSettings: (...args: unknown[]) => mockGetUserSettings(...args),
    getProviderModels: (...args: unknown[]) => mockGetProviderModels(...args),
    updateUserSettings: (...args: unknown[]) => mockUpdateUserSettings(...args),
  },
  tokenLimitsApi: {
    getResolved: (...args: unknown[]) => mockGetResolved(...args),
    updateUser: (...args: unknown[]) => mockTokenLimitsUpdateUser(...args),
  },
}));

function renderHookWithProviders() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return renderHook(() => useAiTabData(), { wrapper });
}

describe("useAiTabData — budget handlers (STATS-002, ADR-094)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("sends an explicit null monthly_budget_usd when the budget is cleared", async () => {
    const { result } = renderHookWithProviders();

    act(() => result.current.handleMonthlyBudgetChange(null));

    await waitFor(() => expect(mockUpdateUserSettings).toHaveBeenCalledOnce());
    // Assert on the payload (call[0]; call[1] is React Query's mutation
    // context). Deep-equal pins the KEY as present with null — an omitted key
    // would be a backend no-op instead of a clear (explicit-null = unset).
    expect(mockUpdateUserSettings.mock.calls[0][0]).toEqual({ monthly_budget_usd: null });
  });

  it("sends the numeric amount when setting a budget", async () => {
    const { result } = renderHookWithProviders();

    act(() => result.current.handleMonthlyBudgetChange(30.5));

    await waitFor(() => expect(mockUpdateUserSettings).toHaveBeenCalledOnce());
    expect(mockUpdateUserSettings.mock.calls[0][0]).toEqual({ monthly_budget_usd: 30.5 });
  });

  it("sends the mode without ever sending a null budget_mode", async () => {
    const { result } = renderHookWithProviders();

    act(() => result.current.handleBudgetModeChange("block"));

    await waitFor(() => expect(mockUpdateUserSettings).toHaveBeenCalledOnce());
    const payload = mockUpdateUserSettings.mock.calls[0][0] as Record<string, unknown>;
    expect(payload).toEqual({ budget_mode: "block" });
    expect("budget_mode" in payload).toBe(true);
    expect(payload.budget_mode).not.toBeNull();
  });
});
