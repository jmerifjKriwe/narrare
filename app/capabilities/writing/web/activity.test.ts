/**
 * The activity banner's pure model (activity.ts): the sparkline's geometry
 * derives deterministically from the aggregate's points — thirty of them,
 * zero-days flat on the midline, negative days honest on the scale — and
 * the readings the copy selects from (the empty window, the day's voice,
 * the daily goal's voice) answer the payload, never a guess. No React, no
 * i18n, no requests.
 */
import { describe, expect, it } from "vitest";

import type { Activity, ActivityPoint } from "@shell/lib/api/client";

import { activityIsEmpty, goalState, sparkline, todayState } from "./activity";

/** Points in the API's own shape — oldest first, one per day of the window. */
function points(words: readonly number[]): ActivityPoint[] {
  return words.map((count, at) => ({
    date: `2026-10-${String(at + 1).padStart(2, "0")}`,
    words: count,
  }));
}

/** The aggregate as the API answers it, overridable per case. */
function aggregate(overrides: Partial<Activity> = {}): Activity {
  return {
    points: points([0, 120, 412]),
    streak_days: 2,
    weekly_average: 17.7,
    today_words: 412,
    daily_goal_words: 750,
    goal_met: false,
    goal_remaining: 338,
    ...overrides,
  };
}

describe("sparkline — the drafted 120×32 line, derived from the points alone", () => {
  it("thirty points span the box oldest-first, the last point marked as today", () => {
    const ramp = points(Array.from({ length: 30 }, (_, at) => at * 10));
    const shape = sparkline(ramp);
    expect(shape).not.toBeNull();
    // The ramp's own extremes: zero at the bottom pad, 290 at the top pad.
    expect(shape?.d.startsWith("M 0,28 ")).toBe(true);
    expect(shape?.d.endsWith(" L 120,4")).toBe(true);
    // One move and twenty-nine lines — every point of the window stands.
    expect(shape?.d.split(" L ")).toHaveLength(30);
    expect(shape?.today).toEqual({ x: 120, y: 4 });
  });

  it("the path is deterministic — the same points draw the same string", () => {
    const words = [0, 0, 120, -40, 0, 340, 0, 0, 180, 260, 412, 0, 0, 0, 90, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
    const first = sparkline(points(words));
    const second = sparkline(points([...words]));
    expect(first).toEqual(second);
    // A rebuild of the same window never shifts a coordinate.
    expect(first?.d).toBe(second?.d);
  });

  it("zero-days lie flat on the midline — an honest empty window, not an invented curve", () => {
    const shape = sparkline(points(Array.from({ length: 30 }, () => 0)));
    expect(shape).not.toBeNull();
    const ys = (shape?.d ?? "").split(" ").filter((token) => token.includes(","));
    expect(ys).toHaveLength(30);
    for (const pair of ys) expect(pair.split(",")[1]).toBe("16");
    expect(shape?.d.startsWith("M 0,16 ")).toBe(true);
    expect(shape?.d.endsWith(" L 120,16")).toBe(true);
    expect(shape?.today).toEqual({ x: 120, y: 16 });
  });

  it("a mixed window scales between its own min and max — negative days honest", () => {
    // -20 .. 60: the negative day owns the bottom, the peak the top, and
    // zero sits proportionally between — no floor, no invented baseline.
    const shape = sparkline(points([-20, 0, 60]));
    expect(shape?.d).toBe("M 0,28 L 60,22 L 120,4");
    expect(shape?.today).toEqual({ x: 120, y: 4 });
  });

  it("a flat nonzero window is a midline too — nothing moved, nothing invented", () => {
    const shape = sparkline(points([5, 5, 5]));
    expect(shape?.d).toBe("M 0,16 L 60,16 L 120,16");
  });

  it("one point stands alone at the centre — a line needs two", () => {
    const shape = sparkline(points([7]));
    expect(shape?.d).toBe("M 60,16");
    expect(shape?.today).toEqual({ x: 60, y: 16 });
  });

  it("no points draw nothing — null, never an empty path", () => {
    expect(sparkline([])).toBeNull();
  });

  it("the box is the caller's — the draft's defaults stand when none is given", () => {
    expect(sparkline(points([0, 10]), 60, 16)?.d).toBe("M 0,12 L 60,4");
    const shape = sparkline(points([0, 10]));
    expect(shape?.d).toBe("M 0,28 L 120,4");
  });
});

describe("activityIsEmpty — the window that holds nothing", () => {
  it("an all-zero window with no streak and no today is the empty answer", () => {
    expect(
      activityIsEmpty(
        aggregate({
          points: points(Array.from({ length: 30 }, () => 0)),
          streak_days: 0,
          today_words: 0,
          weekly_average: 0,
        }),
      ),
    ).toBe(true);
  });

  it("one written day anywhere in the window is not empty", () => {
    const words = Array.from({ length: 30 }, () => 0);
    words[7] = 1;
    expect(activityIsEmpty(aggregate({ points: points(words), streak_days: 0, today_words: 0 }))).toBe(false);
  });

  it("a live streak keeps the window alive even when today is quiet", () => {
    expect(
      activityIsEmpty(
        aggregate({ points: points(Array.from({ length: 30 }, () => 0)), streak_days: 1, today_words: 0 }),
      ),
    ).toBe(false);
  });

  it("a nonzero today is activity, whatever the window behind it", () => {
    expect(activityIsEmpty(aggregate({ points: points([0, 0, 0]), streak_days: 0, today_words: 5 }))).toBe(false);
  });
});

describe("todayState — the day's voice, selected from the net alone", () => {
  it("a positive net is a written day", () => {
    expect(todayState(412)).toBe("written");
  });
  it("zero is a quiet day — honest, not hidden", () => {
    expect(todayState(0)).toBe("quiet");
  });
  it("a negative net is a day that removed more than it added", () => {
    expect(todayState(-5)).toBe("removed");
  });
});

describe("goalState — the daily goal's voice, selected from the aggregate", () => {
  it("no goal stored is the unset neutral — whatever the progress fields say", () => {
    expect(goalState(aggregate({ daily_goal_words: null, goal_met: false, goal_remaining: 0 }))).toBe("unset");
    // Presence decides: an unset goal owes nothing, even beside a stale
    // remainder — the neutral wins over any progress field.
    expect(goalState(aggregate({ daily_goal_words: null, goal_remaining: 338 }))).toBe("unset");
  });
  it("a stored goal the day has not reached is open", () => {
    expect(goalState(aggregate({ daily_goal_words: 750, goal_met: false, goal_remaining: 338 }))).toBe("open");
  });
  it("a stored goal the day reached is met — the aggregate's own mark", () => {
    expect(goalState(aggregate({ daily_goal_words: 400, goal_met: true, goal_remaining: 0 }))).toBe("met");
  });
});
