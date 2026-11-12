import { useTranslation } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";
import { Icon } from "@shell/ui/icons";

/**
 * The activity banner (`screens/library/shelf.html`, and its empty-shelf
 * variant in `shelf-empty.html`): the writing cadence at a glance. Every
 * number the draft shows is a goal-series fact the app does not carry, so
 * every one of them renders its §6.6 neutral — the goal 0, the weekly
 * average 0, the sparkline flat — and each hides behind its follow-up.
 *
 * The empty shelf's variant is the empty screen's own: the routine says it
 * is ready, the goal line asks for the first chapter.
 */
export function ActivityBanner({ empty = false }: { empty?: boolean }) {
  const t = useTranslation();
  return (
    <section className="flex flex-col items-center justify-between gap-4 rounded-[var(--radius-surface)] bg-card p-4 shadow-[var(--shadow-card)] lg:flex-row">
      <div className="flex items-center gap-4">
        <div
          className={`grid h-10 w-10 shrink-0 place-items-center rounded-[var(--radius-control)] ${
            empty ? "bg-surface-container-high text-outline" : "bg-surface-container-high text-primary"
          }`}
        >
          <Icon name={empty ? "clock" : "insights"} />
        </div>
        <div>
          {/* Interim: no goals exist; the drafted "750" is never implied —
           * the §6.6 neutral is 0, and the sentence stays the drafted one.
           * Missing data: the daily writing goal.
           * Follow-up: render the goal and today's progress (#782). */}
          <h3 className="text-emph text-foreground tabular-nums">
            {t("shelf.banner.goal", { count: 0 })}
          </h3>
          <p className="text-meta text-muted">
            {empty
              ? t("shelf.banner.noSession")
              : // Interim: the same neutral in the drafted sentence's shape
                // — 0 written, 0 to go, until a goal series exists.
                // Missing data: today's written words and the daily goal.
                // Follow-up: render both counts (#782).
              t("shelf.banner.goalIdle", { count: 0, remaining: 0 })}
          </p>
        </div>
      </div>
      <div className="flex w-full items-center justify-end gap-4 lg:w-auto">
        {empty ? (
          <div className="hidden flex-col items-end sm:flex">
            <span className="text-eyebrow uppercase text-muted">{t("shelf.banner.routine")}</span>
            <span className="text-emph text-muted">{t("shelf.banner.ready")}</span>
          </div>
        ) : (
          <>
            <div className="hidden flex-col items-end sm:flex">
              <span className="text-eyebrow uppercase text-muted">{t("shelf.banner.weekly")}</span>
              {/* Interim: no goal series exists; the weekly average is the
               * §6.6 neutral, 0 — never a plausible number.
               * Missing data: the daily word series.
               * Follow-up: render the real average (#782). */}
              <span className="text-emph text-foreground tabular-nums">
                {t("shelf.banner.weeklyValue", { count: 0 })}
              </span>
            </div>
            {/* Interim: the sparkline over a series that does not exist —
             * the §6.6 neutral is flat, one line at the drafted panel's own
             * height, the last point still marked. Purely decorative until
             * the series does.
             * Missing data: the daily word series.
             * Follow-up: draw the real week (#782). */}
            <svg
              data-sparkline
              aria-hidden="true"
              className="overflow-visible text-area-writing"
              width="120"
              height="32"
              viewBox="0 0 120 32"
            >
              <path
                d="M 0,16 L 120,16"
                fill="none"
                stroke="currentColor"
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth="2"
              />
              <circle cx="120" cy="16" r="3" className="fill-cover-sepia" />
            </svg>
          </>
        )}
        {/* Interim: no statistics surface exists to open — the drafted door
         * stands, disabled, rather than pointing nowhere.
         * Missing data: the statistics surface (and the goal settings one,
         * on the empty shelf).
         * Follow-up: open them (#788). */}
        <Button variant="secondary" size="md" disabled className="shrink-0">
          {empty ? t("shelf.banner.adjustGoal") : t("shelf.banner.statistics")}
        </Button>
      </div>
    </section>
  );
}
