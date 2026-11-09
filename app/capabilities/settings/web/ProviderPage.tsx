import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";

import { ProvidersPanel } from "./ProvidersPanel";

/**
 * The provider cluster's page: the providers (the saved endpoints), the
 * models that hang off them (which provider serves which model string, and
 * how it is tuned), and the tasks those models serve — the whole provider
 * surface, on a page of its own.
 */
export function ProviderPage() {
  const t = useTranslation();
  // The tab's name: this page is "Anbieter", the cluster's own word — every
  // settings page names itself, the landing and the contributed ones too.
  usePageTitle(t("settings.providers"));
  return <ProvidersPanel />;
}
