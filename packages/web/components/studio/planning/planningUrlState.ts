export type PlanningTab = "storyboard" | "timeline" | "characterArc";

export interface PlanningUrlState {
  open: boolean;
  tab: PlanningTab;
}

const PLANNING_TABS = new Set<PlanningTab>(["storyboard", "timeline", "characterArc"]);

export function parsePlanningUrlState(searchParams: URLSearchParams): PlanningUrlState {
  const tabParam = searchParams.get("planningTab");
  return {
    open: searchParams.get("planning") === "1",
    tab: PLANNING_TABS.has(tabParam as PlanningTab) ? (tabParam as PlanningTab) : "storyboard",
  };
}

export function serializePlanningUrlState(state: PlanningUrlState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.open) params.set("planning", "1");
  if (state.open && state.tab !== "storyboard") params.set("planningTab", state.tab);
  return params;
}
