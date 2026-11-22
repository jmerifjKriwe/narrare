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
 * zero), the language chip as the REAL switcher (D17 — the shared
 * contract's fifth face, `@shell/lib/language`), and the user block (W7
 * Task 3) — the settings-allgemein draft's wired tile: initials, the
 * author_name → email fallback name, and the menu whose rows door into the
 * settings surface at their sections (Autorenname → `#profil-sektion`,
 * Tagesziel → `#tagesziel-feld`, Einstellungen → `/settings`), Abmelden
 * honestly disabled with its no-backend note.
 *
 * Icon faces (spec §6.9): search → search, the draft's `edit` → write
 * (the light stage's pencil; the dark's `draw` yields to the light).
 */
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import { useTranslation } from "../lib/i18n";
import { LanguageChip } from "../lib/language";
import { useSettingsQuery } from "../lib/query";
import { SAVE_FACES, SAVE_TONE_CLASS, useSaveStatus } from "../lib/saveStatus";
import { Icon } from "../ui/icons";
import { initialsFrom, useChromeNovels } from "./chrome";

/** The brand serif, the BookCover pattern: one stack, read from the token.
 *  Book titles wear it — the typographic discipline reserves it for them. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the bar offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/**
 * The user block (W7 Task 3) — the settings-allgemein draft's wired tile.
 * The closed chip names the profile (initials, the author_name → email
 * fallback, the honest neutral when neither stands); opening docks the
 * draft's menu under it: the user info header, the three rows that door
 * into the settings surface (Autorenname → the profile section's address,
 * Tagesziel → the goal field's address, Einstellungen → the surface), and
 * Abmelden honestly disabled — no cloud session exists to end, and the
 * note says so instead of pretending. The menu keeps the quick menu's
 * popover discipline: opening moves focus to the first row, arrows walk
 * with wrap, Home/End jump, Enter/Space choose, Escape closes and returns
 * the focus, an outside press closes without stealing it. The disabled row
 * stays out of the walk — a dead row is not a choice.
 */
