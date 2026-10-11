/**
 * Scene-plan aggregate helpers — pure persistence-shape utilities.
 *
 * Extracted from ScenePlanEditor (PLAN-001 follow-up #1) so the component
 * stays within its RULE-04 budget while gaining the AI-draft context hook.
 * No React, no I/O — only aggregate-shape concerns.
 */

import type { ScenePlan, SceneProposal } from "@/types/planning";

/** Renumber positions 1..N in list order (server diff-syncs by id). */
export function withPositions(scenes: ScenePlan[]): ScenePlan[] {
  return scenes.map((scene, index) =>
    scene.position === index + 1 ? scene : { ...scene, position: index + 1 },
  );
}

export const nowIso = () => new Date().toISOString();

/** Turn an AI proposal into a persisted-shape scene appended to the chapter. */
export function proposalToScene(proposal: SceneProposal, position: number): ScenePlan {
  return {
    ...proposal,
    id: crypto.randomUUID(),
    position,
    status: "planned",
    created_at: nowIso(),
    updated_at: nowIso(),
  };
}
