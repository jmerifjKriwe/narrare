/**
 * The activity banner's pure model: the sparkline's geometry and the two
 * readings the copy selects from. No React, no i18n, no requests — the
 * rules the banner renders, testable on their own (activity.test.ts).
 *
 * The sparkline is the `shelf` draft's 120×32 line, derived from the
 * aggregate's points alone: x spans the box oldest-first, y scales between
 * the window's own min and max inside a 4-unit pad (the stroke's round cap
 * never clips). A flat window — every day zero, or every day the same —
 * lies on the midline: nothing moved, nothing invented. Negative days ride
 * the same scale, unfloored (Task 4's honesty). The marked point is the
 * last one: today, the day the banner's today-line speaks.
 *
 * The daily goal's voice (goalState) reads the aggregate's goal fields —
 * the user's stored answer and the day's progress against it (W4 row 25).
 */

import type { Activity, ActivityPoint } from "@shell/lib/api/client";

/** The drafted line's path and the point that marks today. */
export type Sparkline = { d: string; today: { x: number; y: number } };

/** Two decimals: a coordinate string that never drifts between renders. */
function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

/** The draft's line over the window's points, or null when there are none.
 *  One point stands alone at the centre — a line needs two; the dot still
 *  marks it. The box defaults to the draft's 120×32. */
export function sparkline(
  points: readonly ActivityPoint[],
  width = 120,
  height = 32,
): Sparkline | null {
  if (points.length === 0) return null;
  const words = points.map((point) => point.words);
  const min = Math.min(...words);
  const max = Math.max(...words);
  const pad = 4;
  const x = (at: number) =>
    round2(points.length === 1 ? width / 2 : (at * width) / (points.length - 1));
  const y = (count: number) =>
    round2(max === min ? height / 2 : pad + (1 - (count - min) / (max - min)) * (height - pad * 2));
  const d = words.map((count, at) => `${at === 0 ? "M" : "L"} ${x(at)},${y(count)}`).join(" ");
  const last = words.length - 1;
  return { d, today: { x: x(last), y: y(words[last]) } };
}

/** The window that holds nothing: every day zero, no live streak, no today.
 *  The payload's honest „no rows ever" face (Task 4's no-retroactivity) —
 *  a lapsed atelier whose window is all zeros reads the same neutral, and
 *  the copy claims only what the window shows. */
export function activityIsEmpty(activity: Activity): boolean {
  return (
    activity.streak_days === 0 &&
    activity.today_words === 0 &&
    activity.points.every((point) => point.words === 0)
  );
}

/** The day's voice, selected from the net alone: a written day, a quiet
 *  day, or a day that removed more than it added. The copy's ICU select
 *  reads this — zero and negative are honest states, never hidden. */
export type TodayState = "written" | "quiet" | "removed";
export function todayState(todayWords: number): TodayState {
  if (todayWords > 0) return "written";
  if (todayWords < 0) return "removed";
  return "quiet";
}

/** The daily goal's voice (W4 row 25), selected from the aggregate's own
 *  fields: no goal stored is the unset neutral — presence decides, never
 *  the progress alone; a stored goal the day reached is met, else open.
 *  The remainder math is the server's (the aggregate derives it the way
 *  it derives the streak); the copy reads the answer, never recomputes. */
export type GoalState = "unset" | "open" | "met";
export function goalState(activity: Activity): GoalState {
  if (activity.daily_goal_words === null) return "unset";
  return activity.goal_met ? "met" : "open";
}
