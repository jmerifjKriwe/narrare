"use client";

import { useKBTotalCount } from "@/lib/hooks/useKB";

/**
 * SidebarKBBadge — KB entry-count badge shown on the worldbuilding nav item.
 *
 * Extracted from Sidebar.tsx (RULE-04).
 */

interface SidebarKBBadgeProps {
  novelId: string;
  active: boolean;
}

export function SidebarKBBadge({ novelId, active }: SidebarKBBadgeProps) {
  const kbCount = useKBTotalCount(novelId);
  if (kbCount === 0) return null;
  return (
    <span
      className={`text-xs px-1.5 py-0.5 rounded ${
        active ? "bg-primary-foreground/20" : "bg-muted text-muted-foreground"
      }`}
    >
      {kbCount}
    </span>
  );
}
