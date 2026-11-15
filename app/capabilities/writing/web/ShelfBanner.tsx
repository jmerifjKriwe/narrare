/**
 * The activity banner's placeholder — the `shelf` draft's cadence panel,
 * honestly inert until Task 10 wires the activity aggregate (goal,
 * weekly average, sparkline, streak). The geometry stands where the draft
 * draws it; the values are the spec's neutral —, never the draft's mock
 * 750/840, and the sparkline is omitted (invented data). The statistics
 * door stays disabled with the drafted note.
 */

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

export function ShelfBanner({ noteId }: { noteId: string }) {
  const t = useTranslation();
  return (
    <section className="rounded-xl border border-border bg-surface p-4 shadow-sm lg:p-6">
      <div className="flex flex-col items-center justify-between gap-4 lg:flex-row">
        <div className="flex items-center gap-4">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-surface-container-high text-primary">
            <Icon name="insights" size={22} />
          </div>
          <div>
            <h3 className="text-emph text-foreground">
              <span>{t("writing.shelf.banner.title")}</span>
              <span className="tabular-nums">: —</span>
            </h3>
            <p className="text-meta text-muted">{t("writing.shelf.banner.body")}</p>
          </div>
        </div>
        <div className="flex w-full items-center justify-end gap-4 lg:w-auto">
          <div className="hidden flex-col items-end sm:flex">
            <span className="text-eyebrow uppercase text-muted">{t("writing.shelf.banner.weekly")}</span>
            <span className="text-emph tabular-nums text-muted">—</span>
          </div>
          {/* Task 10 wires the activity aggregate and the statistics door. */}
          <button
            type="button"
            disabled
            aria-describedby={noteId}
            className="h-8 shrink-0 cursor-not-allowed rounded-lg bg-surface-container px-3 text-label text-foreground opacity-50"
          >
            {t("writing.shelf.banner.stats")}
          </button>
        </div>
      </div>
      <p id={noteId} className="mt-2 text-meta text-muted">
        {t("writing.shelf.comingSoon")}
      </p>
    </section>
  );
}
