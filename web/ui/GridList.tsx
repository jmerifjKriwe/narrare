import { GridList as RacGridList, GridListItem, type Selection } from "react-aria-components";
import type { ReactNode } from "react";

import { rowClass } from "./Row";

/**
 * The shell's selection list: React-Aria's grid list with the row
 * primitive's classes painted on. The caller owns the items and both
 * directions of selection — `render` draws a row, `onSelect` hears the
 * choice; React-Aria owns the keyboard contract (arrows walk the rows,
 * click and Space select) and the roles (a named grid of selectable rows).
 *
 * The item classes are `rowClass(item.id === selectedId)` (P4): a row of
 * this list wears exactly what a plain `Row` wears, so the list cannot
 * drift from its siblings — and selection is the L2 wash with the edge
 * marker, not the filled `--primary` block the legacy classes painted
 * here. Focus is the house ring exactly once: `rowClass` carries it under
 * the native `:focus-visible` pseudo-class, and the `data-focus-visible:`
 * variant names the same two ring utilities under React-Aria's attribute
 * (the row's own signal, set on this root) — whichever trigger fires, the
 * paint is the identical box-shadow, so the row shows one ring, keyboard
 * only, never two. The rows stack flush: each carries the `--rule`
 * separator, so a gap here would float a rule inside empty space. A
 * row's text truncates, never wraps (§6, the 360 px rule) — unless the
 * caller passes `wrap`: a name the column cannot grow for (a 120-char
 * entity in the 352 px dock) needs the row to grow instead. The wrap is
 * the chapter rail's precedent (NovelPage): the item leaves the
 * single-line control height behind (`h-auto min-h-7`, appended after the
 * matrix — the P3 precedence) and the span trades `truncate` for
 * `break-words`. React-Aria's gridcell wrapper is `display: contents`, so
 * the span below is the flex
 * child that shrinks — and, wrapped, grows the row instead of ellipsizing.
 */
export function GridList<T>({
  label,
  flush = false,
  items,
  getId,
  render,
  textOf,
  selectedId,
  onSelect,
  wrap = false,
}: {
  label: string;
  /** The surface around the list owns the gutter; rows add none. */
  flush?: boolean;
  items: T[];
  getId: (item: T) => string;
  render: (item: T) => ReactNode;
  /** The row's plain text for type-to-select: the truncate span below is
   *  an element child, so React-Aria cannot infer it from the children. */
  textOf?: (item: T) => string;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Wrapped rows for names the column cannot grow for; the default stays
   *  the truncating single-line row (§6). */
  wrap?: boolean;
}) {
  return (
    <RacGridList
      aria-label={label}
      selectionMode="single"
      selectedKeys={selectedId === null ? [] : [selectedId]}
      onSelectionChange={(keys: Selection) => {
        // "all" cannot occur with a single selection mode that offers one
        // row per item; the guard keeps the narrowing honest anyway.
        if (keys === "all") return;
        const [first] = keys;
        onSelect(first === undefined ? null : String(first));
      }}
      className="flex flex-col"
    >
      {items.map((item) => (
        <GridListItem
          key={getId(item)}
          id={getId(item)}
          textValue={textOf?.(item)}
          className={`${rowClass(getId(item) === selectedId, flush)}${wrap ? " h-auto min-h-7" : ""} data-focus-visible:ring-2 data-focus-visible:ring-focus`}
        >
          <span className={wrap ? "min-w-0 flex-1 break-words" : "min-w-0 flex-1 truncate"}>
            {render(item)}
          </span>
        </GridListItem>
      ))}
    </RacGridList>
  );
}
