"use client";

/**
 * WikiStatusDot — Shared status indicator for wiki panels.
 *
 * Used by WikiOverviewPanel and WikiChapterSummaryPanel.
 */

interface WikiStatusDotProps {
  status: "fresh" | "stale" | "pending";
  size?: "sm" | "md";
}

export function WikiStatusDot({ status, size = "md" }: WikiStatusDotProps) {
  const colorMap = {
    fresh: "bg-green-500",
    stale: "bg-yellow-500",
    pending: "bg-gray-400",
  };
  const sizeClass = size === "sm" ? "w-2 h-2" : "w-2.5 h-2.5";

  return <span className={`inline-block ${sizeClass} rounded-full ${colorMap[status]}`} />;
}
