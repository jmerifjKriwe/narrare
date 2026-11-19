/**
 * The icon rail — the W4 chrome draft (`chrome-rail-topbar`, light face
 * wins; the dark face rides the token ladder) ported onto the shell's
 * tokens: 64px collapsed, gliding to 168px on hover/focus-within (the
 * coarse pointer stands open, `--rail-width`), an elevated overlay that
 * never pushes the content column (DESIGN.md's rail engine).
 *
 * Top to bottom: the brand monogram (the way home), the book switcher —
 * the active novel's cover chip and name, an `unfold_more` menu of the
 * user's real novels (the cover system's pigment at chip size, the row's
 * own genre/progress/chapter facts, never the draft's mock figures) — the
 * nav (Bücherregal live with its per-route active face; Editor and Wissen
 * live with the workspace and the lore graph; Planung and Einstellungen
 * honestly disabled with their later-wave notes), and the foot: the sync dot (the LIVE autosave
 * owner's face, `saveStatus.ts` — Task 12 wired it; tile 3's three states), the
 * real tri-state theme toggle (system → light → dark, the settings theme
 * PATCH, a refusal restores), and the user block (author_name → email
 * fallback, initials, NO tier — the drafts pin „KEIN Tier").
 *
 * The switcher's menu docks 4px off the chip (tile 2) and escapes the
 * rail's clip with fixed positioning; its book rows navigate to the
 * book's workspace (`/novels/$novelId`, W4 Task 11) — the shelf stays the
 * new-book action's target, the create dialog is writing's across a
 * boundary the shell does not cross. The menu keeps the quick menu's
 * popover discipline: arrows walk with wrap, Escape closes and returns
 * focus, an outside press closes without stealing focus.
 *
 * The nav's Editor door is live with the workspace (Task 11): it opens
 * the active book's workspace and wears the active face on a workspace
 * route; with no book standing it waits honestly disabled. The Wissen door
 * is live with the lore graph (W5 Task 3): it opens the active book's graph
 * and wears the active face on either knowledge surface — the graph or the
 * dossiers (W5 Task 5), one area with two surfaces. Planung and Einstellungen
 * keep their later-wave notes.
 *
 * The user menu the draft's tile 4 draws (Autorenname bearbeiten,
 * Tagesziel festlegen, Einstellungen, Abmelden) rides the settings wave
 * (Task 19's author profile and goal surfaces) — no action exists yet, so
 * the block ships as the drafted display chip, not a dead menu.
 *
 * Icon faces (spec §6.9): the draft's Material names pin concepts, the app
 * keeps its own glyphs — collections_bookmark → bookmarkCollection,
 * edit_note → editNote, hub → hub, schema → schema, settings → settings,
 * unfold_more → unfoldMore, dark_mode → theme.
 */
import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import {
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type KeyboardEvent,
} from "react";

import type { Novel } from "../lib/api/client";
import { client } from "../lib/api/client";
import { PALETTE } from "../lib/cover/BookCover";
import { coverModel } from "../lib/cover/cover";
import { useTranslation, type MessageKey } from "../lib/i18n";
import { queryClient, useSettingsQuery } from "../lib/query";
import { SAVE_FACES, SAVE_TONE_CLASS, useSaveStatus } from "../lib/saveStatus";
import { applyTheme, type Theme } from "../lib/theme";
import { Icon, type IconName } from "../ui/icons";
import { useChromeNovels } from "./chrome";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The shell's focus ring on every control the rail offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The expanded rail's labels: zero width and invisible while collapsed,
 *  revealed as the rail glides open — and always open on a coarse pointer,
 *  which has no hover to open it with. The reveal is instant on purpose:
 *  an opacity fade would spend the glide at partial opacity, where the
 *  ink's AA contrast blends below the floor (the axe gate measures the
 *  live DOM, mid-transition included); the width glide carries the
 *  drafted motion. */
const LABEL =
  "w-0 overflow-hidden whitespace-nowrap opacity-0 transition-[width] duration-200 group-hover/rail:w-auto group-hover/rail:opacity-100 group-focus-within/rail:w-auto group-focus-within/rail:opacity-100 pointer-coarse:w-auto pointer-coarse:opacity-100";

/** The nav's five entries in the draft's order. The shelf and the editor
 *  have routes (the editor's is the active book's workspace, resolved at
 *  render); the rest wait honestly disabled, each with its later-wave note. */
