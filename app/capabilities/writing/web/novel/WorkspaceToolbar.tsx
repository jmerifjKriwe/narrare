import { Link } from "@tanstack/react-router";

import { docks } from "@shell/lib/generated/docks";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import type { SaveStatus } from "@shell/lib/save";
import { Button } from "@shell/ui/Button";
import { Field, Input } from "@shell/ui/field";
import { Icon } from "@shell/ui/icons";

import type { FocusStep } from "../routes";

type DockRow = (typeof docks)[number];

/**
 * The save chip's two voices, keyed by the one autosave status the page
 * owns: the dot wears the state colour the rail's sync dot wears (settled
 * green, the debounce and the flight amber, a refusal red), the word is the
 * rail's own chrome vocabulary — the band chip is chrome, like the rail
 * foot, and the two agree word for word; the runhead's indicator keeps the
 * document's voice (`save.*`) beside the text. Idle counts as saved:
 * "absent means saved" is the app's standing truth, so the chip stands
 * permanently in the band, as the draft draws it. No live region here — the
 * editor's own SaveIndicator is the save state's announcement beside the
 * text the writer is looking at.
 */
const SAVE_CHIP: Record<SaveStatus, { dot: string; labelKey: MessageKey }> = {
  idle: { dot: "bg-success", labelKey: "shell.syncSaved" },
  saved: { dot: "bg-success", labelKey: "shell.syncSaved" },
  pending: { dot: "bg-warning", labelKey: "shell.syncPending" },
  saving: { dot: "bg-warning", labelKey: "shell.syncPending" },
  failed: { dot: "bg-danger", labelKey: "shell.syncFailed" },
};

/**
 * The workspace band (F26), dressed as the draft's editor ribbon (spec
 * §5.1): the breadcrumb naming place and book, the save chip reading the
 * one autosave status the runhead reads, the book's live word count, the
 * language chip — and on the right the workbench's own controls (dock
 * tabs, rail toggle, focus, the long rail's filter field) beside the
 * drafted trio of focus, history and export. The controls' behaviour is
 * frozen; only the geometry around them is new. The band pins below the
 * bar while the manuscript scrolls, the draft's own behaviour for it; on a
 * phone it wraps instead of pinning.
 */
