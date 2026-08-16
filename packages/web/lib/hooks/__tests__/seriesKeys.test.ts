/**
 * seriesKeys tests — key-shape contract for the C1 context-window preview.
 *
 * The key MUST nest under the series detail prefix so TanStack invalidations
 * aimed at ["series", seriesId] (or the ["series"] wildcard) also reach the
 * preview cache — the settings-PATCH invalidation relies on this neighborhood
 * (C1 Task 5 brief: verbatim contract for Tasks 6/7).
 */
import { describe, expect, it } from "vitest";
import { seriesKeys } from "../seriesKeys";

describe("seriesKeys.settingsPreview (C1)", () => {
  it("returns the exact readonly tuple", () => {
    expect(seriesKeys.settingsPreview("series-1")).toEqual([
      "series",
      "series-1",
      "settingsPreview",
    ]);
  });

  it("nests under the detail prefix (invalidation reach)", () => {
    const key = seriesKeys.settingsPreview("series-1");

    expect(key.slice(0, seriesKeys.detail("series-1").length)).toEqual(
      seriesKeys.detail("series-1"),
    );
    expect(key.slice(0, seriesKeys.all.length)).toEqual(seriesKeys.all);
  });
});
