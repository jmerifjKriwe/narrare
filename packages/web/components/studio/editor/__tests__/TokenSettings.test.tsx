/**
 * TokenSettings tests — CR-08 P1 frontend contract.
 *
 * The Backend update endpoints persist token-limit changes with 204/no-body.
 * The compact editor control must therefore refetch resolved limits after a
 * successful write instead of treating the write as a full TokenLimitsResponse.
 */

import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { TokenSettings } from "../TokenSettings";

const { baseSettings, mockGetResolved, mockUpdateUser } = vi.hoisted(() => ({
  baseSettings: {
    output_limit: 2000,
    token_profile: "balanced",
    effective_output_limit: 2000,
    tier_percentages: {
      immediate: 0.3,
      recent: 0.2,
      kb_referenced: 0.25,
      kb_suggested: 0.15,
      pinned: 0.1,
    },
    ws_timeout: 1800,
    retry_max_attempts: 3,
    retry_base_delay: 1.0,
    metadata: {
      catalogue: [
        { value: "quick", preset_output_limit: 500, is_custom: false },
        { value: "balanced", preset_output_limit: 2000, is_custom: false },
        { value: "long_texts", preset_output_limit: 8000, is_custom: false },
        { value: "comprehensive", preset_output_limit: 16000, is_custom: false },
        { value: "custom", preset_output_limit: null, is_custom: true },
      ],
      absolute_max: 131072,
      ux_recommended_max: 16000,
    },
    calibration: null,
    suitability: null,
  },
  mockGetResolved: vi.fn(),
  mockUpdateUser: vi.fn(),
}));

vi.mock("@/lib/api/client", () => ({
  tokenLimitsApi: {
    getResolved: (...args: unknown[]) => mockGetResolved(...args),
    updateUser: (...args: unknown[]) => mockUpdateUser(...args),
  },
}));

describe("TokenSettings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetResolved.mockResolvedValue(baseSettings);
    // Backend writes return 204/no body; fetchApi resolves this as undefined.
    mockUpdateUser.mockResolvedValue(undefined);
  });

  it("renders exactly the five public token profile values", async () => {
    render(<TokenSettings />);

    const select = await screen.findByLabelText("tokenSettings.profile");
    const optionValues = Array.from((select as HTMLSelectElement).options).map(
      (option) => option.value,
    );

    expect(optionValues).toEqual(["quick", "balanced", "long_texts", "comprehensive", "custom"]);
    expect(optionValues).not.toContain("conservative");
  });

  it("keeps controls visible after a 204 profile update by refetching resolved limits", async () => {
    const user = userEvent.setup();
    render(<TokenSettings />);

    const select = await screen.findByLabelText("tokenSettings.profile");
    await user.selectOptions(select, "quick");

    await waitFor(() => {
      expect(mockUpdateUser).toHaveBeenCalledWith({ token_profile: "quick" });
      expect(mockGetResolved).toHaveBeenCalledTimes(2);
    });
    expect(screen.getByLabelText("tokenSettings.profile")).toBeDefined();
  });

  it("persists custom raw output limits above 16k and refetches after the 204 write", async () => {
    const user = userEvent.setup();
    render(<TokenSettings />);

    const input = (await screen.findByLabelText(
      "tokenSettings.customOutputLimit",
    )) as HTMLInputElement;
    expect(input.max).toBe("131072");

    await user.clear(input);
    await user.type(input, "64000");
    await user.tab();

    await waitFor(() => {
      expect(mockUpdateUser).toHaveBeenCalledWith({ token_profile: "custom", output_limit: 64000 });
      expect(mockGetResolved).toHaveBeenCalledTimes(2);
    });
  });
});
