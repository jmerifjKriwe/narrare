import type { LucideIcon } from "lucide-react";
import { type KeyboardEvent, useId } from "react";
import { cn } from "@/lib/utils";

interface TabItem {
  readonly id: string;
  /** Resolved i18n label (RULE-16 — never hardcoded inside the primitive). */
  readonly label: string;
  /** Optional decorative leading icon (rendered aria-hidden). */
  readonly icon?: LucideIcon;
  readonly content: React.ReactNode;
}

interface PanelTabsProps {
  readonly tabs: readonly TabItem[];
  /** Controlled active tab id. */
  readonly value: string;
  readonly onValueChange: (id: string) => void;
  /** Accessible name for the tablist grouping (resolved i18n). */
  readonly ariaLabel: string;
}

/**
 * URL-addressable tab list (spec §5.4, Phase C §8.1). Implements the WAI-ARIA
 * tabs pattern: `tablist`/`tab`/`tabpanel` roles, `aria-selected`, mutual
 * `aria-controls`/`aria-labelledby` linking, roving tabindex (active tab is
 * `0`, others `-1`) and arrow-key + Home/End navigation.
 *
 * Presentation only (RULE-13). Controlled — the caller binds `value`/
 * `onValueChange` to `useUrlParam` (one adapter per surface) or any local
 * state source. No hardcoded user-facing strings: `label` and `ariaLabel` are
 * required resolved-i18n props (RULE-16).
 */
export function PanelTabs({ tabs, value, onValueChange, ariaLabel }: PanelTabsProps) {
  const baseId = useId();
  const activeIndex = Math.max(
    0,
    tabs.findIndex((t) => t.id === value),
  );
  const active = tabs[activeIndex];

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    let next = activeIndex;
    if (e.key === "ArrowRight") next = (activeIndex + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (activeIndex - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    else return;
    e.preventDefault();
    onValueChange(tabs[next].id);
  };

  return (
    <div className="flex h-full flex-col">
      <div
        role="tablist"
        aria-label={ariaLabel}
        onKeyDown={onKeyDown}
        className="flex border-b border-border"
      >
        {tabs.map((tab) => {
          const selected = tab.id === value;
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              type="button"
              role="tab"
              id={`${baseId}-tab-${tab.id}`}
              aria-controls={`${baseId}-panel-${tab.id}`}
              aria-selected={selected}
              tabIndex={selected ? 0 : -1}
              onClick={() => onValueChange(tab.id)}
              className={cn(
                "inline-flex items-center gap-1.5 px-3 py-2 text-sm transition-colors",
                "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring",
                selected
                  ? "border-b-2 border-primary text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {Icon && <Icon aria-hidden="true" className="h-4 w-4" />}
              {tab.label}
            </button>
          );
        })}
      </div>
      {/*
        No tabindex on the tabpanel: per the WAI-ARIA tabs pattern, a panel is
        only placed in the tab order when it has no focusable descendants.
        PanelTabs renders arbitrary content (often containing focusable
        controls), so keyboard users reach those children directly and screen
        readers reach the panel via the active tab's aria-controls.
      */}
      <div
        role="tabpanel"
        id={`${baseId}-panel-${active.id}`}
        aria-labelledby={`${baseId}-tab-${active.id}`}
        className="min-h-0 flex-1 overflow-auto"
      >
        {active.content}
      </div>
    </div>
  );
}
