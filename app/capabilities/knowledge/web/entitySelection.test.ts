// @vitest-environment jsdom
import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { isDeadEntityParam, useDeadEntityCleanup } from "./entitySelection";

const rows = [{ id: "e-mira" }, { id: "e-haus" }];

describe("isDeadEntityParam", () => {
  it("stays its hand while the answer has not landed or names nothing", () => {
    expect(isDeadEntityParam(undefined, "e-mira")).toBe(false);
    expect(isDeadEntityParam(rows, undefined)).toBe(false);
  });

  it("judges the param against the novel's own list", () => {
    expect(isDeadEntityParam(rows, "e-mira")).toBe(false);
    expect(isDeadEntityParam(rows, "dead-id")).toBe(true);
  });
});

describe("useDeadEntityCleanup", () => {
  it("clears a dead id and keeps a live one", () => {
    const select = vi.fn();
    const { rerender } = renderHook(
      ({ entityParam }) => useDeadEntityCleanup({ rows, entityParam, select }),
      { initialProps: { entityParam: "dead-id" as string | undefined } },
    );
    expect(select).toHaveBeenCalledWith(null);

    select.mockClear();
    rerender({ entityParam: "e-mira" });
    expect(select).not.toHaveBeenCalled();
  });
});
