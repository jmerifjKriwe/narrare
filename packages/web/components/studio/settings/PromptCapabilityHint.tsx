"use client";

import { Info } from "lucide-react";
import { useTranslations } from "next-intl";

/**
 * PromptCapabilityHint — CR-AUFG-07-30 capability-basis transparency banner.
 *
 * Guaranteed capabilities (Narrare identity, observability, security) always
 * apply and cannot be overridden via the cascade — this banner surfaces that
 * architectural guarantee to the user. It is intentionally not dismissible and
 * stays visible in both simple and expert editor modes (CR-AUFG-07-36).
 *
 * Extracted from :component:`PromptEditor` to keep that orchestrator under the
 * RULE-04 line limit.
 */
export function PromptCapabilityHint() {
  const t = useTranslations("studio");

  return (
    <div className="flex items-start gap-2 rounded-md border border-blue-500/20 bg-blue-500/5 p-3 text-sm text-muted-foreground">
      <Info className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
      <div>
        <p className="font-medium text-foreground">{t("settings.prompts.capabilityHintTitle")}</p>
        <p className="mt-0.5">{t("settings.prompts.capabilityHintBody")}</p>
      </div>
    </div>
  );
}
