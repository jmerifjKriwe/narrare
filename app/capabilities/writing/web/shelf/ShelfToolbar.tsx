import { useTranslation } from "@shell/lib/i18n";
import { controlClass, Select } from "@shell/ui/field";
import { Icon } from "@shell/ui/icons";

/**
 * The shelf's working row (`screens/library/shelf.html`): the search field
 * the drafted shell fixes, the genre filter beside it, and the view toggle
 * at the far edge. All three are pure client state (spec §6.6): the page
 * owns the state, this row only speaks it.
 *
 * The search matches titles today — the placeholder still names figures
 * and tags because the drafts say it, and the gap is filed, not hidden.
 * The filter is the genres the shelf itself carries; the toggle is the
 * drafted pair of icon cells with the standing one pressed.
 */

/** The two views the drafted toggle names. */
export type ShelfView = "grid" | "list";

/** One icon cell of the view toggle: the drafted pressed treatment — the
 *  standing cell on the card ground in the primary ink — is the segmented
 *  control's own, not a button-matrix paint. */
function ViewButton({
  pressed,
  label,
  icon,
  onPick,
}: {
  pressed: boolean;
  label: string;
  icon: React.ReactNode;
  onPick: () => void;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={pressed}
      onClick={onPick}
      className={`inline-flex p-1.5 transition-colors focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus focus-visible:ring-offset-1 focus-visible:ring-offset-transparent ${
        pressed
          ? "rounded-[var(--radius-control)] bg-card text-primary shadow-[var(--shadow-card)]"
          : "rounded-[var(--radius-control)] text-muted hover:bg-card hover:text-foreground"
      }`}
    >
      {icon}
    </button>
  );
}

/** The search/filter/toggle row. Controlled throughout: `search`, `genre`
 *  and `view` are the page's state, the row's handlers report back. */
export function ShelfToolbar({
  search,
  onSearch,
  genres,
  genre,
  onGenre,
  view,
  onView,
}: {
  search: string;
  onSearch: (value: string) => void;
  /** The genres the shelf carries, in the order given. */
  genres: string[];
  genre: string | null;
  onGenre: (value: string | null) => void;
  view: ShelfView;
  onView: (view: ShelfView) => void;
}) {
  const t = useTranslation();
  return (
    <div className="flex flex-col items-center justify-between gap-3 pb-1 sm:flex-row">
      <div className="flex w-full items-center gap-2 sm:w-auto">
        <div
          className={`${controlClass()} flex w-full items-center gap-2 px-3 shadow-[var(--shadow-card)] focus-within:outline-hidden focus-within:ring-2 focus-within:ring-focus focus-within:ring-offset-1 focus-within:ring-offset-transparent sm:w-72`}
        >
          <span className="shrink-0 text-muted">
            <Icon name="search" />
          </span>
          {/* Interim: only titles are searched; figures and tags become
           * searchable with their search index.
           * Missing data: the figure/tag search index.
           * Follow-up: match them too (#785). */}
          <input
            type="text"
            aria-label={t("shelf.searchLabel")}
            placeholder={t("shelf.searchPlaceholder")}
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            className="w-full bg-transparent text-label text-foreground placeholder:text-muted focus:outline-none"
          />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <span className="text-muted" aria-hidden="true">
            <Icon name="tune" />
          </span>
          <Select
            aria-label={t("shelf.filterLabel")}
            value={genre ?? ""}
            onChange={(event) => onGenre(event.target.value === "" ? null : event.target.value)}
            className="w-auto"
          >
            <option value="">{t("shelf.filterAll", { count: genres.length })}</option>
            {genres.map((each) => (
              <option key={each} value={each}>
                {each}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="flex items-center gap-2 self-end text-muted sm:self-auto">
        <span className="text-meta text-muted">{t("shelf.viewLabel")}</span>
        <div className="flex items-center gap-2" role="group" aria-label={t("shelf.viewLabel")}>
          <ViewButton
            pressed={view === "grid"}
            label={t("shelf.viewGrid")}
            icon={<Icon name="gridView" />}
            onPick={() => onView("grid")}
          />
          <ViewButton
            pressed={view === "list"}
            label={t("shelf.viewList")}
            icon={<Icon name="viewList" />}
            onPick={() => onView("list")}
          />
        </div>
      </div>
    </div>
  );
}
