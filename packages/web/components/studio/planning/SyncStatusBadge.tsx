"use client";

import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";
import type { SyncStatus } from "@/types";

interface SyncStatusBadgeProps {
  status: SyncStatus;
  className?: string;
}

const STATUS_STYLES: Record<SyncStatus, string> = {
  empty: "bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400",
  planned: "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400",
  on_track: "bg-green-100 text-green-600 dark:bg-green-900/40 dark:text-green-400",
  deviated: "bg-yellow-100 text-yellow-600 dark:bg-yellow-900/40 dark:text-yellow-400",
  completed: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400",
};

const STATUS_DOTS: Record<SyncStatus, string> = {
  empty: "bg-gray-400",
  planned: "bg-blue-400",
  on_track: "bg-green-500",
  deviated: "bg-yellow-500",
  completed: "bg-emerald-500",
};

export function SyncStatusBadge({ status, className }: SyncStatusBadgeProps) {
  const t = useTranslations("studio");

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium",
        STATUS_STYLES[status],
        className,
      )}
    >
      <span className={cn("w-1.5 h-1.5 rounded-full", STATUS_DOTS[status])} aria-hidden="true" />
      {t(`storyboard.status.${status}`)}
    </span>
  );
}