function UserBlock() {
  const t = useTranslation();
  const navigate = useNavigate();
  const settings = useSettingsQuery();
  const pathname = useRouterState({ select: (state) => state.location.pathname });

  const authorName = settings.data?.author_name ?? null;
  const email = settings.data?.email ?? null;
  const goal = settings.data?.daily_goal_words ?? null;
  const userName = authorName ?? email ?? t("shell.rail.user");
  const initials = initialsFrom(authorName ?? (email !== null ? email.split("@")[0] : null));
  // The trigger's name carries the chip's initials, as the switcher's does
  // („Aktives Buch: {monogram} {title}"): the glyphs are the tile's visible
  // text, so the accessible name says them too (WCAG 2.5.3 label-in-name).
  const userNameLabel = initials !== null ? `${initials} ${userName}` : userName;
  const onSettings = pathname === "/settings";

  const [open, setOpen] = useState(false);
  const menuId = useId();
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const itemCount = 3; // the walk: the two profile doors and Einstellungen

  const close = useCallback((returnFocus: boolean) => {
    setOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  /** One door: close with the focus returned, then walk to the settings
   *  surface at the row's own section address. */
  function go(hash?: string) {
    close(true);
    void navigate({ to: "/settings", hash });
  }

  // While the menu stands: Escape closes innermost-first, an outside press
  // closes without stealing focus — the quick menu's discipline.
  useEffect(() => {
    if (!open) return;
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      close(true);
    }
    function onDown(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open, close]);

  // Opening moves focus to the menu's first row — the draft's lead.
  useEffect(() => {
    if (open) itemRefs.current[0]?.focus();
  }, [open]);

  /** The trigger's keyboard: ArrowDown/ArrowUp open the menu. */
  function triggerKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    setOpen(true);
  }

  /** The rows' keyboard — the walk described above. */
  function itemKey(event: KeyboardEvent<HTMLButtonElement>, at: number) {
    let next: number;
    if (event.key === "ArrowDown") next = (at + 1) % itemCount;
    else if (event.key === "ArrowUp") next = (at - 1 + itemCount) % itemCount;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = itemCount - 1;
    else if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      event.currentTarget.click();
      return;
    } else if (event.key === "Tab") {
      close(true);
      return;
    } else return;
    event.preventDefault();
    itemRefs.current[next]?.focus();
  }

  const itemClass = (active: boolean) =>
    `flex w-full items-center justify-between gap-2 rounded px-4 py-2 text-left text-meta transition-colors ${FOCUS} ${
      active ? "bg-surface-container font-semibold text-primary" : "text-foreground hover:bg-surface-container"
    }`;

  return (
    <div ref={wrapperRef} className="relative">
      <button
        type="button"
        ref={triggerRef}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label={t("shell.rail.user.named", { name: userNameLabel })}
        onClick={() => setOpen((previous) => !previous)}
        onKeyDown={triggerKey}
        title={t("shell.rail.user.named", { name: userNameLabel })}
        className={`flex items-center gap-2 rounded border border-border bg-surface-container-low py-1 pl-1.5 pr-2 text-left transition-colors hover:border-outline-variant ${FOCUS}`}
      >
        {/* The initials chip: a presentational duplicate of the name beside
            it — the label below carries the same glyphs (the switcher's
            contract, „Aktives Buch: {monogram} {title}"), so what the tile
            shows is what the name says (WCAG 2.5.3). */}
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded bg-soft text-[10px] font-bold text-primary">
          {initials ?? <Icon name="person" size={14} />}
        </span>
        {/* The space keeps the initials and the name separate words in the
            visible text — the name carries both, in order. Without it the
            concatenated „EQErika Quell" is one pseudo-word no label can
            contain, and label-in-name (WCAG 2.5.3) reads the tile as
            mislabelled — the switcher's own finding, here too. */}
        {" "}
        <span className="max-w-[10rem] truncate text-meta font-medium text-foreground">{userName}</span>
        <span className="text-muted">
          <Icon name={open ? "expandLess" : "chevronDown"} size={14} />
        </span>
      </button>
      {open && (
        <div
          id={menuId}
          role="menu"
          aria-label={t("shell.rail.user")}
          className="absolute right-0 top-full z-50 mt-1.5 w-80 rounded-lg border border-border bg-surface-container-lowest py-2 shadow-overlay"
        >
          {/* The user info header — the row's own answers, mono email. */}
          <div className="mb-1 border-b border-rule px-4 py-2.5">
            <div className="truncate text-label font-semibold leading-tight text-foreground">{userName}</div>
            {email !== null && (
              <div className="mt-0.5 truncate font-mono text-[11px] text-muted">{email}</div>
            )}
          </div>
          <div className="py-1">
            <button
              type="button"
              role="menuitem"
              ref={(node) => {
                itemRefs.current[0] = node;
              }}
              onKeyDown={(event) => itemKey(event, 0)}
              onClick={() => go("profil-sektion")}
              className={itemClass(false)}
            >
              <span>{t("shell.menu.authorName")}</span>
              <span className="text-[10px] text-muted">{t("shell.menu.profileMeta")}</span>
            </button>
            <button
              type="button"
              role="menuitem"
              ref={(node) => {
                itemRefs.current[1] = node;
              }}
              onKeyDown={(event) => itemKey(event, 1)}
              onClick={() => go("tagesziel-feld")}
              className={itemClass(false)}
            >
              <span>{t("shell.menu.goal")}</span>
              {/* The row's real goal, the dash when none stands — never a
                  mock figure (the draft's 500 W is its example row). */}
              <span className="font-mono text-[10px] text-muted">
                {goal !== null ? t("shell.menu.goalMeta", { count: goal }) : "—"}
              </span>
            </button>
            <button
              type="button"
              role="menuitem"
              aria-current={onSettings ? "true" : undefined}
              ref={(node) => {
                itemRefs.current[2] = node;
              }}
              onKeyDown={(event) => itemKey(event, 2)}
              onClick={() => go()}
              className={itemClass(onSettings)}
            >
              <span className="flex items-center gap-2">
                {onSettings && (
                  <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-primary" />
                )}
                {t("shell.menu.settings")}
              </span>
              {onSettings && (
                <span className="text-[10px] text-primary">{t("shell.menu.settingsActive")}</span>
              )}
            </button>
          </div>
          <div aria-hidden="true" className="mx-0 my-1 border-t border-rule" />
          {/* Abmelden: honestly disabled — the local instance holds no
              cloud session to end. Out of the walk, the note carries the
              reason (the draft's LOKAL row and its box). */}
          <div className="px-4 py-2">
            <div className="flex cursor-not-allowed items-center justify-between text-muted opacity-60">
              <span className="font-normal line-through">{t("shell.menu.signOut")}</span>
              <span className="rounded bg-soft px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-muted">
                {t("shell.menu.localBadge")}
              </span>
            </div>
            <div className="mt-2 rounded border border-rule bg-panel p-2.5 text-[11px] leading-relaxed text-muted">
              {t("shell.menu.localNote")}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export function TopBar() {
  const t = useTranslation();
  const { novels, active, bookId } = useChromeNovels();
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  // The live sync owner — one state with the rail foot and the editor foot
  // (Task 12). The face is the draft's tile-3 vocabulary, the honest sub-label
  // rides as the tooltip.
  const saveStatus = useSaveStatus();
  const saveFace = SAVE_FACES[saveStatus];
  const saveTone = SAVE_TONE_CLASS[saveFace.tone];
  const searchNoteId = useId();

  const bookFace = bookId !== null;
  // The settings face (W7 Task 3): the draft's „Atelier › Einstellungen"
  // crumb on its surface — a global page wears no book, so the shelf face
  // would name the wrong place.
  const settingsFace = !bookFace && pathname === "/settings";
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
        ) : settingsFace ? (
          <>
            <Link to="/" className={`shrink-0 text-muted transition-colors hover:text-foreground ${FOCUS}`}>
              {t("shell.topbar.atelier")}
            </Link>
            <span aria-hidden="true" className="text-outline-variant">
              /
            </span>
            <span className="truncate font-semibold text-foreground">{t("shell.nav.settings")}</span>
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

        {/* The user block: the wired tile (W7 Task 3) — initials and name,
            the menu that doors into the settings surface. */}
        <UserBlock />
      </div>
    </header>
  );
}