const NAV: readonly {
  label: MessageKey;
  icon: IconName;
  to?: string;
  note?: MessageKey;
}[] = [
  { label: "shell.nav.shelf", icon: "bookmarkCollection", to: "/" },
  { label: "shell.nav.editor", icon: "editNote", note: "shell.nav.editor.note" },
  { label: "shell.nav.knowledge", icon: "hub", note: "shell.nav.knowledge.note" },
  { label: "shell.nav.planning", icon: "schema", note: "shell.nav.planning.note" },
  { label: "shell.nav.settings", icon: "settings", note: "shell.nav.settings.note" },
];

/** The novel status words the menu's progress meta speaks — the shelf's
 *  own vocabulary, read from the merged catalog (the key union is
 *  compile-checked, so a dropped key fails the build, never silently).
 *  The chrome and the shelf render the same row's same words; the
 *  vocabulary consolidates into the shell when the workspace lands. */
const STATUS_KEYS: Record<string, MessageKey> = {
  draft: "writing.shelf.status.draft",
  revision: "writing.shelf.status.revision",
  final: "writing.shelf.status.final",
};

/** The cover chip: the cover system's channel pigment and monogram at the
 *  draft's chip size — the model decides, the palette stays the one literal
 *  record (R2), never a second palette. The monogram is visible text, so it
 *  is NOT aria-hidden: the switcher's name carries it explicitly, and the
 *  menu rows' name-from-content picks it up — both agree with what the eye
 *  sees (WCAG 2.5.3). */
function CoverChip({ novel, className }: { novel: Novel; className: string }) {
  const model = coverModel({ title: novel.title, genre: novel.genre, size: "mini" });
  const palette = PALETTE[model.channel];
  return (
    <span
      className={`flex shrink-0 items-center justify-center rounded-sm ${palette.ground} ${palette.ink} ${className}`}
    >
      <span className={`${SERIF} text-[7px] font-bold leading-none`}>{model.monogramText}</span>
    </span>
  );
}

/** The initials the user block's avatar wears: the first and last word's
 *  initial of the author name, or of the email's local part — „H. Calder"
 *  and „h.calder@…" both read HC. No source, no initials (the person glyph
 *  answers). */
function initialsFrom(source: string | null): string | null {
  if (source === null) return null;
  const words = source.trim().split(/[\s._-]+/).filter((word) => word.length > 0);
  if (words.length === 0) return null;
  const first = Array.from(words[0].toUpperCase())[0] ?? "";
  const last = words.length > 1 ? (Array.from(words[words.length - 1].toUpperCase())[0] ?? "") : "";
  return first + last || null;
}

/** The theme cycle's three states: the row's null is the system's own. */
const THEME_CYCLE: Record<"system" | Theme, { next: Theme | null; name: MessageKey }> = {
  system: { next: "light", name: "shell.theme.system" },
  light: { next: "dark", name: "shell.theme.light" },
  dark: { next: null, name: "shell.theme.dark" },
};

