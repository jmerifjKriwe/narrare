"use client";

/**
 * SeriesTabNav — 4-tab navigation bar for the Series workspace (Spec 1,
 * Slice 4). Uses Next.js segment-based routing:
 *   Bände    → /series/[id]          (default)
 *   Canon    → /series/[id]/canon    (placeholder — Slice 5)
 *   Settings → /series/[id]/settings (Task 4.7)
 *   Voice    → /series/[id]/voice    (DISABLED placeholder — Spec 3)
 *
 * The Voice tab is rendered as a non-navigable element (aria-disabled) so users
 * cannot route into an unbuilt feature. Extracted from SeriesWorkspace (RULE-04:
 * one responsibility per file). All copy goes through `useTranslations("studio")`
 * — no hardcoded JSX text (enforced by scripts/validate-i18n.ts).
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
      <div role="tablist" className="flex gap-1">
        {tabs.map((tab) => {
          const active = isActive(tab);
          const label = t(tab.labelKey);
          const baseClass = "border-b-2 px-4 py-3 text-sm font-medium transition-colors";
          const stateClass = active
            ? "border-blue-600 text-blue-600"
            : "border-transparent text-muted-foreground hover:text-foreground";
          const className = `${baseClass} ${stateClass} ${tab.disabled ? "cursor-not-allowed opacity-60" : ""}`;

          if (tab.disabled) {
            // Disabled placeholder tab — non-navigable so users cannot route
            // into the unbuilt Voice feature (Spec 3). tabIndex=-1 keeps it
            // out of the tab order while remaining programmatically
            // focusable (ARIA-compliant disabled-tab pattern).
            return (
              <span
                key={tab.id}
                role="tab"
                id={`series-tab-${tab.id}`}
                data-testid={`series-tab-${tab.id}`}
                data-active={active}
                tabIndex={-1}
                aria-selected={active}
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
              role="tab"
              id={`series-tab-${tab.id}`}
              data-testid={`series-tab-${tab.id}`}
              data-active={active}
              aria-selected={active}
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
