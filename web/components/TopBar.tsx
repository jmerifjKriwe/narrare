/**
 * The topbar — the W4 chrome draft's semantic bar (56px, `h-14`) on the
 * shell's tokens, spanning the page above the rail with its left group on
 * the content axis (`--rail-width`, the light stage's own indent).
 *
 * Two faces, one bar: on the shelf the breadcrumb reads „Atelier / Das
 * Bücherregal" and the word chip the atelier's real total (tile 7, light
 * wins over the dark's book count); on a workspace route it reads
 * „Manuscripts / <book>" with the book's own word count and the volume
 * chip when the book belongs to a series (the live stage). The workspace
 * route rides Task 11 — the book face is structurally ready now.
 *
 * Beside the breadcrumb: the save chip, reading the same LIVE sync owner
 * as the rail foot and the editor foot (`saveStatus.ts` — Task 12 wired it;
 * the draft's tile-3 faces, Gespeichert / Sicherung läuft … / Sicherung
 * fehlgeschlagen). On the
 * right: the ⌘K search chip, honestly disabled with the drafted tooltip
 * (INTERIM #882 — the command palette is a later shell wave's; the chip
 * keeps its geometry and its note, never a pretend door), the real word
 * chip (the rows' own Σ, the family's dash on a failure, never an invented
 * zero), and the language chip as the REAL switcher (D17 — the shared
 * contract's fifth face, `@shell/lib/language`).
 *
 * Icon faces (spec §6.9): search → search, the draft's `edit` → write
 * (the light stage's pencil; the dark's `draw` yields to the light).
 */
import { Link } from "@tanstack/react-router";
import { useId } from "react";

import { useTranslation } from "../lib/i18n";
import { LanguageChip } from "../lib/language";
import { SAVE_FACES, SAVE_TONE_CLASS, useSaveStatus } from "../lib/saveStatus";
import { Icon } from "../ui/icons";
import { useChromeNovels } from "./chrome";

