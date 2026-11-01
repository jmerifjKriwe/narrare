import type { ReactNode, TableHTMLAttributes } from "react";

/**
 * The data table and its cell contracts. A real `<table>` — headers
 * associate through `scope="col"`, not ARIA repair — separated by a
 * `--rule` between rows and never edged with `--border` (L3): the
 * `divide-y` on the body is the whole separator story, and it draws
 * nothing under the last row, because a table ends, it does not close.
 * The density law's 26 px row (§8.3) is the cell height; `text-body` is
 * the cell's voice, `text-meta` the header's (the scale's own
 * table-header step, in the panel eyebrow's uppercase). Numerals line up
 * only where they are figures: `tabular-nums` rides exactly the
 * right-aligned columns, header and cells together.
 *
 * Cells read their value straight off the row — `key` is a field of `T`
 * — so a display transformation belongs in the row the consumer builds,
 * not in a render prop here. The `dense` knob is the panel's 10/12 law
 * applied to cells (10 px `px-2.5`, regular 12 px `px-3`); it never
 * touches the 26 px height.
 */

/** A column reads left, or is a figures column: right-aligned, tabular. */
export type TableAlign = "left" | "right";

export type TableColumn<T> = {
  /** The row field the column shows — also its cells' React key. */
  key: Extract<keyof T, string>;
  label: ReactNode;
  align?: TableAlign;
  /** A CSS width for the column, set on its header and every cell. */
  width?: string;
};

export type TableProps<T> = Omit<
  TableHTMLAttributes<HTMLTableElement>,
  "children"
> & {
  columns: TableColumn<T>[];
  rows: T[];
  /** The row's identity — the `<tr>` key, stable across re-sorts. */
  rowKey: (row: T) => string;
  /** Tighter cell padding, for tables in tight places: the panel's 10 px measure. */
  dense?: boolean;
  /**
   * Appended after the table's own classes: the table classes are the
   * contract, this the extension (the P3 precedence).
   */
  className?: string;
};

/** The table root: full measure, collapsed edges; the voices come with the cells. */
export function tableClass(): string {
  return "w-full border-collapse";
}

/** The body's separator: a rule between rows, never an edge (L3). */
export function tableBodyClass(): string {
  return "divide-y divide-rule";
}

const ALIGN_CLASSES: Record<TableAlign, string> = {
  left: "text-left",
  right: "text-right tabular-nums",
};

/** The header cell: the 26 px row, the meta eyebrow over its column. */
export function tableHeadCellClass(
  align: TableAlign = "left",
  dense = false,
): string {
  return `h-[26px] ${dense ? "px-2.5" : "px-3"} ${ALIGN_CLASSES[align]} text-meta uppercase tracking-[0.1em] text-muted`;
}

/** The body cell: the 26 px row, body type, figures aligned where they are figures. */
export function tableBodyCellClass(
  align: TableAlign = "left",
  dense = false,
): string {
  return `h-[26px] ${dense ? "px-2.5" : "px-3"} text-body ${ALIGN_CLASSES[align]}`;
}

export function Table<T>({
  columns,
  rows,
  rowKey,
  dense = false,
  className,
  ...rest
}: TableProps<T>) {
  // Appended after the matrix: `tableClass` is the contract, this the
  // extension (the P3 precedence).
  const classes = className ? `${tableClass()} ${className}` : tableClass();
  return (
    <table {...rest} className={classes}>
      <thead>
        <tr>
          {columns.map((column) => (
            <th
              key={column.key}
              scope="col"
              style={column.width ? { width: column.width } : undefined}
              className={tableHeadCellClass(column.align, dense)}
            >
              {column.label}
            </th>
          ))}
        </tr>
      </thead>
      <tbody className={tableBodyClass()}>
        {rows.map((row) => (
          <tr key={rowKey(row)}>
            {columns.map((column) => (
              <td
                key={column.key}
                style={column.width ? { width: column.width } : undefined}
                className={tableBodyCellClass(column.align, dense)}
              >
                {/* The field is display-ready by contract — a string, a
                    number, a node; anything structured is the consumer's
                    bug, and the runtime will name it. */}
                {row[column.key] as unknown as ReactNode}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
