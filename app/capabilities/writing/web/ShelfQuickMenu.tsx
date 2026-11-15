/**
 * The per-card quick menu — the `shelf-quick-menu` draft's four panels on
 * the shell's tokens, the filter popover's dialog discipline (Task 7).
 *
 * The „···" trigger (the draft's `more_vert`, a 28px target at the card's
 * top-right) opens a w-64 popover docked 4px under it: the „Buch-Optionen"
 * eyebrow, Duplizieren / Exportieren / Archivieren, a hairline, and the
 * honest meta line — „Letzter Export:" with the row's `last_exported_at`
 * localized, or the dash when none. An archived book swaps the header to
 * „Archivierte Optionen", the third row to Wiederherstellen (the primary
 * ink's hope signal), and the meta line to „Archiviert am:".
 *
 * Archivieren is reversible, never red: it opens the draft's confirm
 * popover („Ins Archiv stellen?", the book's own name in the body, ghost
 * Abbrechen + secondary Archivieren) — no modal, no alarm colour.
 * Wiederherstellen acts at once, the draft's symmetric return. While an
 * action runs the menu stays open, the acting row spins („… " + „Bitte
 * warten"), the rest wait dimmed. A refusal closes the menu and leaves the
 * draft's gentle error line under it — the muted danger as an accent rule
 * and symbol only, the loss-free message, and „Erneut versuchen" which
 * re-runs the very action. Export keeps the menu open on success so the
 * meta line refetches to the fresh date; the ZIP artifact lands through
 * the browser's download seam.
 *
 * Semantics: a non-modal dialog (`role="dialog"`, labelled, the trigger
 * `aria-haspopup`/`aria-expanded`/`aria-controls`); opening moves focus to
 * the first action (the confirm to its action button); Escape is staged
 * innermost-first (confirm → menu → trigger), an outside press closes
 * without stealing focus, and neither closes while an action is in flight.
 * The error line is a polite `role="alert"` on the card.
 *
 * Icon faces (spec §6.9): the draft's Material names pin concepts, the app
 * keeps its own glyphs — content_copy → copy, inventory_2 → archive,
 * unarchive → unarchive, more_vert → moreVert, download → export (the
 * pre-W0 export face), error_outline → warning (the set's failure face),
 * arrow/↺ → refresh; progress_activity is the shell's border spinner.
 */

import { forwardRef, useEffect, useId, useLayoutEffect, useRef, useState } from "react";

import type { Novel } from "@shell/lib/api/client";
import { formatDate } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import { useArchiveNovel, useDuplicateNovel, useExportNovel } from "@shell/lib/query";
import { Icon, type IconName } from "@shell/ui/icons";

/** The shell's focus ring on every control the menu offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The meta line's date face — the draft's „14. Feb. 2026" grammar. */
const DATE_OPTS = { day: "numeric", month: "short", year: "numeric" } as const;

/** The four actions; archive and restore share the one PATCH. */
type Action = "duplicate" | "export" | "archive" | "restore";
type View = "closed" | "menu" | "confirm";

/** The shell's busy face (the provisioning step's spinner): a ring with
 *  one transparent quarter, turning. No glyph — the motion is the mark. */
function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="h-3.5 w-3.5 shrink-0 animate-spin rounded-full border border-primary border-t-transparent"
    />
  );
}

/**
 * Hand a blob to the browser as a download: a temporary anchor with the
 * `download` attribute, clicked once, removed, its object URL revoked one
 * task later (the navigation reads the URL asynchronously). The pre-W0
 * interchange seam, kept — the archive lives in Downloads, not the page.
 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

/** One action row — the draft's label geometry, the busy spinner in the
 *  icon's place, „Bitte warten" standing right while it runs. The tone is
 *  the draft's: neutral ink for duplicate/export, the archive's secondary
 *  grey (never red), the restore's primary hope signal. */
const MenuRow = forwardRef<
  HTMLButtonElement,
  {
    icon: IconName;
    label: string;
    busy: boolean;
    disabled: boolean;
    onClick: () => void;
    tone?: "primary" | "settings";
  }
