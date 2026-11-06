import { useState } from "react";

import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient, useSettingsQuery } from "@shell/lib/query";
import { applyTheme, type Theme } from "@shell/lib/theme";
import { Field, Select } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";

/**
 * The appearance cluster: the reader's light. One select — system, light,
 * dark — persisted on the user row and applied before the write, so the page
 * does not wait to answer. A refusal restores the prior light and says so in
 * the same place every refusal speaks.
 *
 * The control keeps its own selection until the refetch lands: the query is
 * the record, but a select that only moves after a roundtrip reads as broken.
 */
export function AppearancePage() {
  const t = useTranslation();
  usePageTitle(t("settings.clusterAppearance"));
  const settings = useSettingsQuery();
  const stored = settings.data?.theme ?? null;
  const [chosen, setChosen] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  const value = chosen ?? stored ?? "system";

  async function choose(next: string): Promise<void> {
    const theme: Theme | null = next === "system" ? null : (next as Theme);
    const previous: Theme | null =
      stored === "light" || stored === "dark" ? stored : null;
    setChosen(next);
    applyTheme(theme);
    setFailed(false);
    try {
      const { response } = await client.PATCH("/api/settings/theme", {
        body: { theme },
      });
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      // The row changed, so the cached answer is stale; the refetch brings
      // back what was just persisted, so cache and row cannot disagree.
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      // The write did not happen, so neither the document nor the control may
      // pretend it did.
      setChosen(null);
      applyTheme(previous);
      setFailed(true);
    }
  }

  return (
    <section aria-labelledby="settings-appearance-heading">
      <h2 id="settings-appearance-heading" className="text-emph font-semibold">
        {t("settings.clusterAppearance")}
      </h2>
      <div className="mt-3 max-w-64">
        <Field label={t("settings.appearance.themeLabel")} hint={t("settings.appearance.hint")}>
          <Select value={value} onChange={(event) => void choose(event.target.value)}>
            <option value="system">{t("settings.appearance.system")}</option>
            <option value="light">{t("settings.appearance.light")}</option>
            <option value="dark">{t("settings.appearance.dark")}</option>
          </Select>
        </Field>
      </div>
      {failed ? (
        <Notice tone="danger" live="alert" className="mt-2">
          {t("settings.appearance.errorSave")}
        </Notice>
      ) : null}
    </section>
  );
}
