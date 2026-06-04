"use client";

/**
 * KBFieldSourceBadge — Colored badge showing field value source (user/ai/world_derived/merged).
 *
 * Extracted from KBSessionFieldList for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";
import type { KBCreationField } from "@/lib/api/kb-sessions";

interface KBFieldSourceBadgeProps {
  source: KBCreationField["source"];
}

export function KBFieldSourceBadge({ source }: KBFieldSourceBadgeProps) {
  const t = useTranslations("studio");

  const badges: Record<KBCreationField["source"], { label: string; className: string }> = {
    user: {
      label: t("kb.source_user"),
      className: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400",
    },
    ai: {
      label: t("kb.source_ai"),
      className: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400",
    },
    world_derived: {
      label: t("kb.source_world_derived"),
      className: "bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400",
    },
    merged: {
      label: t("kb.source_merged"),
      className: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400",
    },
  };
  const badge = badges[source];

  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${badge.className}`}>
      {badge.label}
    </span>
  );
}