>(function MenuRow({ icon, label, busy, disabled, onClick, tone }, ref) {
  const t = useTranslation();
  const toneClass =
    tone === "primary"
      ? "bg-primary/5 font-medium text-primary hover:bg-primary/10"
      : tone === "settings"
        ? "text-secondary hover:bg-surface-container"
        : "text-foreground hover:bg-surface-container";
  const iconClass = tone === "primary" ? "text-primary" : tone === "settings" ? "text-secondary" : "text-muted";
  const stateClass = busy ? "bg-surface-container opacity-60" : disabled ? "opacity-40" : "";
  return (
    <button
      type="button"
      ref={ref}
      disabled={disabled}
      onClick={onClick}
      className={`flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-label transition-colors ${toneClass} ${stateClass} ${disabled ? "cursor-not-allowed" : ""} ${FOCUS}`}
    >
      {busy ? (
        <Spinner />
      ) : (
        <span className={iconClass}>
          <Icon name={icon} size={16} />
        </span>
      )}
      <span className={busy ? "font-medium text-foreground" : ""}>{busy ? `${label} …` : label}</span>
      {busy && <span className="ml-auto text-meta text-muted">{t("writing.shelf.menu.wait")}</span>}
    </button>
  );
});

export function ShelfQuickMenu({ novel }: { novel: Novel }) {
  const t = useTranslation();
  const [view, setView] = useState<View>("closed");
  const [busy, setBusy] = useState<Action | null>(null);
  const [error, setError] = useState<Action | null>(null);
  const popoverId = useId();
  const wrapperRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const firstRowRef = useRef<HTMLButtonElement | null>(null);
  const exportRowRef = useRef<HTMLButtonElement | null>(null);
  const archiveRowRef = useRef<HTMLButtonElement | null>(null);
  const confirmActionRef = useRef<HTMLButtonElement | null>(null);
  /** Returning from the confirm (Escape or Abbrechen) lands focus back on
   *  the archive row, not the menu's first action — the staged return. */
  const returnToArchiveRef = useRef(false);
  /** Export keeps the menu open, but its row was disabled while busy — the
   *  browser drops a disabled row's focus to the body. Once the ask settles
   *  and the row re-enables, focus returns to it so a keyboard reader is
   *  never stranded mid-menu. */
  const focusExportOnIdleRef = useRef(false);
  /** The popover overhangs its narrow card freely (the article carries no
   *  clip), but it must never leave the viewport: at the lg-band's leftmost
   *  column a right-aligned 256px menu would run off the left edge. Clamp
   *  its left edge into the viewport, measured from the trigger when a
   *  surface opens and on resize. `null` keeps the draft's right-0 anchor. */
  const [menuLeft, setMenuLeft] = useState<number | null>(null);

  const duplicate = useDuplicateNovel();
  const exportNovel = useExportNovel();
  const archive = useArchiveNovel();

  const archived = novel.archived_at != null;
  const open = view !== "closed";

  /** Close; `returnFocus` is the Escape/success path — an outside press
   *  leaves the focus where the reader put it. A trigger unmounted by the
   *  refetch (the archived card left the grid) is simply not focused. */
  function close(returnFocus: boolean) {
    setView("closed");
    if (returnFocus) triggerRef.current?.focus();
  }

  // While a surface stands: Escape yields innermost-first, an outside
  // press closes. Neither interrupts an action in flight — the busy menu
  // holds until the answer lands. The listeners leave when it closes.
  useEffect(() => {
    if (!open) return;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape" || busy !== null) return;
      event.preventDefault();
      if (view === "confirm") {
        returnToArchiveRef.current = true;
        setView("menu");
      } else {
        setView("closed");
        triggerRef.current?.focus();
      }
    }
    function onDown(event: MouseEvent) {
      if (busy !== null) return;
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setView("closed");
      }
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open, view, busy]);

  // Opening moves focus to the surface's own first control — the menu's
  // first action, the confirm's action button (the popover discipline).
  // A return from the confirm lands on the archive row instead.
  useEffect(() => {
    if (view === "menu") {
      if (returnToArchiveRef.current) {
        returnToArchiveRef.current = false;
        archiveRowRef.current?.focus();
      } else {
        firstRowRef.current?.focus();
      }
    } else if (view === "confirm") {
      confirmActionRef.current?.focus();
    }
  }, [view]);

  // Export's focus restore: the row re-enables when busy clears (this effect
  // runs after that render), so the focus lands on a live control, not the
  // disabled one the browser just blurred.
  useEffect(() => {
    if (busy === null && focusExportOnIdleRef.current) {
      focusExportOnIdleRef.current = false;
      exportRowRef.current?.focus();
    }
  }, [busy]);

  // Clamp the popover into the viewport — the leftmost lg-band card would
  // otherwise overhang off the left edge once the article's clip is gone.
  // Measured before paint (no flash at the wrong anchor), recomputed on
  // resize; the draft's right-aligned overhang stands wherever it fits.
  const surfaceVisible = view !== "closed" || error !== null;
  useLayoutEffect(() => {
    if (!surfaceVisible || wrapperRef.current === null) {
      setMenuLeft(null);
      return;
    }
    const compute = () => {
      const rect = wrapperRef.current?.getBoundingClientRect();
      if (!rect) return;
      const width = 256; // w-64
      const margin = 8;
      const desired = rect.right - width; // the draft's right-aligned anchor
      const clamped = Math.max(margin, Math.min(desired, window.innerWidth - width - margin));
      setMenuLeft(clamped - rect.left);
    };
    compute();
    window.addEventListener("resize", compute);
    return () => window.removeEventListener("resize", compute);
  }, [surfaceVisible]);

  /** Run an action: busy on its row, the menu open; success refetches the
   *  shelf (the hook invalidates `["novels"]`), a refusal leaves the card's
   *  error line. Export alone keeps the menu open — its meta line refreshes. */
  function run(action: Action) {
    setError(null);
    setBusy(action);
    const fail = () => {
      setBusy(null);
      setError(action);
      setView("closed");
    };
    if (action === "duplicate") {
      duplicate.mutate(novel.id, {
        onSuccess: () => {
          setBusy(null);
          close(true);
        },
        onError: fail,
      });
    } else if (action === "export") {
      exportNovel.mutate(novel.id, {
        onSuccess: (data) => {
          downloadBlob(data.blob, data.filename);
          focusExportOnIdleRef.current = true;
          setBusy(null);
        },
        onError: fail,
      });
    } else {
      archive.mutate(
        { novelId: novel.id, archived: action === "archive" },
        {
          onSuccess: () => {
            setBusy(null);
            close(true);
          },
          onError: fail,
        },
      );
    }
  }

  const errorKey = {
    duplicate: "writing.shelf.menu.error.duplicate",
    export: "writing.shelf.menu.error.export",
    archive: "writing.shelf.menu.error.archive",
    restore: "writing.shelf.menu.error.restore",
  } as const;

  /** The clamped horizontal anchor for every popover surface (menu,
   *  confirm, error notice) — they share the trigger's wrapper. */
  const surfaceStyle = menuLeft !== null ? { left: menuLeft, right: "auto" as const } : undefined;

  return (
    <div ref={wrapperRef} className="absolute right-2 top-2 z-50">
      {/* The 28px trigger — the draft's two faces: neutral closed, the
          primary border and ink while the menu stands. */}
      <button
        type="button"
        ref={triggerRef}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={popoverId}
        aria-label={t("writing.shelf.card.options")}
        onClick={() => {
          // The busy guard matches Escape and the outside press: an action
          // in flight holds the menu. Opening dismisses a standing error
          // notice for good — engaging the menu is the reader's answer to
          // it, so it never reappears stale on the next close.
          if (busy !== null) return;
          if (open) {
            close(false);
          } else {
            setError(null);
            setView("menu");
          }
        }}
        className={
          open
            ? `flex h-7 w-7 items-center justify-center rounded-md border border-primary bg-surface text-primary shadow-sm transition-colors ${FOCUS}`
            : `flex h-7 w-7 items-center justify-center rounded-md border border-border bg-surface text-muted shadow-sm transition-colors hover:text-foreground ${FOCUS}`
        }
      >
        <Icon name="moreVert" size={18} />
      </button>

      {view === "menu" && (
        <div
          id={popoverId}
          role="dialog"
          aria-label={archived ? t("writing.shelf.menu.titleArchived") : t("writing.shelf.menu.title")}
          style={surfaceStyle}
          className="absolute right-0 top-full z-50 mt-1 w-64 rounded-xl border border-outline-variant bg-surface-container-lowest p-1.5 shadow-lg"
        >
          <div className="mb-1 border-b border-rule px-2.5 py-1 text-eyebrow font-semibold uppercase tracking-wider text-muted">
            {archived ? t("writing.shelf.menu.titleArchived") : t("writing.shelf.menu.title")}
          </div>
          <MenuRow
            ref={firstRowRef}
            icon="copy"
            label={t("writing.shelf.menu.duplicate")}
            busy={busy === "duplicate"}
            disabled={busy !== null}
            onClick={() => run("duplicate")}
          />
          <MenuRow
            ref={exportRowRef}
            icon="export"
            label={t("writing.shelf.menu.export")}
            busy={busy === "export"}
            disabled={busy !== null}
            onClick={() => run("export")}
          />
          {archived ? (
            <MenuRow
              icon="unarchive"
              label={t("writing.shelf.menu.restore")}
              busy={busy === "restore"}
              disabled={busy !== null}
              onClick={() => run("restore")}
              tone="primary"
            />
          ) : (
            <MenuRow
              ref={archiveRowRef}
              icon="archive"
              label={t("writing.shelf.menu.archive")}
              busy={false}
              disabled={busy !== null}
              onClick={() => setView("confirm")}
              tone="settings"
            />
          )}
          {/* The hairline and the honest meta line. */}
          <div className="my-1 border-t border-rule" />
          <div className="flex items-center justify-between px-2.5 py-1 text-meta text-muted">
            <span>{archived ? t("writing.shelf.menu.archivedAt") : t("writing.shelf.menu.lastExport")}</span>
            {archived ? (
              <span className="font-medium text-foreground">{formatDate(novel.archived_at as string, DATE_OPTS)}</span>
            ) : novel.last_exported_at != null ? (
              <span className="font-mono text-foreground">{formatDate(novel.last_exported_at, DATE_OPTS)}</span>
            ) : (
              <span className="font-mono">—</span>
            )}
          </div>
        </div>
      )}

      {view === "confirm" && (
        <div
          id={popoverId}
          role="dialog"
          aria-label={t("writing.shelf.menu.confirm.title")}
          style={surfaceStyle}
          className="absolute right-0 top-full z-50 mt-1 w-64 rounded-xl border border-outline-variant bg-surface-container-lowest p-4 shadow-lg"
        >
          <div className="flex items-start gap-2.5">
            <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded border border-border bg-surface-container-low text-primary">
              <Icon name="archive" size={16} />
            </div>
            <div>
              <h4 className="text-label font-semibold leading-tight text-foreground">
                {t("writing.shelf.menu.confirm.title")}
              </h4>
              <p className="mt-1 text-meta leading-snug text-muted">
                {t("writing.shelf.menu.confirm.body", { title: novel.title })}
              </p>
            </div>
          </div>
          <div className="mt-3 flex items-center justify-end gap-2 border-t border-rule pt-2">
            <button
              type="button"
              disabled={busy !== null}
              onClick={() => {
                returnToArchiveRef.current = true;
                setView("menu");
              }}
              className={`rounded border border-border px-2.5 py-1.5 text-meta text-muted transition-colors hover:bg-surface-container-low ${FOCUS} ${busy !== null ? "cursor-not-allowed opacity-50" : ""}`}
            >
              {t("writing.shelf.menu.confirm.cancel")}
            </button>
            <button
              type="button"
              ref={confirmActionRef}
              disabled={busy !== null}
              onClick={() => run("archive")}
              className={`inline-flex items-center gap-1.5 rounded border border-primary/20 bg-surface-container-low px-3 py-1.5 text-meta font-semibold text-primary transition-colors hover:bg-secondary-container ${FOCUS} ${busy !== null ? "cursor-not-allowed opacity-60" : ""}`}
            >
              {busy === "archive" && <Spinner />}
              {t("writing.shelf.menu.archive")}
            </button>
          </div>
        </div>
      )}

      {/* The gentle error line under the closed menu — the muted danger as
          an accent rule and symbol only, the loss-free message, the retry
          that re-runs the very action (archive returns to its confirm).
          Opening the menu clears it for good (the trigger's onClick), so it
          is dismissed by retry or by engaging the menu — never stale on a
          later close. */}
      {error !== null && view === "closed" && (
        <div
          role="alert"
          style={surfaceStyle}
          className="absolute right-0 top-full z-40 mt-1 w-64 rounded-lg border border-rule border-l-2 border-l-danger bg-surface-container-lowest p-2.5 shadow-lg"
        >
          <div className="flex items-start gap-1.5">
            <span className="mt-0.5 shrink-0 text-danger">
              <Icon name="warning" size={14} />
            </span>
            <div className="flex-1">
              <p className="text-meta leading-tight text-foreground">{t(errorKey[error])}</p>
              <button
                type="button"
                onClick={() => {
                  setView(error === "archive" ? "confirm" : "menu");
                  run(error);
                }}
                className={`mt-1 inline-flex items-center gap-1 text-meta font-medium text-primary underline underline-offset-2 transition-colors hover:text-foreground ${FOCUS}`}
              >
                {t("writing.shelf.error.retry")}
                <Icon name="refresh" size={12} />
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}