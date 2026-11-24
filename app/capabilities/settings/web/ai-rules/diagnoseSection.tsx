/**
 * The System-Diagnose section (W8 Task 9) — the approved draft's fourth
 * section on the shell's tokens, standing only on what the reads answer:
 *
 * - The driver card speaks the driver read's one word. On `fake` it is the
 *   draft's offline card, true as written; on `configured` it states exactly
 *   what the word means — no endpoint is named, nothing claimed beyond the
 *   read. A pending or failed read shows no card at all (the offline card's
 *   own precedent: no answer, no claim).
 * - One danger card per model whose newest audit failed: the stored
 *   `last_error_code`, the model's name, and „Erneut testen“ — the real
 *   re-ask, the same write the model card's test face runs. The draft's
 *   static 401/502 examples are faces of these cards, rendered only when a
 *   real failure stands behind them.
 */
import type { Model } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { useTestModel } from "../aiRulesQuery";
import { useDriver } from "../driverQuery";

const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

export function DiagnoseSection({ models }: { models: Model[] }) {
  const t = useTranslation();
  const driver = useDriver();
  const testModel = useTestModel();

  const failing = models.filter((model) => model.last_error_code !== null);
  const showDriverCard = driver.isSuccess;

  return (
    <section id="sektion-diagnose" aria-labelledby="ai-rules-diagnose-heading" className="space-y-4">
      <div className="space-y-0.5">
        <h2 id="ai-rules-diagnose-heading" className="text-title font-semibold text-foreground">
          {t("settings.ai.section.diagnose")}
        </h2>
        <p className="text-meta text-muted">{t("settings.ai.diag.sub")}</p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        {showDriverCard && (
          <article
            data-testid="driver-card"
            data-driver-kind={driver.data.kind}
            className="flex flex-col justify-between space-y-3 rounded-lg border border-border bg-card p-4 shadow-sm"
          >
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-success">
                  <Icon name="checkCircle" size={18} />
                  <span className="text-emph font-semibold">
                    {driver.data.kind === "fake"
                      ? t("settings.ai.diag.fakeTitle")
                      : t("settings.ai.diag.configuredTitle")}
                  </span>
                </div>
                <span aria-hidden="true" className="h-2 w-2 rounded-full bg-success" />
              </div>
              <p className="text-meta leading-relaxed text-muted">
                {driver.data.kind === "fake"
                  ? t("settings.ai.diag.fakeBody")
                  : t("settings.ai.diag.configuredBody")}
              </p>
            </div>
            <div className="rounded bg-surface px-3 py-1.5 text-center text-meta font-medium text-success">
              {t("settings.ai.diag.noAction")}
            </div>
          </article>
        )}

        {failing.map((model) => (
          <article
            key={model.id}
            data-testid="diagnose-error-card"
            className="flex flex-col justify-between space-y-3 rounded-lg border border-border bg-card p-4 shadow-sm"
          >
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-danger">
                <Icon name="warning" size={18} />
                <span className="text-emph font-semibold">
                  {t("settings.ai.diag.errorTitle", { code: model.last_error_code ?? "" })}
                </span>
              </div>
              <p className="text-meta leading-relaxed text-muted">{t("settings.ai.diag.errorBody")}</p>
              <p className="font-mono text-[11px] text-muted">
                {model.name} · {t("settings.ai.models.via", { provider: model.provider_name })}
              </p>
            </div>
            <button
              type="button"
              disabled={testModel.isPending}
              onClick={() => testModel.mutate({ id: model.id })}
              className={`w-full rounded bg-soft py-1.5 text-label text-foreground transition-colors hover:bg-surface-container-high ${FOCUS} ${testModel.isPending ? "cursor-wait opacity-60" : ""}`}
            >
              {t("settings.ai.diag.retest")}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
