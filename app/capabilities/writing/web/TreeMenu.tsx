/**
 * The tree row's quick menu (W4 Task 13) — the shelf quick menu's popover
 * discipline re-owned for the explorer's rows. The workspace drafts draw
 * no rename/delete affordance on the tree, so the established pattern
 * applies (the brief's rule: no invented geometry): the „···" trigger
 * (`more_vert`, the shelf's own face at the row's scale) opens a labelled
 * non-modal dialog with the eyebrow and two rows — edit/rename and delete.
 * The actions hand off to the page's dialogs and close the menu; the
 * trigger's id rides along as the opener, so the dialog's close can return
 * focus to the row that asked.
 *
 * The popover portals to the body and docks under the trigger (fixed,
 * measured — the chapter card clips its overflow and the explorer body
 * scrolls, so an absolute child would be cut or drift): clamped into the
 * viewport, flipped above the trigger near the bottom edge, re-measured on
 * resize and scroll. Opening moves focus to the first row; Escape returns
 * to the trigger; an outside press closes without stealing focus. There is
 * no busy state here — the menu never runs a write itself.
 *
 * The trigger keeps the draft's calm: invisible at rest on an inactive
 * row, revealed on hover or keyboard focus (`group-focus-within`), always
 * visible while its menu stands. A control that cannot be seen until it is
 * wanted, but never hidden from the keyboard.
 */

import { useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import { useTranslation } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

/** The shell's focus ring on every control the menu offers. */
const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

/** The popover's width — the shelf menu's w-64 narrowed to the column. */
const PANEL_WIDTH = 192;

export function TreeMenu({
  label,
  editLabel,
  onEdit,
  onDelete,
}: {
  /** The eyebrow and the trigger's accessible name (chapter/scene options). */
  label: string;
  /** The first row's label — Umbenennen for a chapter, Bearbeiten for a scene. */
  editLabel: string;
  /** Hands off to the page's edit dialog; the argument is the trigger's id
   *  (the dialog's focus return). */
  onEdit: (openerId: string) => void;
  /** Hands off to the page's delete confirm, the same carry. */
  onDelete: (openerId: string) => void;
}) {
  const t = useTranslation();
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
  const triggerId = useId();
  const panelId = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const firstRowRef = useRef<HTMLButtonElement | null>(null);

  // Dock the panel under the trigger, clamped into the viewport and flipped
  // above near the bottom edge. Measured before paint; re-measured on
  // resize and on any scroll (the explorer body scrolls under the panel).
  useLayoutEffect(() => {
    if (!open) return;
    const compute = () => {
      const rect = triggerRef.current?.getBoundingClientRect();
      if (!rect) return;
      const margin = 8;
      const height = panelRef.current?.offsetHeight ?? 120;
      const left = Math.max(
        margin,
        Math.min(rect.right - PANEL_WIDTH, window.innerWidth - PANEL_WIDTH - margin),
      );
      const below = rect.bottom + 4;
      const top =
        below + height > window.innerHeight - margin
          ? Math.max(margin, rect.top - height - 4)
          : below;
      setPos({ top, left });
    };
    compute();
    window.addEventListener("resize", compute);
    window.addEventListener("scroll", compute, true);
    return () => {
      window.removeEventListener("resize", compute);
      window.removeEventListener("scroll", compute, true);
    };
  }, [open]);

  // Opening lands focus on the first row; Escape returns to the trigger,
  // an outside press closes without stealing focus (the shelf's discipline).
  useEffect(() => {
    if (!open) return;
    firstRowRef.current?.focus();
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    }
    function onDown(event: MouseEvent) {
      const target = event.target as Node;
      if (panelRef.current?.contains(target) || triggerRef.current?.contains(target)) return;
      setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [open]);

  function handoff(action: (openerId: string) => void) {
    setOpen(false);
    action(triggerId);
  }

  return (
    <>
      <button
        type="button"
        id={triggerId}
        ref={triggerRef}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        aria-label={label}
        onClick={() => setOpen((previous) => !previous)}
        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded text-muted transition-colors hover:text-foreground ${FOCUS} ${
          open ? "opacity-100" : "opacity-0 group-hover:opacity-100 group-focus-within:opacity-100"
        }`}
      >
        <Icon name="moreVert" size={14} />
      </button>
      {open &&
        createPortal(
          <div
            id={panelId}
            ref={panelRef}
            role="dialog"
            aria-label={label}
            style={{ position: "fixed", top: pos?.top ?? 0, left: pos?.left ?? 0, width: PANEL_WIDTH }}
            className="z-50 rounded-xl border border-outline-variant bg-surface-container-lowest p-1.5 shadow-lg"
          >
            <div className="mb-1 border-b border-rule px-2.5 py-1 text-eyebrow font-semibold uppercase tracking-wider text-muted">
              {label}
            </div>
            <button
              type="button"
              ref={firstRowRef}
              onClick={() => handoff(onEdit)}
              className={`flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-label text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              <span className="text-muted">
                <Icon name="write" size={16} />
              </span>
              {editLabel}
            </button>
            <button
              type="button"
              onClick={() => handoff(onDelete)}
              className={`flex w-full items-center gap-2.5 rounded px-2.5 py-1.5 text-left text-label text-danger transition-colors hover:bg-danger/10 ${FOCUS}`}
            >
              <span>
                <Icon name="trash" size={16} />
              </span>
              {t("writing.workspace.tree.delete")}
            </button>
          </div>,
          document.body,
        )}
    </>
  );
}