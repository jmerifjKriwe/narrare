import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";

import { ProvidersPanel } from "./ProvidersPanel";

/**
 * The provider cluster's page: the profiles with their keys and tuning, and
 * the tasks they serve — the whole provider surface, on a page of its own.
 */
export function ProviderPage() {
  const t = useTranslation();
  // The tab's name: this page is "Anbieter", the cluster's own word — every
  // settings page names itself, the landing and the contributed ones too.
  usePageTitle(t("settings.providers"));
  return <ProvidersPanel />;
}