/** The brand serif, the BookCover pattern: one stack, read from the token.
 *  Book titles wear it — the typographic discipline reserves it for them. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the bar offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

export function TopBar() {
  const t = useTranslation();
  const { novels, active, bookId } = useChromeNovels();
  // The live sync owner — one state with the rail foot and the editor foot
  // (Task 12). The face is the draft's tile-3 vocabulary, the honest sub-label
  // rides as the tooltip.
  const saveStatus = useSaveStatus();
  const saveFace = SAVE_FACES[saveStatus];
  const saveTone = SAVE_TONE_CLASS[saveFace.tone];
  const searchNoteId = useId();

  const bookFace = bookId !== null;
  const rows = (novels.data ?? []).filter((novel) => novel.archived_at == null);
  const totalWords = rows.reduce((sum, novel) => sum + novel.word_count, 0);

  // The word chip: the book's own count on the workspace, the atelier's
  // total on the shelf — the rows' own figures while the ask stands, the
  // family's dash on a failure, a quiet placeholder while it runs.
  const wordsValue = novels.isPending ? (
    <span aria-hidden="true" className="block h-4 w-16 animate-pulse rounded bg-soft" />
  ) : novels.isSuccess ? (
    bookFace ? (
      active !== null ? (
        t("shell.topbar.words", { count: active.word_count })
      ) : (
        "—"
      )
    ) : (
      t("shell.topbar.wordsTotal", { count: totalWords })
    )
  ) : (
    "—"
  );

  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border bg-panel px-4">
      {/* The breadcrumb, on the content axis; the save chip beside it. */}
      <div className="flex min-w-0 items-center gap-2 pl-[var(--rail-width)] text-meta font-medium">
        {bookFace ? (
          <>
            <Link to="/" className={`shrink-0 text-muted transition-colors hover:text-foreground ${FOCUS}`}>
              {t("shell.topbar.manuscripts")}
            </Link>
            <span aria-hidden="true" className="text-outline-variant">
              /
            </span>
            <span className={`${SERIF} truncate text-base font-semibold tracking-tight text-foreground`}>
              {active?.title ?? "—"}
            </span>
            {active?.series_volume != null && (
              <span className="ml-2 shrink-0 rounded border border-border bg-surface-container-low px-1.5 py-0.5 font-mono text-[10px] text-muted">
                {t("shell.topbar.volume", { volume: active.series_volume })}
              </span>
            )}
          </>
        ) : (
          <>
            <Link to="/" className={`shrink-0 text-muted transition-colors hover:text-foreground ${FOCUS}`}>
              {t("shell.topbar.atelier")}
            </Link>
            <span aria-hidden="true" className="text-outline-variant">
              /
            </span>
            <span className="truncate font-semibold text-foreground">{t("shell.topbar.shelf")}</span>
          </>
        )}
        {/* The save chip — the draft's sync-state geometry (tile 3), the
            same live owner as the rail foot and the editor foot. The dot
            pulses while the write is engaged; the honest sub-label is the
            tooltip. */}
        <span
          title={t(saveFace.note)}
          className={`ml-3 flex shrink-0 items-center gap-1.5 rounded border border-border bg-surface-container-low px-2 py-0.5 text-meta font-medium ${saveTone.text}`}
        >
          <span
            aria-hidden="true"
            className={`h-2 w-2 rounded-full ${saveTone.dot} ${saveStatus === "saving" ? "animate-pulse" : ""}`}
          />
          {t(saveFace.label)}
        </span>
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {/* The ⌘K search chip: INTERIM #882 — honestly disabled until the
            * shell palette wave ships the command palette. The drafted
            * tooltip names the reason; aria-describedby carries it to
            * assistive tech even while it waits for hover. Below the sm
            * breakpoint the chip folds away (#911): it is the one interim
            * control in the cluster, and the right cluster is otherwise
            * rigid (shrink-0) — at phone widths it alone pushed the
            * document past the viewport. The word chip and the language
            * switcher, the real controls, stay at every width. */}
        <div className="group relative hidden cursor-not-allowed sm:block">
          <button
            type="button"
            disabled
            // The visible keycap rides the name (WCAG 2.5.3) — the note
            // below carries the reason the shortcut does not work yet.
            aria-label={`${t("shell.topbar.search")} ⌘K`}
            aria-describedby={searchNoteId}
            className="flex cursor-not-allowed items-center gap-2 rounded border border-border/80 bg-surface-container-low px-2.5 py-1 text-meta text-muted opacity-75"
          >
            <Icon name="search" size={17} />
            <span>{t("shell.topbar.search")}</span>
            {/* The keycap is a visual hint, not part of the control's name
                (WCAG 2.5.3: the visible label is the name; the note carries
                the reason) — aria-hidden keeps the two in agreement. */}
            <kbd
              aria-hidden="true"
              className="rounded border border-border bg-surface-container-lowest px-1.5 py-0.5 font-mono text-[10px] text-muted"
            >
              ⌘K
            </kbd>
          </button>
          <div
            id={searchNoteId}
            role="tooltip"
            className="absolute right-0 top-full z-50 mt-1.5 hidden whitespace-nowrap rounded bg-inverse-surface px-2.5 py-1 text-[11px] text-inverse-foreground shadow-overlay group-hover:block"
          >
            {t("shell.topbar.search.note")}
          </div>
        </div>

        {/* The word chip: the real Σ, never the draft's mock figure. */}
        <div className="flex items-center gap-1.5 rounded border border-border bg-surface-container-low px-2.5 py-1 text-meta font-medium text-foreground">
          <span className="text-primary">
            <Icon name="write" size={16} />
          </span>
          <span className="tabular-nums">{wordsValue}</span>
        </div>

        {/* The language chip: the real switcher (D17), the shared
            contract's chrome face — not the pre-checkpoint passive DE. */}
        <LanguageChip />
      </div>
    </header>
  );
}
