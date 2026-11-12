import { useTranslation } from "@shell/lib/i18n";
import { formatNumber } from "@shell/lib/format";
import { Button } from "@shell/ui/Button";
import { Icon } from "@shell/ui/icons";

/**
 * The shelf's head, as `screens/library/shelf.html` draws it: the area's
 * eyebrow with its session dot, the page title in the brand serif, the
 * metrics strip beside it, and the shelf's two doors — import and new
 * book — at the strip's end.
 *
 * The metrics are the list's own truth (spec §6.6): the book count and
 * the summed words derive from what stands on the shelf; the streak has
 * no source yet and renders its §6.6 neutral. The session line is the
 * one dated fact the clock itself owns — the season and the year, said
 * the way the drafts say them.
 */

/** The session label's season word: northern meteorological seasons, the
 *  clock's own derivation — never a stored or invented session. */
const SEASON_KEYS = [
  "shelf.season.winter",
  "shelf.season.winter",
  "shelf.season.spring",
  "shelf.season.spring",
  "shelf.season.spring",
  "shelf.season.summer",
  "shelf.season.summer",
  "shelf.season.summer",
  "shelf.season.autumn",
  "shelf.season.autumn",
  "shelf.season.autumn",
  "shelf.season.winter",
] as const;

/** One metric card: the icon in its cell, the number, the eyebrow label.
 *  Everything but the values is the drafted shape — px-4 py-2.5 on the
 *  surface radius, a 32 px icon cell on the control radius, the number at
 *  the emph step, the label at the eyebrow's. */
function Metric({
  icon,
  cellClass,
  value,
  label,
}: {
  icon: React.ReactNode;
  cellClass: string;
  value: string;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-[var(--radius-surface)] bg-surface-container-low px-4 py-2.5 shadow-[var(--shadow-card)]">
      <div className={`grid h-8 w-8 place-items-center rounded-[var(--radius-control)] ${cellClass}`}>
        {icon}
      </div>
      <div>
        <div className="text-emph leading-none text-foreground tabular-nums">{value}</div>
        <div className="mt-0.5 text-eyebrow uppercase text-muted">{label}</div>
      </div>
    </div>
  );
}

/** The shelf's head: title block, metrics and the two doors. The empty
 *  shelf keeps the head exactly as the standing one draws it — the quiet
 *  metric cells and both doors included (`shelf-empty.html` draws the
 *  same strip, doors and all) — so the drafted create affordances stand
 *  twice there: the header door and the empty panel's own CTA. */
export function ShelfHeader({
  count,
  totalWords,
  empty = false,
  onCreate,
  onImport,
}: {
  count: number;
  totalWords: number;
  empty?: boolean;
  onCreate: () => void;
  onImport: () => void;
}) {
  const t = useTranslation();
  const now = new Date();
  const season = t(SEASON_KEYS[now.getMonth()]);
  // The empty shelf's icons sit quiet in the outline ink (shelf-empty's
  // own cells); the standing shelf's carry their accents.
  const quietCell = "bg-surface-container-high text-outline";
  // A real `header` element, scoped by `main` (no banner role — the top
  // bar owns that one): it names the container the create and import
  // doors live in, so tests and screen readers can tell the header's
  // door from the empty panel's own CTA apart by scope, not by order.
  return (
    <header className="flex flex-col justify-between gap-4 pb-1 lg:flex-row lg:items-end">
      <div>
        <div className="mb-1.5 flex items-center gap-2">
          <span className="text-eyebrow uppercase text-area-writing">{t("shelf.eyebrow")}</span>
          <span className="h-1.5 w-1.5 rounded-full bg-outline-variant" aria-hidden="true" />
          <span className="text-meta text-muted">
            {t("shelf.session", { season, year: now.getFullYear() })}
          </span>
        </div>
        <h1 className="text-[26px] leading-[34px] font-semibold tracking-tight text-primary [font-family:'EB_Garamond',Georgia,'Times_New_Roman',serif]">
          {t("shelf.title")}
        </h1>
        <p className="mt-1 text-body text-muted">{t("shelf.subtitle")}</p>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <Metric
          icon={<Icon name="books" />}
          cellClass={empty ? quietCell : "bg-surface-container-high text-primary"}
          value={t("shelf.metrics.novels", { count })}
          label={t("shelf.metrics.activeProjects")}
        />
        <Metric
          icon={<Icon name="historyEdu" />}
          cellClass={empty ? quietCell : "bg-secondary-container text-primary"}
          value={formatNumber(totalWords)}
          label={t("shelf.metrics.totalWords")}
        />
        <Metric
          icon={<Icon name="localFire" />}
          cellClass={empty ? quietCell : "bg-surface-container-high text-warning"}
          // Interim: no writing-streak source exists; the §6.6 neutral is
          // the em dash, never a guessed number.
          // Missing data: daily writing activity.
          // Follow-up: render the tracked streak (index issue at Task 11).
          value={t("shelf.streakNone")}
          label={t("shelf.metrics.streak")}
        />
        {/* Both doors stand on the empty shelf too — the draft draws the
         *  strip with its doors and the panel with its own CTA beside
         *  them (`shelf-empty.html`). */}
        <div className="flex items-center gap-2 pl-2">
          <Button variant="secondary" size="md" icon={<Icon name="import" />} onClick={onImport}>
            {t("shelf.import")}
          </Button>
          <Button variant="primary" size="md" icon={<Icon name="plus" />} onClick={onCreate}>
            {t("novels.new")}
          </Button>
        </div>
      </div>
    </header>
  );
}
