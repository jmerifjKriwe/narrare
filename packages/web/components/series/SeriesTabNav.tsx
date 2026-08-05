"use client";

/**
 * SeriesTabNav — 4-tab navigation bar for the Series workspace (Spec 1,
 * Slice 4). Uses Next.js segment-based routing:
 *   Bände    → /series/[id]          (default)
 *   Canon    → /series/[id]/canon    (Slice 5)
 *   Settings → /series/[id]/settings (Task 4.7)
 *   Voice    → /series/[id]/voice    (Spec 3, Tasks 5–6 — now navigable)
 *
 * I-F5: these are ROUTE-NAVIGATION LINKS, not ARIA tabs. ARIA `tablist`/`tab`
 * imply an in-page tab panel contract (arrow-key roving, `aria-controls`/
 * `aria-selected`, single `tabindex` management) that these route links do not
 * honour. Using plain links inside a `<nav>` (with `aria-current="page"` on the
 * active route) is the semantically correct pattern for navigation.
 *
 * Extracted from SeriesWorkspace (RULE-04: one responsibility per file). All
 * copy goes through `useTranslations("studio")` — no hardcoded JSX text
 * (enforced by scripts/validate-i18n.ts).
 */
import type { Route } from "next";
import Link from "next/link";
import { useTranslations } from "next-intl";

type TabId = "baende" | "canon" | "settings" | "voice";

interface TabDef {
  readonly id: TabId;
  readonly href: string;
  readonly labelKey: string;
}

interface SeriesTabNavProps {
  readonly seriesId: string;
  readonly pathname: string;
}

export function SeriesTabNav({ seriesId, pathname }: SeriesTabNavProps) {
  const t = useTranslations("studio");
  const basePath = `/series/${seriesId}`;

  const tabs: readonly TabDef[] = [
    { id: "baende", href: basePath, labelKey: "series.workspace.tabs.baende" },
    { id: "canon", href: `${basePath}/canon`, labelKey: "series.workspace.tabs.canon" },
    { id: "settings", href: `${basePath}/settings`, labelKey: "series.workspace.tabs.settings" },
    { id: "voice", href: `${basePath}/voice`, labelKey: "series.workspace.tabs.voice" },
  ];

  function isActive(tab: TabDef): boolean {
    // The default (Bände) tab lives exactly at the base path — a startsWith
    // check would wrongly mark it active on every sub-route.
    if (tab.id === "baende") return pathname === basePath;
    return pathname === tab.href || pathname.startsWith(`${tab.href}/`);
  }

  return (
    <nav aria-label={t("series.workspace.tabsLabel")} className="border-b px-6">
      <div className="flex gap-1">
        {tabs.map((tab) => {
          const active = isActive(tab);
          const label = t(tab.labelKey);
          const className = active
            ? "border-b-2 border-accent-series px-4 py-3 text-sm font-medium text-accent-series transition-colors"
            : "border-b-2 border-transparent px-4 py-3 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground";

          return (
            <Link
              key={tab.id}
              href={tab.href as Route}
              data-testid={`series-tab-${tab.id}`}
              aria-current={active ? "page" : undefined}
              className={className}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
