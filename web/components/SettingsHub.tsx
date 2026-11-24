/**
 * The settings hub chrome (W8 ruling 4): the shared section nav across the
 * settings area's pages, ported from the owner-approved
 * `settings-ai-rules-2` draft's header — its geometry, its active face, its
 * doors. It lives in the shell (`web/components/`) since W8 PR 3: the area's
 * three authorities span two capabilities (Allgemein and KI-Regeln belong to
 * `settings`, Prompts to `prompts`), and a capability never imports another
 * (rule 1) — the shared chrome is the shell's, each page renders it above
 * its own content. Its labels live in the shared catalogs (`i18n/`) for the
 * same reason: the chrome's text has no capability owner.
 *
 * The draft draws three items; all three routes exist (the Prompts surface
 * joined in PR 3, the commit this item's door went live in — the door and
 * the surface behind it land together, never a door to nowhere).
 *
 * The draft's right-hand chip („Lokaler Speicher verifiziert") is not
 * ported: it is invented chrome, a claim no read answers (the Stitch round
 * audit's finding 5).
 *
 * The active item is the route the page stands on, from the router's own
 * state — the rail's gear precedent (aria-current, the filled face).
 */
import { Link, useRouterState } from "@tanstack/react-router";

import { useTranslation } from "../lib/i18n";
import { Icon, type IconName } from "../ui/icons";

const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The hub's items in the draft's order, each with its glyph and its own
 *  route. */
const ITEMS: ReadonlyArray<{
  to: string;
  labelKey: "shell.hub.general" | "shell.hub.aiRules" | "shell.hub.prompts";
  icon: IconName;
}> = [
  { to: "/settings", labelKey: "shell.hub.general", icon: "tune" },
  { to: "/settings/ai-regeln", labelKey: "shell.hub.aiRules", icon: "spark" },
  { to: "/settings/prompts", labelKey: "shell.hub.prompts", icon: "document" },
];

export function SettingsHub() {
  const t = useTranslation();
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  return (
    <header className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-panel p-2 shadow-sm">
      <nav aria-label={t("shell.hub.label")} className="flex items-center gap-1.5">
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
