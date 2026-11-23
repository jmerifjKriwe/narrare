/**
 * The settings hub chrome (W8 ruling 4): the shared section nav across the
 * settings capability's own pages, ported from the owner-approved
 * `settings-ai-rules-2` draft's header — its geometry, its active face, its
 * doors. The draft draws three items; this chrome carries the two whose
 * routes exist (Allgemein, KI-Regeln): the Prompts item waits for its PR 3
 * route — a door to nowhere is a dead promise, and the hub grows the item
 * in the commit that mounts the surface behind it.
 *
 * The draft's right-hand chip („Lokaler Speicher verifiziert") is not
 * ported: it is invented chrome, a claim no read answers (the Stitch round
 * audit's finding 5).
 *
 * The active item is the route the page stands on, from the router's own
 * state — the rail's gear precedent (aria-current, the filled face).
 */
import { Link, useRouterState } from "@tanstack/react-router";

import { useTranslation } from "@shell/lib/i18n";
import { Icon, type IconName } from "@shell/ui/icons";

const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The hub's items in the draft's order, each with its glyph and its own
 *  route. A third item joins when its surface exists — never before. */
const ITEMS: ReadonlyArray<{ to: string; labelKey: "settings.hub.general" | "settings.hub.aiRules"; icon: IconName }> = [
  { to: "/settings", labelKey: "settings.hub.general", icon: "tune" },
  { to: "/settings/ai-regeln", labelKey: "settings.hub.aiRules", icon: "spark" },
];

export function SettingsHub() {
  const t = useTranslation();
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-panel p-2 shadow-sm">
      <nav aria-label={t("settings.hub.label")} className="flex items-center gap-1.5">
        {ITEMS.map((item) => {
          const active = pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              // Exact matching: `/settings` must not wear the active face on
              // `/settings/ai-regeln` (the router's prefix match would mark
              // both links aria-current on the child page — two current
              // pages is a lie the landmarks tell).
              activeOptions={{ exact: true }}
              className={`inline-flex items-center gap-2 rounded px-3 py-1.5 text-label transition-colors ${FOCUS} ${
                active
                  ? "bg-primary font-semibold text-primary-foreground shadow-sm"
                  : "text-muted hover:bg-soft hover:text-foreground"
              }`}
            >
              <Icon name={item.icon} size={16} />
              <span>{t(item.labelKey)}</span>
              {active && (
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary-foreground/70" />
              )}
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
