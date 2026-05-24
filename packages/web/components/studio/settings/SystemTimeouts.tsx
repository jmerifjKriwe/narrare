"use client";

import { useTranslations } from "next-intl";
import { useCallback } from "react";

// --- Types ---

interface SystemTimeoutsProps {
  readonly wsTimeout: number;
  readonly retryMaxAttempts: number;
  readonly retryBaseDelay: number;
  readonly onChange: (values: {
    ws_timeout?: number;
    retry_max_attempts?: number;
    retry_base_delay?: number;
  }) => void;
  readonly disabled?: boolean;
}

// --- Component ---

export function SystemTimeouts({
  wsTimeout,
  retryMaxAttempts,
  retryBaseDelay,
  onChange,
  disabled,
}: SystemTimeoutsProps) {
  const t = useTranslations("studio");

  const handleNumberChange = useCallback(
    (field: "ws_timeout" | "retry_max_attempts" | "retry_base_delay", raw: string) => {
      const value = parseFloat(raw);
      if (Number.isNaN(value)) return;
      if (field === "ws_timeout" && value < 60) return;
      if (field === "retry_max_attempts" && (value < 1 || value > 10)) return;
      if (field === "retry_base_delay" && (value < 0.1 || value > 30)) return;
      onChange({
        [field]: field === "retry_base_delay" ? value : Math.round(value),
      });
    },
    [onChange],
  );

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
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
            onChange={(e) => handleNumberChange("ws_timeout", e.target.value)}
            disabled={disabled}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm disabled:opacity-50"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {t("settings.ai.systemTimeouts.wsTimeoutHint")}
          </p>
        </div>
        <div>
          <label htmlFor="retry-attempts" className="block text-sm text-muted-foreground mb-1">
            {t("settings.ai.systemTimeouts.retryAttempts")}
          </label>
          <input
            id="retry-attempts"
            type="number"
            min={1}
            max={10}
            value={retryMaxAttempts}
            onChange={(e) => handleNumberChange("retry_max_attempts", e.target.value)}
            disabled={disabled}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm disabled:opacity-50"
          />
        </div>
        <div>
          <label htmlFor="retry-delay" className="block text-sm text-muted-foreground mb-1">
            {t("settings.ai.systemTimeouts.retryDelay")}
          </label>
          <input
            id="retry-delay"
            type="number"
            min={0.1}
            max={30}
            step={0.1}
            value={retryBaseDelay}
            onChange={(e) => handleNumberChange("retry_base_delay", e.target.value)}
            disabled={disabled}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm disabled:opacity-50"
          />
          <p className="mt-1 text-xs text-muted-foreground">
            {t("settings.ai.systemTimeouts.retryDelayHint")}
          </p>
        </div>
      </div>
    </div>
  );
}
