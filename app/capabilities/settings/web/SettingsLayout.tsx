import { Link, Outlet } from "@tanstack/react-router";

import { settingsPages } from "@shell/lib/generated/settingsPages";
import { useTranslation } from "@shell/lib/i18n";
import { rowClass } from "@shell/ui/Row";

/**
 * The area's own clusters, in the order the nav and the hub show them.
 * Contributed pages join both from the generated registry — a new cluster
 * appears here without an edit to this file.
 */
export const CLUSTERS = [
  {
    id: "language",
    path: "/settings/language",
    titleKey: "settings.clusterLanguage",
    descriptionKey: "settings.clusterLanguage.description",
  },
  {
    id: "provider",
    path: "/settings/provider",
    titleKey: "settings.clusterProvider",
    descriptionKey: "settings.clusterProvider.description",
  },
] as const;

/**
 * The settings area's frame: the title, the way back, the cluster nav — its
 * own two clusters plus every page the registry contributes — and the outlet
 * the hub and the sub-pages render into. The frame is what makes /settings
 * an area: every page of it shows the same doors.
 *
 * The shape is nav 200 + content 56 rem under the 1000 px cap: from md the
 * nav is the area's own narrow column and the pages keep their measure; on a
 * phone the column stacks above them. The nav is a vertical row list — the
 * cluster links wear `rowClass`, the L2 current treatment rides
 * `aria-current` through the attribute selector (the IconRail precedent: the
 * paint can only agree with the semantics the router sets). These are links,
 * so React Aria stays out — a destination is an anchor's job.
 */
export function SettingsLayout() {
  const t = useTranslation();

  return (
    <div className="mx-auto max-w-[1000px] px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("settings.heading")}</h1>
      <p className="mt-2 text-body text-muted">
        <Link
          to="/"
          className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("settings.back")}
        </Link>
      </p>

      <div className="mt-6 md:grid md:grid-cols-[200px_minmax(0,56rem)] md:gap-8">
        <nav aria-label={t("settings.heading")} className="flex flex-col">
          {[...CLUSTERS, ...settingsPages].map((cluster) => (
            <Link
              key={cluster.id}
              to={cluster.path}
              className={`${rowClass(false, true)} last:border-b-0 aria-[current=page]:bg-soft aria-[current=page]:font-semibold aria-[current=page]:shadow-[inset_2px_0_0_var(--primary)]`}
            >
              {t(cluster.titleKey)}
            </Link>
          ))}
        </nav>

        {/* The wrapper keeps multi-root pages in this column: an Outlet's
            fragment children are grid items of their own, and from the
            second one on they auto-place into the nav's cell. `min-w-0`
            lets long content shrink inside the minmax track; `mt-6` holds
            the mobile stack's seam that the nav's removed last-row rule
            used to hold (md resets it — the column gap takes over).
            The frame also owns the page's shape: this container and the
            area's single <h1> above are its, so a contributed settings
            page brings sections under an <h2> and no container or <h1>
            of its own — a second of either double-insets the area or
            hands a screen reader two page titles. */}
        <div className="min-w-0 mt-6 md:mt-0">
          <Outlet />
        </div>
      </div>
    </div>
  );
}