export function IconRail() {
  const t = useTranslation();
  const navigate = useNavigate();
  const { novels, active, bookId } = useChromeNovels();
  const settings = useSettingsQuery();
  // The live sync owner (Task 12): one state, the rail foot, the topbar
  // chip and the editor foot read the same hook.
  const saveStatus = useSaveStatus();
  const saveFace = SAVE_FACES[saveStatus];
  const saveTone = SAVE_TONE_CLASS[saveFace.tone];
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  // The Wissen door's active face: the knowledge area is matched — the
  // graph or the dossiers route (the route ids, never a parsed pathname —
  // the chrome's own discipline). One area, two surfaces (W5 Tasks 3/5).
  const knowledgeActive = useRouterState({
    select: (state) =>
      state.matches.some(
        (match) =>
          match.routeId === "/novels/$novelId/knowledge/graph" ||
          match.routeId === "/novels/$novelId/knowledge/dossiers",
      ),
  });

  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPos, setMenuPos] = useState<{ left: number; top: number } | null>(null);
  const menuId = useId();
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const menuRef = useRef<HTMLDivElement | null>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // The menu's population: the active book leads, the rest newest first —
  // archived books are not switchable works (the shelf's own rule).
  const rows = (novels.data ?? []).filter((novel) => novel.archived_at == null);
  // The cover chip's monogram is visible text, so it rides the switcher's
  // accessible name too (WCAG 2.5.3) — the cover model decides it, the
  // same source the chip renders.
  const activeMonogram =
    active !== null
      ? coverModel({ title: active.title, genre: active.genre, size: "mini" }).monogramText
      : null;
  const ordered =
    active !== null
      ? [active, ...rows.filter((novel) => novel.id !== active.id).sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at))]
      : [...rows].sort((a, b) => Date.parse(b.updated_at) - Date.parse(a.updated_at));
  // The new-book action is the menu's last item; on an empty or unreachable
  // list it stands alone.
  const itemCount = novels.isSuccess && ordered.length > 0 ? ordered.length + 1 : 1;

  const closeMenu = useCallback((returnFocus: boolean) => {
    setMenuOpen(false);
    if (returnFocus) triggerRef.current?.focus();
  }, []);

  // The menu escapes the rail's overflow clip with fixed positioning,
  // docked 4px off the chip (tile 2) and clamped into the viewport — the
  // quick menu's clamp discipline, measured before paint and on resize.
  useLayoutEffect(() => {
    if (!menuOpen) {
      setMenuPos(null);
      return;
    }
    const compute = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = 240; // w-60
      const height = menuRef.current?.offsetHeight ?? 320;
      const margin = 8;
      const left = Math.max(margin, Math.min(rect.right + 4, window.innerWidth - width - margin));
      const top = Math.max(margin, Math.min(rect.top, window.innerHeight - height - margin));
      setMenuPos({ left, top });
    };
    compute();
    window.addEventListener("resize", compute);
    return () => window.removeEventListener("resize", compute);
  }, [menuOpen]);

  // While the menu stands: Escape closes innermost-first, an outside press
  // closes without stealing focus — the quick menu's discipline.
  useEffect(() => {
    if (!menuOpen) return;
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      closeMenu(true);
    }
    function onDown(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [menuOpen, closeMenu]);

  // Opening moves focus to the menu's first row — the active book leads.
  useEffect(() => {
    if (menuOpen) itemRefs.current[0]?.focus();
  }, [menuOpen]);

  function triggerKey(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    setMenuOpen(true);
  }

  /** The menu's keyboard: arrows walk with wrap, Home/End jump, Enter/Space
   *  activate the row, Tab closes and advances past the trigger. */
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
      closeMenu(true);
      return;
    } else return;
    event.preventDefault();
    itemRefs.current[next]?.focus();
  }

  /** The menu row's meta line: the row's own genre and facts — the drafted
   *  progress (floored percent, the shelf's rule) with the status word when
   *  a target measures it, the chapter count otherwise. Never the mock. */
  function bookMeta(novel: Novel): string {
    const target = novel.target_words;
    const fact =
      target != null && target > 0
        ? t("writing.shelf.card.percent", {
            percent: Math.floor(Math.min(100, Math.max(0, (novel.word_count / target) * 100))),
          }) +
          (novel.status != null && novel.status in STATUS_KEYS
            ? ` (${t(STATUS_KEYS[novel.status])})`
            : "")
        : t("writing.shelf.chapters", { count: novel.chapter_count });
    return [novel.genre, fact].filter(Boolean).join(" • ");
  }

  // The theme toggle: the row's choice (null = system), applied at once and
  // PATCHed through the theme's own door; a refusal restores the prior
  // appearance, success refreshes the cached row.
  const theme = settings.data?.theme ?? null;
  const themeState: "system" | Theme = theme === "light" || theme === "dark" ? theme : "system";
  const cycle = THEME_CYCLE[themeState];
  const nextName = cycle.next === null ? t("shell.theme.system") : t(THEME_CYCLE[cycle.next].name);
  const themeLabel = t("shell.rail.theme", { current: t(cycle.name), next: nextName });
  async function toggleTheme() {
    const previous = theme;
    const next = cycle.next;
    applyTheme(next);
    try {
      const { response } = await client.PATCH("/api/settings/theme", { body: { theme: next } });
      if (!response.ok) throw new Error(`refused: ${response.status}`);
      void queryClient.invalidateQueries({ queryKey: ["settings"] });
    } catch {
      applyTheme(previous === "light" || previous === "dark" ? previous : null);
    }
  }

  // The user block: author_name first, the email label when none is stored,
  // the honest profile neutral when neither exists — never a tier.
  const authorName = settings.data?.author_name ?? null;
  const email = settings.data?.email ?? null;
  const userName = authorName ?? email ?? t("shell.rail.user");
  const initials = initialsFrom(authorName ?? (email !== null ? email.split("@")[0] : null));
  const userTitle =
    authorName !== null || email !== null
      ? t("shell.rail.user.named", { name: userName })
      : t("shell.rail.user");

  return (
    <aside className="group/rail absolute inset-y-0 left-0 z-30 flex w-full select-none flex-col justify-between overflow-hidden border-r border-border bg-panel px-2 py-3 transition-[width] duration-200 hover:w-[168px] focus-within:w-[168px] pointer-coarse:w-[168px]">
      <div className="flex w-full flex-col items-center gap-4">
        {/* The brand head: the monogram is the way home; the expanded rail
            names the atelier beside it (tile 1). */}
        <div className="flex w-full items-center justify-center gap-2.5 group-hover/rail:justify-start pointer-coarse:justify-start">
          <Link
            to="/"
            aria-label={t("app.title")}
            title={`${t("app.title")} / ${t("shell.brand.tagline")}`}
            className={`${SERIF} flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary text-base font-bold text-primary-foreground shadow-sm transition-all hover:opacity-95 group-hover/rail:h-8 group-hover/rail:w-8 pointer-coarse:h-8 pointer-coarse:w-8 ${FOCUS}`}
          >
            N
          </Link>
          <span className={`${LABEL} flex flex-col leading-tight`}>
            <span className="text-meta font-bold text-foreground">{t("app.title")}</span>
            <span className="text-[10px] text-muted">{t("shell.brand.tagline")}</span>
          </span>
        </div>

        {/* The book switcher: the active novel's cover chip and name, the
            unfold_more mark; the menu of real novels docks off it. */}
        <div ref={wrapperRef} className="relative w-full">
          <button
            type="button"
            ref={triggerRef}
            aria-haspopup="menu"
            aria-expanded={menuOpen}
            aria-controls={menuId}
            aria-label={
              active !== null
                ? t("shell.rail.switcher.named", { title: `${activeMonogram} ${active.title}` })
                : t("shell.rail.switcher")
            }
            onClick={() => setMenuOpen((previous) => !previous)}
            onKeyDown={triggerKey}
            className={`flex w-full flex-col items-center justify-center gap-0.5 rounded border border-border bg-surface-container-low p-1 transition-colors hover:border-primary group-hover/rail:flex-row group-hover/rail:justify-between group-hover/rail:gap-1.5 group-hover/rail:p-1.5 pointer-coarse:flex-row pointer-coarse:justify-between pointer-coarse:gap-1.5 pointer-coarse:p-1.5 ${FOCUS}`}
          >
            {active !== null ? (
              <CoverChip novel={active} className="h-6 w-7 group-hover/rail:w-5 pointer-coarse:w-5" />
            ) : (
              <span
                aria-hidden="true"
                className="flex h-6 w-7 shrink-0 items-center justify-center text-muted group-hover/rail:w-5 pointer-coarse:w-5"
              >
                <Icon name="books" size={14} />
              </span>
            )}
            {/* The space keeps the monogram and the title separate words in
                the visible text — the name carries both, in order. */}
            {" "}
            <span className={`${LABEL} ${SERIF} min-w-0 flex-1 truncate text-left text-meta font-semibold text-foreground`}>
              {active?.title}
            </span>
            <span className="shrink-0 text-muted">
              <Icon name="unfoldMore" size={14} />
            </span>
          </button>
          {menuOpen && (
            <div
              ref={menuRef}
              id={menuId}
              role="menu"
              aria-label={t("shell.rail.menu.title")}
              style={{ position: "fixed", left: menuPos?.left ?? 0, top: menuPos?.top ?? 0 }}
              className="z-50 w-60 space-y-1.5 rounded-lg border border-border bg-surface-container-lowest p-2.5 shadow-overlay"
            >
              <div className="flex items-center justify-between px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-muted">
                <span>{t("shell.rail.menu.title")}</span>
                {novels.isPending ? (
                  <span aria-hidden="true" className="block h-3 w-12 animate-pulse rounded bg-soft" />
                ) : (
                  <span className="font-mono text-foreground">
                    {novels.isSuccess
                      ? t("shell.rail.menu.count", { count: ordered.length })
                      : "—"}
                  </span>
                )}
              </div>
              {novels.isSuccess && ordered.length > 0 ? (
                ordered.map((novel, at) => (
                  <button
                    key={novel.id}
                    type="button"
                    // The rows are menu actions, not links: the router marks
                    // every Link to the current route aria-current="page",
                    // which would flatten the active book's mark. Each row
                    // opens its book's workspace (W4 Task 11).
                    role="menuitem"
                    aria-current={novel.id === active?.id ? "true" : undefined}
                    ref={(node) => {
                      itemRefs.current[at] = node;
                    }}
                    onKeyDown={(event) => itemKey(event, at)}
                    onClick={() => {
                      closeMenu(true);
                      void navigate({ to: "/novels/$novelId", params: { novelId: novel.id } });
                    }}
                    className={`flex w-full items-center gap-2.5 rounded-md border p-2 text-left transition-colors ${
                      novel.id === active?.id
                        ? "border-primary/30 bg-primary/10"
                        : "border-transparent hover:bg-surface-container-low"
                    } ${FOCUS}`}
                  >
                    <CoverChip novel={novel} className="h-8 w-6 rounded" />
                    {/* The space keeps monogram and title separate words —
                        the row's name-from-content and its visible text
                        agree (WCAG 2.5.3). */}
                    {" "}
                    <span className="min-w-0 flex-1">
                      <span className={`${SERIF} flex items-center justify-between gap-1 truncate text-meta font-bold text-foreground`}>
                        <span className="truncate">{novel.title}</span>
                        {novel.id === active?.id && (
                          <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-primary" />
                        )}
                      </span>
                      <span className="block truncate text-[10px] text-muted">{bookMeta(novel)}</span>
                    </span>
                  </button>
                ))
              ) : novels.isError ? (
                <p className="px-2 py-1.5 text-meta text-muted">
                  {t("shell.rail.menu.unavailable")}
                </p>
              ) : novels.isPending ? (
                <span aria-hidden="true" className="block h-8 animate-pulse rounded bg-soft" />
              ) : (
                <p className="px-2 py-1.5 text-meta text-muted">{t("shell.rail.menu.empty")}</p>
              )}
              <div aria-hidden="true" className="h-px bg-border" />
              <button
                type="button"
                role="menuitem"
                ref={(node) => {
                  itemRefs.current[itemCount - 1] = node;
                }}
                onKeyDown={(event) => itemKey(event, itemCount - 1)}
                onClick={() => {
                  closeMenu(true);
                  void navigate({ to: "/" });
                }}
                className={`flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-meta font-semibold text-primary transition-colors hover:bg-primary/10 ${FOCUS}`}
              >
                <Icon name="plus" size={16} />
                <span>{t("shell.rail.newBook")}</span>
              </button>
            </div>
          )}
        </div>

        <div aria-hidden="true" className="h-px w-8 bg-border" />

        {/* The nav: the shelf and the editor live (the editor opens the
            active book's workspace, Task 11), the three later-wave doors
            honestly disabled with their notes. */}
        <nav aria-label={t("shell.nav.label")} className="flex w-full flex-col items-center gap-1.5">
          {NAV.map((entry) => {
            const face = (isCurrent: boolean) =>
              `flex w-full items-center justify-center gap-0 rounded-lg border px-2 py-1.5 transition-colors group-hover/rail:justify-start group-hover/rail:gap-2.5 pointer-coarse:justify-start pointer-coarse:gap-2.5 ${
                isCurrent
                  ? "border-primary/20 bg-primary/10 font-semibold text-primary"
                  : "border-transparent text-muted hover:bg-surface-container-low hover:text-foreground"
              } ${FOCUS}`;
            const children = (
              <>
                <span className="shrink-0">
                  <Icon name={entry.icon} size={22} />
                </span>
                <span className={`${LABEL} text-meta font-medium`}>{t(entry.label)}</span>
              </>
            );
            // The editor's door is the active book's workspace — with no
            // book standing there is nothing to edit, and the note says so.
            if (entry.label === "shell.nav.editor") {
              return active !== null ? (
                <Link
                  key={entry.label}
                  to="/novels/$novelId"
                  params={{ novelId: active.id }}
                  aria-label={t(entry.label)}
                  title={t(entry.label)}
                  aria-current={bookId !== null ? "page" : undefined}
                  className={face(bookId !== null)}
                >
                  {children}
                </Link>
              ) : (
                <button
                  key={entry.label}
                  type="button"
                  disabled
                  aria-label={t(entry.label)}
                  title={entry.note !== undefined ? t(entry.note) : undefined}
                  className="flex w-full cursor-not-allowed items-center justify-center gap-0 rounded-lg border border-transparent px-2 py-1.5 text-muted opacity-50 group-hover/rail:justify-start group-hover/rail:gap-2.5 pointer-coarse:justify-start pointer-coarse:gap-2.5"
                >
                  {children}
                </button>
              );
            }
            // The Wissen door is the active book's lore graph (W5 Task 3 —
            // the later-wave interim retired): with a book standing it opens
            // the graph and wears the active face on the graph route; with no
            // book it waits honestly disabled, the note saying so.
            if (entry.label === "shell.nav.knowledge") {
              return active !== null ? (
                <Link
                  key={entry.label}
                  to="/novels/$novelId/knowledge/graph"
                  params={{ novelId: active.id }}
                  aria-label={t(entry.label)}
                  title={t(entry.label)}
                  aria-current={knowledgeActive ? "page" : undefined}
                  className={face(knowledgeActive)}
                >
                  {children}
                </Link>
              ) : (
                <button
                  key={entry.label}
                  type="button"
                  disabled
                  aria-label={t(entry.label)}
                  title={entry.note !== undefined ? t(entry.note) : undefined}
                  className="flex w-full cursor-not-allowed items-center justify-center gap-0 rounded-lg border border-transparent px-2 py-1.5 text-muted opacity-50 group-hover/rail:justify-start group-hover/rail:gap-2.5 pointer-coarse:justify-start pointer-coarse:gap-2.5"
                >
                  {children}
                </button>
              );
            }
            return entry.to !== undefined ? (
              <Link
                key={entry.label}
                to={entry.to}
                aria-label={t(entry.label)}
                title={t(entry.label)}
                aria-current={pathname === entry.to ? "page" : undefined}
                className={face(pathname === entry.to)}
              >
                {children}
              </Link>
            ) : (
              <button
                key={entry.label}
                type="button"
                disabled
                aria-label={t(entry.label)}
                title={entry.note !== undefined ? t(entry.note) : undefined}
                className="flex w-full cursor-not-allowed items-center justify-center gap-0 rounded-lg border border-transparent px-2 py-1.5 text-muted opacity-50 group-hover/rail:justify-start group-hover/rail:gap-2.5 pointer-coarse:justify-start pointer-coarse:gap-2.5"
              >
                {children}
              </button>
            );
          })}
        </nav>
      </div>

      {/* The foot: sync, theme, user — the draft's three marks, no tier. */}
      <div className="flex w-full flex-col items-center gap-3 border-t border-border/80 pt-3">
        {/* The sync dot: the live autosave owner's face (tile 3) — green at
            rest, amber pulsing while the write is engaged, red on a refusal.
            One state with the topbar chip and the editor foot; the honest
            sub-label is the tooltip. */}
        <div
          className="flex w-full items-center justify-center gap-2 group-hover/rail:justify-start pointer-coarse:justify-start"
          title={t(saveFace.note)}
        >
          <span
            aria-hidden="true"
            className={`h-2.5 w-2.5 shrink-0 rounded-full ring-4 ${saveTone.dot} ${saveTone.ring} ${
              saveStatus === "saving" ? "animate-pulse" : ""
            }`}
          />
          <span className={`${LABEL} text-meta font-medium ${saveTone.text}`}>{t(saveFace.label)}</span>
        </div>

        {/* The theme toggle: one button, three states, the row's own door. */}
        <button
          type="button"
          aria-label={themeLabel}
          title={themeLabel}
          onClick={() => void toggleTheme()}
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded text-muted transition-colors hover:bg-surface-container-low hover:text-foreground ${FOCUS}`}
        >
          <Icon name="theme" size={19} />
        </button>

        {/* The user block: initials and name, author_name → email fallback,
            the honest neutral when neither stands. Display only — the
            drafted user menu's actions ride the settings wave (Task 19). */}
        <div
          className="flex w-full items-center justify-center gap-2 rounded border border-transparent p-0 transition-colors group-hover/rail:justify-start group-hover/rail:border-border/40 group-hover/rail:bg-surface-container-low/60 group-hover/rail:p-1.5 pointer-coarse:justify-start pointer-coarse:border-border/40 pointer-coarse:bg-surface-container-low/60 pointer-coarse:p-1.5"
          title={userTitle}
        >
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-border bg-surface-container-low text-meta font-semibold text-foreground transition-all group-hover/rail:h-6 group-hover/rail:w-6 group-hover/rail:bg-surface-container-lowest group-hover/rail:text-[10px] group-hover/rail:font-bold pointer-coarse:h-6 pointer-coarse:w-6 pointer-coarse:bg-surface-container-lowest pointer-coarse:text-[10px] pointer-coarse:font-bold">
            {initials ?? <Icon name="person" size={16} />}
          </span>
          <span className={`${LABEL} text-meta font-medium text-foreground`}>{userName}</span>
        </div>
      </div>
    </aside>
  );
}
