"use client";

/**
 * SlashCommandMenu (CR-AUFG-07-20).
 *
 * Presentational, fully-controlled dropdown listing the resolved slash commands.
 * It owns no state; the host hook ({@link useSlashCommandState}) drives
 * `activeIndex`, filtering and dispatch. The menu attaches a window-level
 * keydown listener only while mounted (i.e. while open) and `preventDefault`s
 * navigation/selection keys so they do not leak into the TipTap editor
 * (spec §43 — do not interfere with editor shortcuts / text entry).
 */
import { useEffect } from "react";
import type { SlashCommandAvailability } from "./contracts";

/** A command resolved for display (availability already computed). */
export interface SlashCommandMenuItem {
  readonly id: string;
  readonly labelKey: string;
  readonly descriptionKey: string;
  readonly availability: SlashCommandAvailability;
}

interface SlashCommandMenuProps {
  /** Filtered command list (already limited to the current query). */
  readonly items: readonly SlashCommandMenuItem[];
  /** Controlled active (highlighted) index into {@link SlashCommandMenuProps.items}. */
  readonly activeIndex: number;
  /** Current filter query (used for the empty-state copy). */
  readonly query: string;
  /** Pixel position for the dropdown (caret-relative). */
  readonly position: { top: number; left: number };
  readonly onActiveIndexChange: (index: number) => void;
  /** Select (run) the command at the given index. */
  readonly onSelect: (index: number) => void;
  /** Dismiss the menu without running a command (Escape). */
  readonly onDismiss: () => void;
  /** next-intl translator scoped to the `studio` namespace. */
  readonly t: (key: string, params?: Record<string, unknown>) => string;
}

const DISABLED_REASON_KEY: Record<Exclude<SlashCommandAvailability, "available">, string> = {
  "no-selection": "slashCommands.disabledReasons.noSelection",
  unavailable: "slashCommands.disabledReasons.unavailable",
};

const NAV_KEYS = new Set(["ArrowDown", "ArrowUp", "Enter", "Escape", "Tab"]);

/** Indices of runnable (available) items, in order. */
function availableIndices(items: readonly SlashCommandMenuItem[]): number[] {
  return items.reduce<number[]>((acc, item, idx) => {
    if (item.availability === "available") acc.push(idx);
    return acc;
  }, []);
}

/** Next available index when navigating by `delta` (+1 / −1), wrapping. */
function nextAvailable(
  items: readonly SlashCommandMenuItem[],
  from: number,
  delta: 1 | -1,
): number {
  const indices = availableIndices(items);
  if (indices.length === 0) return from;
  const pos = indices.indexOf(from);
  // If the current index isn't available, anchor to the closest end.
  const anchored = pos === -1 ? (delta > 0 ? -1 : indices.length) : pos;
  const nextPos = (anchored + delta + indices.length) % indices.length;
  return indices[nextPos] ?? from;
}

export function SlashCommandMenu({
  items,
  activeIndex,
  query,
  position,
  onActiveIndexChange,
  onSelect,
  onDismiss,
  t,
}: SlashCommandMenuProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (!NAV_KEYS.has(event.key)) return;
      // Eat navigation/selection keys so the editor caret & text entry stay put.
      event.preventDefault();
      event.stopPropagation();

      if (event.key === "Escape") {
        onDismiss();
        return;
      }
      if (event.key === "ArrowDown") {
        onActiveIndexChange(nextAvailable(items, activeIndex, 1));
        return;
      }
      if (event.key === "ArrowUp") {
        onActiveIndexChange(nextAvailable(items, activeIndex, -1));
        return;
      }
      if (event.key === "Enter" || event.key === "Tab") {
        const active = items[activeIndex];
        if (active && active.availability === "available") onSelect(activeIndex);
      }
    }
    window.addEventListener("keydown", handleKeyDown, true);
    return () => window.removeEventListener("keydown", handleKeyDown, true);
  }, [items, activeIndex, onActiveIndexChange, onSelect, onDismiss]);

  return (
    <div
      role="listbox"
      aria-label={t("slashCommands.menuLabel")}
      className="slash-command-menu fixed z-50 w-72 max-h-72 overflow-y-auto rounded-lg border border-border bg-popover shadow-lg"
      style={{ top: position.top, left: position.left }}
    >
      {items.length === 0 ? (
        <p className="px-3 py-2 text-sm text-muted-foreground">
          {t("slashCommands.empty")}
          {query ? <span className="block text-xs opacity-70">“{query}”</span> : null}
        </p>
      ) : (
        <ul className="py-1">
          {items.map((cmd, index) => {
            const disabled = cmd.availability !== "available";
            return (
              <li key={cmd.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={index === activeIndex}
                  aria-disabled={disabled}
                  disabled={disabled}
                  onClick={() => {
                    if (!disabled) onSelect(index);
                  }}
                  className={`flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left transition-colors ${
                    index === activeIndex ? "bg-accent" : ""
                  } ${disabled ? "cursor-not-allowed opacity-50" : "hover:bg-accent"}`}
                >
                  <span className="text-sm font-medium text-foreground">{t(cmd.labelKey)}</span>
                  <span className="text-xs text-muted-foreground">{t(cmd.descriptionKey)}</span>
                  {disabled && (
                    <span className="text-xs text-muted-foreground/80">
                      {t(DISABLED_REASON_KEY[cmd.availability])}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
