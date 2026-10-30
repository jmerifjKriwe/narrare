import { Link, Outlet } from "@tanstack/react-router";

import { settingsPages } from "@shell/lib/generated/settingsPages";
import { useTranslation } from "@shell/lib/i18n";

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
 */
export function SettingsLayout() {
  const t = useTranslation();

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("settings.heading")}</h1>
      <p className="mt-2 text-sm text-muted">
        <Link to="/" className="underline-offset-4 hover:underline">
          {t("settings.back")}
        </Link>
      </p>

      <nav
        aria-label={t("settings.heading")}
        className="mt-6 flex flex-wrap gap-2 border-b border-border pb-4"
      >
        {[...CLUSTERS, ...settingsPages].map((cluster) => (
          <Link
            key={cluster.id}
            to={cluster.path}
            className="rounded-md border border-border px-3 py-1.5 text-sm font-medium underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t(cluster.titleKey)}
          </Link>
        ))}
      </nav>

      <Outlet />
    </div>
  );
}
