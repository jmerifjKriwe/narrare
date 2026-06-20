/**
 * TokenMetadataWarnings tests — CR-08 P1 D5/D6 calibration & suitability UI.
 *
 * Stale/offline/unknown/invalid metadata must render a warning and must NOT
 * look calibrated. Provider-too-small and other suitability findings render
 * from the suitability.issues payload.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { TokenMetadataWarnings } from "@/components/studio/settings/TokenMetadataWarnings";
import type { CalibrationMetadata, SuitabilityMetadata } from "@/types";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function calibration(overrides: Partial<CalibrationMetadata> = {}): CalibrationMetadata {
  return {
    provider: "openai",
    model_id: "gpt-test",
    status: "known_fresh",
    source: "models.dev",
    provider_max_output_tokens: 4096,
    context_window_tokens: 128000,
    source_timestamp: 1700000000,
    cache_age_seconds: 10,
    detail: null,
    ...overrides,
  };
}

function suitability(overrides: Partial<SuitabilityMetadata> = {}): SuitabilityMetadata {
  return {
    intent: "summary",
    output_profile: "balanced",
    requested_output_tokens: 2000,
    effective_output_tokens: 2000,
    recommended_output_tokens: 2000,
    minimum_viable_output_tokens: 512,
    calibration_status: "known_fresh",
    provider_max_output_tokens: 4096,
    severity: "advisory",
    is_allowed: true,
    issues: [],
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("TokenMetadataWarnings", () => {
  it("renders nothing when no metadata is available", () => {
    const { container } = render(<TokenMetadataWarnings calibration={null} suitability={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a calibrated indicator for known_fresh metadata with no issues", () => {
    render(<TokenMetadataWarnings calibration={calibration()} suitability={null} />);
    expect(screen.getByTestId("token-calibrated")).toBeDefined();
  });

  it("renders a stale warning and NOT a calibrated indicator for known_stale", () => {
    render(
      <TokenMetadataWarnings
        calibration={calibration({ status: "known_stale" })}
        suitability={null}
      />,
    );
    expect(screen.getByText("tokenWarnings.calibrationStale")).toBeDefined();
    expect(screen.queryByTestId("token-calibrated")).toBeNull();
  });

  it("renders an unknown warning and NOT a calibrated indicator for unknown_model", () => {
    render(
      <TokenMetadataWarnings
        calibration={calibration({ status: "unknown_model" })}
        suitability={null}
      />,
    );
    expect(screen.getByText("tokenWarnings.calibrationUnknown")).toBeDefined();
    expect(screen.queryByTestId("token-calibrated")).toBeNull();
  });

  it("renders an offline warning and NOT a calibrated indicator for offline_no_cache", () => {
    render(
      <TokenMetadataWarnings
        calibration={calibration({ status: "offline_no_cache" })}
        suitability={null}
      />,
    );
    expect(screen.getByText("tokenWarnings.calibrationOffline")).toBeDefined();
    expect(screen.queryByTestId("token-calibrated")).toBeNull();
  });

  it("renders an invalid warning and NOT a calibrated indicator for invalid_metadata", () => {
    render(
      <TokenMetadataWarnings
        calibration={calibration({ status: "invalid_metadata" })}
        suitability={null}
      />,
    );
    expect(screen.getByText("tokenWarnings.calibrationInvalid")).toBeDefined();
    expect(screen.queryByTestId("token-calibrated")).toBeNull();
  });

  it("renders the provider-too-small warning from suitability issues", () => {
    render(
      <TokenMetadataWarnings
        calibration={calibration()}
        suitability={suitability({
          severity: "hard_block",
          is_allowed: false,
          provider_max_output_tokens: 128,
          issues: [
            {
              severity: "hard_block",
              code: "provider_cap_below_minimum_floor",
              message: "server message",
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("tokenWarnings.providerTooSmall")).toBeDefined();
    // A hard block must not show the friendly calibrated badge.
    expect(screen.queryByTestId("token-calibrated")).toBeNull();
  });

  it("renders a requested-cap warning from suitability issues", () => {
    render(
      <TokenMetadataWarnings
        calibration={calibration()}
        suitability={suitability({
          severity: "warning",
          issues: [
            {
              severity: "warning",
              code: "provider_cap_below_requested",
              message: "server message",
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("tokenWarnings.providerCapBelowRequested")).toBeDefined();
  });

  it("falls back to the server message for unknown issue codes", () => {
    render(
      <TokenMetadataWarnings
        calibration={calibration()}
        suitability={suitability({
          issues: [
            {
              severity: "advisory",
              code: "some_future_code",
              message: "Future server message",
            },
          ],
        })}
      />,
    );
    expect(screen.getByText("Future server message")).toBeDefined();
  });
});
