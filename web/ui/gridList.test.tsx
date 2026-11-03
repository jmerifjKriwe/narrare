// @vitest-environment jsdom
/**
 * The selection list wears the row primitive: the item classes are
 * `rowClass` (P4), so a GridList row cannot drift from a plain Row — and
 * the selection is the L2 wash with the edge marker, never the filled
 * `--primary` block the legacy item classes painted here. Nothing
 * behavioural pins that string (a regression to the old paint would pass
 * every E2E gate), so the class contract is pinned here, the way
 * `buttonClass` and `rowClass` themselves are.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { GridList } from "./GridList";

describe("GridList", () => {
  afterEach(cleanup);

  const items = [
    { id: "a", name: "Anton" },
    { id: "b", name: "Berta" },
  ];

  function renderList(selectedId: string | null) {
    return render(
      <GridList
        label="Liste"
        items={items}
        getId={(item) => item.id}
        selectedId={selectedId}
        onSelect={() => {}}
        render={(item) => item.name}
      />,
    );
  }

  it("dresses its rows in rowClass: the wash and the edge marker on the selected row, a filled primary nowhere", () => {
    renderList("b");
    const rows = screen.getAllByRole("row");
    expect(rows).toHaveLength(2);
    for (const row of rows) {
      // The L2 ban holds on every row; the focus appendage rides both
      // triggers (the native pseudo-class and the RAC attribute variant).
      expect(row.className).not.toContain("bg-primary");
      expect(row.className).toContain("data-focus-visible:ring-2");
      expect(row.className).toContain("data-focus-visible:ring-focus");
    }
    const selected = rows.find((row) => row.textContent === "Berta");
    expect(selected).toBeTruthy();
    // The selection additions, as one token run: the wash, the weight,
    // the edge marker.
    expect(selected!.className).toContain(
      "bg-soft font-semibold shadow-[inset_2px_0_0_var(--primary)]",
    );
    const unselected = rows.find((row) => row.textContent === "Anton");
    expect(unselected).toBeTruthy();
    expect(unselected!.className).not.toContain("font-semibold");
  });

  it("carries the row matrix itself — the rule separator and the house ring", () => {
    renderList(null);
    const row = screen.getAllByRole("row")[0]!;
    expect(row.className).toContain("border-b");
    expect(row.className).toContain("focus-visible:ring-2");
    expect(row.className).toContain("focus-visible:ring-focus");
  });
});
