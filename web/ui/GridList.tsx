import { GridList as RacGridList, GridListItem, type Selection } from "react-aria-components";
import type { ReactNode } from "react";

/**
 * The shell's selection list: React-Aria's grid list with the tokens
 * painted on. The caller owns the items and both directions of selection —
 * `render` draws a row, `onSelect` hears the choice; React-Aria owns the
 * keyboard contract (arrows walk the rows, click and Space select) and the
 * roles (a named grid of selectable rows).
 */
export function GridList<T>({
  label,
  items,
  getId,
  render,
  selectedId,
  onSelect,
}: {
  label: string;
  items: T[];
  getId: (item: T) => string;
  render: (item: T) => ReactNode;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
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
      className="flex flex-col gap-2"
    >
      {items.map((item) => (
        <GridListItem
          key={getId(item)}
          id={getId(item)}
          className="cursor-default rounded-md border border-border bg-card px-4 py-2 text-sm outline-none data-selected:border-primary data-selected:bg-primary data-selected:text-primary-foreground data-focus-visible:outline-2 data-focus-visible:outline-focus"
        >
          {render(item)}
        </GridListItem>
      ))}
    </RacGridList>
  );
}
