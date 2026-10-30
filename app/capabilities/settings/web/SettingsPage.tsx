import { Link } from "@tanstack/react-router";

import { settingsPages } from "@shell/lib/generated/settingsPages";
import { useTranslation } from "@shell/lib/i18n";

import { CLUSTERS } from "./SettingsLayout";

/**
 * The hub, the area's landing: one card per cluster — the two settings owns,
 * then every page the registry contributes — so the gear's click names all
 * of the area's doors at once. The card's title is the door; its
 * description says what lives behind it. The registry's rows carry no
 * description: the title is the whole card until the contributing
 * capability's page says more.
 */
export function SettingsPage() {
  const t = useTranslation();

  return (
    <>
      {[...CLUSTERS, ...settingsPages].map((cluster) => (
        <section
          key={cluster.id}
          aria-labelledby={`settings-cluster-${cluster.id}`}
          className="mt-8 rounded-lg border border-border bg-card px-4 py-4"
        >
          <h2 id={`settings-cluster-${cluster.id}`} className="text-lg font-semibold">
            <Link
              to={cluster.path}
              className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
            >
              {t(cluster.titleKey)}
            </Link>
          </h2>
          {"descriptionKey" in cluster ? (
            <p className="mt-1 text-sm text-muted">{t(cluster.descriptionKey)}</p>
          ) : null}
        </section>
      ))}
    </>
  );
}
