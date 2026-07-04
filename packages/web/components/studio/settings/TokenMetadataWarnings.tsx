"use client";

/**
 * TokenMetadataWarnings — CR-08 P1 D5/D6 calibration & suitability UI.
 *
 * Renders explicit warning labels for stale / offline / unknown / invalid
 * calibration and for suitability findings (provider-too-small, requested-cap,
 * context-too-small, capability). Stale/offline/unknown/invalid states must
 * NEVER look calibrated — only `known_fresh` with no blocking findings shows
 * a calibrated indicator.
 *
 * Pure presentational component: props in, warnings out. The warning list is
 * derived from the API `calibration` / `suitability` metadata payloads.
 */

import { AlertTriangle, ShieldAlert, ShieldCheck } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo } from "react";
import type { CalibrationMetadata, SuitabilityIssue, SuitabilityMetadata } from "@/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type WarningTone = "info" | "warning" | "danger";

interface WarningDescriptor {
  readonly id: string;
  readonly tone: WarningTone;
  /** i18n label key under the `tokenWarnings` namespace, or null to use text. */
  readonly labelKey: string | null;
  /** Literal fallback text (used when labelKey is null). */
  readonly text: string;
}

interface TokenMetadataWarningsProps {
  readonly calibration: CalibrationMetadata | null;
  readonly suitability: SuitabilityMetadata | null;
}

// ---------------------------------------------------------------------------
// Static maps (mirror Core/backend codes; parity via contract tests)
// ---------------------------------------------------------------------------

/** Calibration status → i18n key. `known_fresh` is intentionally absent. */
const CALIBRATION_WARNING_KEYS: Partial<Record<string, string>> = {
  known_stale: "tokenWarnings.calibrationStale",
  unknown_model: "tokenWarnings.calibrationUnknown",
  offline_no_cache: "tokenWarnings.calibrationOffline",
  invalid_metadata: "tokenWarnings.calibrationInvalid",
};

/** Suitability issue code → i18n key. Unknown codes fall back to server message. */
const SUITABILITY_CODE_KEYS: Record<string, string> = {
  calibration_known_stale: "tokenWarnings.calibrationStale",
  calibration_unknown_model: "tokenWarnings.calibrationUnknown",
  calibration_offline_no_cache: "tokenWarnings.calibrationOffline",
  calibration_invalid_metadata: "tokenWarnings.calibrationInvalid",
  provider_cap_below_minimum_floor: "tokenWarnings.providerTooSmall",
  provider_cap_below_requested: "tokenWarnings.providerCapBelowRequested",
  context_window_below_required_floor: "tokenWarnings.contextTooSmall",
  capability_unknown: "tokenWarnings.capabilityUnknown",
  capability_below_recommendation: "tokenWarnings.capabilityBelowRecommendation",
};

const SEVERITY_TONE: Record<string, WarningTone> = {
  advisory: "info",
  warning: "warning",
  hard_block: "danger",
};

const TONE_STYLES: Record<WarningTone, string> = {
  info: "border-blue-500/40 bg-blue-500/10 text-blue-600",
  warning: "border-amber-500/40 bg-amber-500/10 text-amber-600",
  danger: "border-red-500/40 bg-red-500/10 text-red-600",
};

// ---------------------------------------------------------------------------
// Pure derivation (exported for potential unit testing)
// ---------------------------------------------------------------------------

/**
 * Build the ordered warning list from calibration + suitability metadata.
 *
 * When `suitability` is present its issues are authoritative (they already
 * include calibration-derived findings). Otherwise a single warning is
 * derived from `calibration.status` so the settings page — which may request
 * provider/model without an intent — still surfaces stale/offline evidence.
 */
export function collectTokenWarnings(
  calibration: CalibrationMetadata | null,
  suitability: SuitabilityMetadata | null,
): WarningDescriptor[] {
  const descriptors: WarningDescriptor[] = [];

  if (suitability) {
    for (const issue of suitability.issues) {
      descriptors.push(issueToDescriptor(issue));
    }
  } else if (calibration) {
    const labelKey = CALIBRATION_WARNING_KEYS[calibration.status];
    if (labelKey) {
      descriptors.push({
        id: `calibration-${calibration.status}`,
        tone: "warning",
        labelKey,
        text: calibration.status,
      });
    }
  }

  return descriptors;
}

function issueToDescriptor(issue: SuitabilityIssue): WarningDescriptor {
  const labelKey = SUITABILITY_CODE_KEYS[issue.code] ?? null;
  return {
    id: `suitability-${issue.code}`,
    tone: SEVERITY_TONE[issue.severity] ?? "warning",
    labelKey,
    text: issue.message,
  };
}

/** True only when calibration is fresh and there are no blocking/warning findings. */
function isCalibrated(
  calibration: CalibrationMetadata | null,
  suitability: SuitabilityMetadata | null,
): boolean {
  if (calibration?.status !== "known_fresh") return false;
  if (suitability) {
    return suitability.issues.every((i) => i.severity === "advisory");
  }
  return true;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TokenMetadataWarnings({ calibration, suitability }: TokenMetadataWarningsProps) {
  const t = useTranslations("studio");

  const warnings = useMemo(
    () => collectTokenWarnings(calibration, suitability),
    [calibration, suitability],
  );

  const calibrated = isCalibrated(calibration, suitability);

  if (warnings.length === 0 && !calibrated) {
    return null;
  }

  return (
    <div className="space-y-2" data-testid="token-metadata-warnings">
      {calibrated && (
        <div
          data-testid="token-calibrated"
          className="flex items-center gap-2 rounded-md border border-green-500/40 bg-green-500/10 px-3 py-2 text-sm text-green-600"
        >
          <ShieldCheck className="h-4 w-4 shrink-0" aria-hidden="true" />
          <span>{t("tokenWarnings.calibrated")}</span>
        </div>
      )}
      {warnings.map((w) => (
        <div
          key={w.id}
          role="status"
          data-testid={`token-warning-${w.id}`}
          className={`flex items-start gap-2 rounded-md border px-3 py-2 text-sm ${TONE_STYLES[w.tone]}`}
        >
          {w.tone === "danger" ? (
            <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          ) : (
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
          )}
          <span>{w.labelKey ? t(w.labelKey) : w.text}</span>
        </div>
      ))}
    </div>
  );
}
