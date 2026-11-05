// @vitest-environment jsdom
/**
 * The table's class contracts, pinned whole: `tableBodyClass` carries the
 * L3 law — a `--rule` between rows, never a `--border` edge — and the
 * cell helpers carry the density law's 26 px row (§8.3) in the type
 * scale's own voices. `tabular-nums` rides exactly the right-aligned
 * columns, so numerals line up in a figures column and nowhere else; a
 * stray alignment or a sneaking `--border` fails here, not in a
 * screenshot. Behaviour (the axe pass) is the E2E suites' job; the
 * caption wiring is rendered below against jsdom, because "first child"
 * is a DOM fact, not a string fact.
 */
import { createElement } from "react";
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  tableBodyCellClass,
  tableBodyClass,
  tableClass,
  tableHeadCellClass,
  Table,
} from "./Table";
import type { TableProps } from "./Table";

describe("tableClass", () => {
  it("is the full-measure collapsed table, and nothing else", () => {
    expect(tableClass()).toBe("w-full border-collapse");
  });

  it("separates rows with the rule, never the border edge (L3)", () => {
    expect(tableBodyClass()).toBe("divide-y divide-rule");
    expect(tableBodyClass()).not.toContain("border");
  });
});

describe("tableHeadCellClass", () => {
  it("carries exactly the pinned string per alignment and density", () => {
    expect(tableHeadCellClass("left", false)).toBe(
      "h-[26px] px-3 text-left text-meta uppercase tracking-[0.1em] text-muted",
    );
    expect(tableHeadCellClass("right", false)).toBe(
      "h-[26px] px-3 text-right tabular-nums text-meta uppercase tracking-[0.1em] text-muted",
    );
    expect(tableHeadCellClass("left", true)).toBe(
      "h-[26px] px-2.5 text-left text-meta uppercase tracking-[0.1em] text-muted",
    );
    expect(tableHeadCellClass("right", true)).toBe(
      "h-[26px] px-2.5 text-right tabular-nums text-meta uppercase tracking-[0.1em] text-muted",
    );
  });

  it("defaults to the regular left-aligned cell — the pinned string itself", () => {
    expect(tableHeadCellClass()).toBe(tableHeadCellClass("left", false));
  });
});

describe("tableBodyCellClass", () => {
  it("carries exactly the pinned string per alignment and density", () => {
    expect(tableBodyCellClass("left", false)).toBe(
      "h-[26px] px-3 text-body text-left",
    );
    expect(tableBodyCellClass("right", false)).toBe(
      "h-[26px] px-3 text-body text-right tabular-nums",
    );
    expect(tableBodyCellClass("left", true)).toBe(
      "h-[26px] px-2.5 text-body text-left",
    );
    expect(tableBodyCellClass("right", true)).toBe(
      "h-[26px] px-2.5 text-body text-right tabular-nums",
    );
  });

  it("defaults to the regular left-aligned cell — the pinned string itself", () => {
    expect(tableBodyCellClass()).toBe(tableBodyCellClass("left", false));
  });

  it("keeps tabular numerals and the right edge a pair, only for figures columns", () => {
    for (const dense of [false, true]) {
      expect(tableBodyCellClass("right", dense)).toContain("tabular-nums");
      expect(tableBodyCellClass("right", dense)).toContain("text-right");
      expect(tableBodyCellClass("left", dense)).not.toContain("tabular-nums");
      expect(tableBodyCellClass("left", dense)).not.toContain("text-right");
    }
  });

  it("never wears the legacy vocabulary or a filled primary", () => {
    for (const align of ["left", "right"] as const) {
      for (const dense of [false, true]) {
        const classes = tableBodyCellClass(align, dense);
        expect(classes).not.toContain("text-sm");
        expect(classes).not.toContain("rounded-md");
        expect(classes).not.toContain("bg-primary");
      }
    }
  });
});

type Row = { id: string; title: string };

/** A one-column table, rendered: the caption wiring is a DOM fact. */
function renderTable(props: Partial<TableProps<Row>> = {}) {
  return render(
    createElement(Table<Row>, {
      columns: [{ key: "title", label: "Titel" }],
      rows: [{ id: "1", title: "Eins" }],
      rowKey: (row: Row) => row.id,
      ...props,
    }),
  );
}

describe("Table's caption", () => {
  afterEach(cleanup);

  it("renders a real caption as the table's first child", () => {
    const { container } = renderTable({ caption: "Kapitelverzeichnis" });
    const table = container.firstElementChild;
    expect(table?.tagName).toBe("TABLE");
    const caption = table?.firstElementChild;
    expect(caption?.tagName).toBe("CAPTION");
    expect(caption?.textContent).toBe("Kapitelverzeichnis");
  });

  it("renders no caption element when none is given", () => {
    const { container } = renderTable();
    expect(container.querySelector("caption")).toBeNull();
    // The first child goes straight to the header row's group.
    expect(container.firstElementChild?.firstElementChild?.tagName).toBe(
      "THEAD",
    );
  });
});
