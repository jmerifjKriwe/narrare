"use client";

import { useTranslations } from "next-intl";
import type { AIDiffState } from "@/lib/ai-diff/contracts";

interface AIDiffBadgeProps {
  readonly state: AIDiffState;
}

const STATE_STYLES: Record<AIDiffState, string> = {
  suggested: "border-primary/30 bg-primary/10 text-primary",
  accepted: "border-green-500/40 bg-green-500/10 text-green-700 dark:text-green-400",
  rejected: "border-red-500/40 bg-red-500/10 text-red-700 dark:text-red-400",
  unchanged: "border-border bg-muted text-muted-foreground",
};

/**
 * Accessible state badge. The label is always visible text (never color alone),
 * using canonical `studio.aiActions.suggested` plus dedicated `studio.aiDiff.*`
 * state keys (CR-AUFG-07-18 AC #1).
 */
export function AIDiffBadge({ state }: AIDiffBadgeProps) {
  const t = useTranslations("studio");
  const label =
    state === "suggested"
      ? t("aiActions.suggested")
      : state === "accepted"
        ? t("aiDiff.accepted")
        : state === "rejected"
          ? t("aiDiff.rejected")
          : t("aiDiff.unchanged");
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${STATE_STYLES[state]}`}
    >
      {label}
    </span>
  );
}