export function WorkspaceToolbar({
  focus,
  collapsed,
  showRail,
  pending,
  failed,
  chapterCount,
  railFilter,
  activeDockPath,
  step,
  toggleRail,
  toggleDock,
  setWalkedIndex,
  setRailFilter,
  bookTitle,
  words,
  status,
  localeChip,
  onExport,
}: {
  focus: FocusStep;
  collapsed: boolean;
  showRail: boolean;
  pending: boolean;
  failed: boolean;
  chapterCount: number;
  railFilter: string | null;
  activeDockPath: string | undefined;
  step: (next: FocusStep) => void;
  toggleRail: () => void;
  toggleDock: (dock: DockRow) => void;
  setWalkedIndex: (value: number | null) => void;
  setRailFilter: (value: string | null) => void;
  /** The book's name, as the row holds it; `undefined` while the row waits
   *  — the breadcrumb then names the place alone. */
  bookTitle: string | undefined;
  /** The book's Σ chapter words, derived in `useNovelWorkspace`;
   *  `undefined` while the chapters wait — no count claims a book the page
   *  cannot see. */
  words: number | undefined;
  /** The open chapter's autosave state — the same owner the runhead's
   *  indicator reads (one status, no drift). */
  status: SaveStatus;
  /** The active locale's code, uppercased — the shell's language state,
   *  not a second one. */
  localeChip: string;
  /** The export press, wired by the page to the shelf's own dialog;
   *  absent while the book's row waits, and the button waits with it. */
  onExport: (() => void) | undefined;
}) {
  const t = useTranslation();
  // The save chip names the open chapter's save story, so it stands only
  // where the workbench holds one: not while the book loads or failed, and
  // not on an empty book, where a save state would name no document.
  const saveChip = !pending && !failed && chapterCount > 0;
  // The draft's centre pill — the target-progress indicator — stays hidden:
  // interim: per-chapter target field missing, shares shelf follow-up #783
  return (
    <div className="mt-6 flex min-h-11 flex-wrap items-center gap-2 rounded-[var(--radius-control)] border border-border bg-surface/80 px-3 py-1 shadow-sm backdrop-blur-md lg:sticky lg:top-0 lg:z-20">
      {/* The band wraps before it overflows: a phone's 328 px content
          box cannot hold the breadcrumb, the chips, the cluster's controls
          and an input's automatic minimum on one line, and the field is
          `min-w-0` so it shrinks into the space the buttons leave (or
          takes a line of its own) instead of pushing the page's gutter
          aside. */}
      {/* The breadcrumb: the place, then the book in the emph step — the
          draft's own pair. The book's span truncates visually while its
          text (and so its accessible name) stays the whole title, and the
          tooltip carries it for a pointer; while the row waits the place
          stands alone, with no separator dangling after it. */}
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate text-meta text-muted">
          {t("workspace.breadcrumbRoot")}
        </span>
        {bookTitle !== undefined ? (
          <>
            <span aria-hidden="true" className="text-meta text-outline-variant">
              /
            </span>
            <span
              title={bookTitle}
              className="min-w-0 truncate text-emph text-primary"
            >
              {bookTitle}
            </span>
          </>
        ) : null}
      </div>
      {saveChip ? (
        <span
          data-save={status}
          className="flex items-center gap-1.5 rounded-full bg-surface-container-low px-2 py-0.5 text-meta text-muted"
        >
          <span
            aria-hidden="true"
            className={`h-1.5 w-1.5 shrink-0 rounded-full ${SAVE_CHIP[status].dot}`}
          />
          {t(SAVE_CHIP[status].labelKey)}
        </span>
      ) : null}
      {words !== undefined ? (
        <span className="flex items-center gap-1.5 rounded-full bg-surface-container-low px-2 py-0.5 text-meta text-muted">
          <Icon name="editNote" size={14} />
          <span className="tabular-nums">
            {t("chapters.wordCount", { count: words })}
          </span>
        </span>
      ) : null}
      {/* The language chip: the active locale, opening the settings page's
          own switcher — the language's one destination, and the one store
          (`web/lib/locale`) speaks for it. The visible code rides inside
          the accessible name, so the name is never less than what is on
          screen. */}
      <Link
        to="/settings/language"
        aria-label={t("workspace.languageChip", { code: localeChip })}
        className="flex items-center gap-1.5 rounded-full bg-surface-container-low px-2 py-0.5 text-meta text-muted hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
      >
        <Icon name="globe" size={14} />
        {localeChip}
      </Link>
      {/* The draft's centre pill ("Kapitel-Ziel: 765 / 1.000 Wörter" and
          its bar) stands in this slot once a per-chapter target exists;
          the slot stays empty rather than showing a number the app does
          not have. */}
      {/* The rail's filter (Task 12): the long rail's own field, in the
          band that already holds the rail's collapse control. It stands
          only above twenty chapters and only while the rail itself is
          on screen — a field for a hidden list would be a promise with
          no subject. The input's accessible name is the fuller phrase
          that carries the visible label inside it, so the name a reader
          hears says what the field matches. */}
      {focus === 0 && showRail && !pending && !failed && chapterCount > 20 ? (
        <Field label={t("chapters.railFilter")} className="ml-auto w-40 min-w-0">
          <Input
            type="search"
            value={railFilter ?? ""}
            onChange={(event) => {
              const value = event.target.value;
              // The walk ends with the question: its row may no longer
              // be in the list the next answer renders, and a stale
              // index would leave that list without a tab stop.
              setWalkedIndex(null);
              setRailFilter(value.trim() === "" ? null : value);
            }}
            aria-label={t("chapters.railFilterAria")}
            className="min-w-0"
          />
        </Field>
      ) : null}
      {/* The band's controls: the workbench's own — dock tabs, the rail's
          collapse, focus — then the draft's right trio of focus (F9),
          history and export. The long rail's filter keeps its place ahead
          of them, the tail it already had. Each control keeps its name,
          its pressed state and its press; nothing about the re-skin moves
          a behaviour. */}
      <div className="ml-auto flex items-center gap-2">
        <div
          role="group"
          aria-label={t("workspace.dockToggle")}
          className="flex items-center gap-2"
        >
          {docks.map((dock) => (
            <Button
              key={dock.id}
              variant="icon"
              icon={<Icon name={dock.id} />}
              label={t(dock.titleKey)}
              aria-pressed={activeDockPath === dock.path}
              onClick={() => toggleDock(dock)}
            />
          ))}
        </div>
        {focus === 0 ? (
          <Button
            variant="icon"
            icon={<Icon name={collapsed ? "railShow" : "railHide"} />}
            label={t("workspace.railToggle")}
            aria-pressed={collapsed}
            onClick={toggleRail}
          />
        ) : null}
        <Button
          variant="icon"
          icon={<Icon name="focus" />}
          label={t("workspace.focusToggle")}
          aria-pressed={focus > 0}
          onClick={() => step(focus === 0 ? 1 : 0)}
        />
        {/* The label is the reason itself, as the move items' filtered
            labels are: a press that cannot run says so where a reader
            looks, and the tooltip repeats it for the pointer. */}
        <Button
          variant="icon"
          icon={<Icon name="historyEdu" />}
          label={t("workspace.historyPending")}
          title={t("workspace.historyPending")}
          aria-disabled="true"
          // interim: no version-history capability yet — follow-up filed in W3's index
          className="opacity-50"
        />
        {onExport !== undefined ? (
          <Button
            variant="ghost"
            icon={<Icon name="export" />}
            onClick={onExport}
            aria-label={t("shelf.export")}
          >
            {/* The visible word yields below `sm` so the wrapped band
                stays one control tall; the accessible name is the same
                word either way, so the button never goes unnamed. */}
            <span className="hidden sm:inline">{t("shelf.export")}</span>
          </Button>
        ) : null}
      </div>
    </div>
  );
}
