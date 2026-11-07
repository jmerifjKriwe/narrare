import { describe, expect, it } from "vitest";

import { exportAge } from "./exportAge";

/** A pinned "now": the comparison is pure, so the clock is the test's to set. */
const NOW = new Date("2026-11-07T12:00:00Z");

describe("exportAge", () => {
  it("never_exported_is_never", () => {
    // No export stamp, whatever the book has done since: the one answer is
    // that there is nothing to compare against.
    expect(exportAge(null, "2026-11-01T12:00:00Z", NOW)).toEqual({ kind: "never" });
  });

  it("an_export_after_the_last_change_is_fresh", () => {
    // The archive holds everything the canon changed — the export followed
    // the last write.
    expect(exportAge("2026-11-06T12:00:00Z", "2026-11-01T12:00:00Z", NOW)).toEqual({
      kind: "fresh",
    });
    // The boundary instant is fresh too: an export that followed the change
    // by nothing still followed it. And the instants, not the strings, are
    // compared — the same moment in two offsets is not a change.
    expect(exportAge("2026-11-01T12:00:00Z", "2026-11-01T12:00:00Z", NOW)).toEqual({
      kind: "fresh",
    });
    expect(exportAge("2026-11-01T13:00:00+01:00", "2026-11-01T12:00:00Z", NOW)).toEqual({
      kind: "fresh",
    });
  });

  it("an_export_before_the_last_change_is_stale_with_its_day_count", () => {
    // The archive predates the last write, and the count is the backup's
    // own age: whole days from the export to now, floored.
    expect(exportAge("2026-11-04T12:00:00Z", "2026-11-06T12:00:00Z", NOW)).toEqual({
      kind: "stale",
      days: 3,
    });
  });

  it("a_change_without_an_export_is_stale", () => {
    // A change no export covers reads as stale however young it is — and
    // the count stays the backup's age, not the change's: an hour-old edit
    // over a ten-day-old export warns about the ten days.
    expect(exportAge("2026-10-28T12:00:00Z", "2026-11-07T11:00:00Z", NOW)).toEqual({
      kind: "stale",
      days: 10,
    });
  });
});
