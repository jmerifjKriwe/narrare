"use client";

/**
 * SeriesTabNav — 4-tab navigation bar for the Series workspace (Spec 1,
 * Slice 4). Uses Next.js segment-based routing:
 *   Bände    → /series/[id]          (default)
 *   Canon    → /series/[id]/canon    (placeholder — Slice 5)
 *   Settings → /series/[id]/settings (Task 4.7)
 *   Voice    → /series/[id]/voice    (DISABLED placeholder — Spec 3)
 *
 * I-F5: these are ROUTE-NAVIGATION LINKS, not ARIA tabs. ARIA `tablist`/`tab`
 * imply an in-page tab panel contract (arrow-key roving, `aria-controls`/
 * `aria-selected`, single `tabindex` management) that these route links do not
 * honour. Using plain links inside a `<nav>` (with `aria-current="page"` on the
 * active route) is the semantically correct pattern for navigation. The Voice
 * tab is rendered as a non-navigable element (`aria-disabled`) so users cannot
 * route into an unbuilt feature.
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
  readonly disabled: boolean;
}

interface SeriesTabNavProps {
  readonly seriesId: string;
  readonly pathname: string;
}

export function SeriesTabNav({ seriesId, pathname }: SeriesTabNavProps) {
  const t = useTranslations("studio");
  const basePath = `/series/${seriesId}`;

  const tabs: readonly TabDef[] = [
    { id: "baende", href: basePath, labelKey: "series.workspace.tabs.baende", disabled: false },
    {
      id: "canon",
      href: `${basePath}/canon`,
      labelKey: "series.workspace.tabs.canon",
      disabled: false,
    },
    {
      id: "settings",
      href: `${basePath}/settings`,
      labelKey: "series.workspace.tabs.settings",
      disabled: false,
    },
    {
      id: "voice",
      href: `${basePath}/voice`,
      labelKey: "series.workspace.tabs.voice",
      disabled: true,
    },
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
          const baseClass = "border-b-2 px-4 py-3 text-sm font-medium transition-colors";
          const stateClass = active
            ? "border-accent-series text-accent-series"
            : "border-transparent text-muted-foreground hover:text-foreground";
          const className = `${baseClass} ${stateClass} ${tab.disabled ? "cursor-not-allowed opacity-60" : ""}`;

          if (tab.disabled) {
            // Disabled placeholder — non-navigable so users cannot route into
            // the unbuilt Voice feature (Spec 3).
            return (
              <span
                key={tab.id}
                data-testid={`series-tab-${tab.id}`}
                aria-disabled="true"
                className={className}
              >
                {label}
                <span className="ml-1 text-xs font-normal">
                  {`(${t("series.workspace.comingInSpec3")})`}
                </span>
              </span>
            );
          }

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
