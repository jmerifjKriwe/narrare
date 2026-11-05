import { Link } from "@tanstack/react-router";

import { settingsPages } from "@shell/lib/generated/settingsPages";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";

import { CLUSTERS } from "./SettingsLayout";

/**
 * The hub, the area's landing: one door per cluster — the two settings owns,
 * then every page the registry contributes — so the gear's click names all
 * of the area's doors at once. The door is the heading; its description says
 * what lives behind it. The registry's rows carry no description: the title
 * is the whole door until the contributing capability's page says more.
 *
 * The doors are sections separated by rules — the hub holds no working set
 * (no rows to scan, no form, no state to name), so no panel stands here; a
 * link is a link, and the doors stay links. The hub is the settings landing,
 * so it wears the area's name in the tab; each sub-page owns its own (the
 * title stack's top names the page, and a child's push never loses to this
 * one — the hub unmounts when a cluster opens).
 */
export function SettingsPage() {
  const t = useTranslation();
  // The tab's name: this landing is "Einstellungen" until a cluster opens.
  usePageTitle(t("settings.heading"));

  return (
    <>
      {[...CLUSTERS, ...settingsPages].map((cluster) => (
        <section
          key={cluster.id}
          aria-labelledby={`settings-cluster-${cluster.id}`}
          className="border-b border-rule py-5 first:pt-0 last:border-b-0 last:pb-0"
        >
          <h2 id={`settings-cluster-${cluster.id}`} className="text-emph font-semibold">
            <Link
              to={cluster.path}
              className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
            >
              {t(cluster.titleKey)}
            </Link>
          </h2>
          {"descriptionKey" in cluster ? (
            <p className="mt-1 text-body text-muted">{t(cluster.descriptionKey)}</p>
          ) : null}
        </section>
      ))}
    </>
  );
}
