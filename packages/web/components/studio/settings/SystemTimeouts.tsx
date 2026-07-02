"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";

// --- Types ---

interface SystemTimeoutsProps {
  readonly wsTimeout: number;
  readonly onChange: (values: { ws_timeout?: number }) => void;
  readonly disabled?: boolean;
}

// --- Component ---

/**
 * System timeout configuration for AI operations.
 *
 * Only the WebSocket idle timeout is user-configurable here — it has a real
 * runtime consumer. The former `retry_max_attempts` / `retry_base_delay`
 * controls were a false surface (never reached a runtime retry boundary) and
 * were removed end-to-end per ADR-060. Transport retry is now governed by Core
 * at the provider SDK layer (`NARRARE_LLM_TRANSPORT_MAX_RETRIES`).
 */
export function SystemTimeouts({ wsTimeout, onChange, disabled }: SystemTimeoutsProps) {
  const t = useTranslations("studio");

  const handleWsTimeoutChange = useCallback(
    (raw: string) => {
      const value = parseFloat(raw);
      if (Number.isNaN(value)) return;
      if (value < 60) return;
      onChange({ ws_timeout: Math.round(value) });
    },
    [onChange],
  );

  return (
    <div className="space-y-4">
      <div>
        <label htmlFor="ws-timeout" className="block text-sm text-muted-foreground mb-1">
          {t("settings.ai.systemTimeouts.wsTimeout")}
        </label>
        <input
          id="ws-timeout"
          type="number"
          min={60}
          step={60}
          value={wsTimeout}
          onChange={(e) => handleWsTimeoutChange(e.target.value)}
          disabled={disabled}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm disabled:opacity-50"
        />
        <p className="mt-1 text-xs text-muted-foreground">
          {t("settings.ai.systemTimeouts.wsTimeoutHint")}
        </p>
      </div>
    </div>
  );
}
