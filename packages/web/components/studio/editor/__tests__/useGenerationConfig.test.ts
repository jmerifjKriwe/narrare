/**
 * useGenerationConfig tests — form state + GenerateRequest assembly.
 *
 * Focus (PLAN-001 spec §8.1): `scenes` attach to scene_by_scene requests when
 * the chapter has scene plans and the toggle is on — default ON while plans
 * exist, explicit-off persists for the session (sessionStorage) across panel
 * remounts.
 */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { ScenePlan } from "@/types/planning";
import { useGenerationConfig } from "../useGenerationConfig";

function makeScene(overrides: Partial<ScenePlan> = {}): ScenePlan {
  return {
    id: "scene-1",
    position: 1,
    title: "The Gate",
    pov_character_ref: { id: null, name: "John" },
    location_ref: null,
    present_characters: [{ id: null, name: "Mara", goal: "Stop him" }],
    purpose: "Reach the gate",
    conflict: "Mara blocks the path",
    resolution: "",
    beats: ["Arrival", "Standoff"],
    status: "in_progress",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function setup(scenePlans?: ScenePlan[] | null) {
  return renderHook(() => useGenerationConfig({ scenePlans }));
}

beforeEach(() => {
  // The session-scoped preference starts untouched in every test.
  window.sessionStorage.clear();
});

describe("useGenerationConfig", () => {
  it("keeps the legacy request shape when the chapter has no scene plans", () => {
    const { result } = setup(null);
    act(() => {
      result.current.setMode("scene_by_scene");
      result.current.setOutline("Act structure");
    });

    const req = result.current.buildRequest();
    expect(req.mode).toBe("scene_by_scene");
    expect(req.outline).toBe("Act structure");
    expect(req.scenes).toBeUndefined();
  });

  it("defaults to attaching scenes when plans exist (spec §8.1 default ON)", () => {
    const { result } = setup([makeScene()]);
    act(() => result.current.setMode("scene_by_scene"));

    expect(result.current.useScenePlans).toBe(true);
    // Field-exact mirror of GenerateSceneSchema — identity-free names only.
    expect(result.current.buildRequest().scenes).toEqual([
      {
        title: "The Gate",
        pov_character_name: "John",
        location_name: "",
        present_characters: [{ name: "Mara", goal: "Stop him" }],
        purpose: "Reach the gate",
        conflict: "Mara blocks the path",
        resolution: "",
        beats: ["Arrival", "Standoff"],
        status: "in_progress",
      },
    ]);
  });

  it("never attaches scenes outside scene_by_scene mode", () => {
    const { result } = setup([makeScene()]);
    act(() => result.current.setMode("full_draft"));

    expect(result.current.buildRequest().scenes).toBeUndefined();
  });

  it("does not attach scenes for an empty plan list", () => {
    const { result } = setup([]);
    act(() => result.current.setMode("scene_by_scene"));

    expect(result.current.useScenePlans).toBe(false);
    expect(result.current.buildRequest().scenes).toBeUndefined();
  });

  it("persists an explicit toggle-off across hook remounts (session scope)", () => {
    const first = setup([makeScene()]);
    act(() => {
      first.result.current.setMode("scene_by_scene");
      first.result.current.setUseScenePlans(false);
    });
    expect(first.result.current.useScenePlans).toBe(false);
    expect(first.result.current.buildRequest().scenes).toBeUndefined();
    first.unmount();

    // Fresh mount (panel reopened): explicit-off survives; the default would be ON.
    const second = setup([makeScene()]);
    act(() => second.result.current.setMode("scene_by_scene"));
    expect(second.result.current.useScenePlans).toBe(false);
    expect(second.result.current.buildRequest().scenes).toBeUndefined();
  });

  it("honors an explicit toggle-on once plans arrive", () => {
    const { result, rerender } = renderHook(
      ({ plans }) => useGenerationConfig({ scenePlans: plans }),
      { initialProps: { plans: null as ScenePlan[] | null } },
    );

    act(() => result.current.setUseScenePlans(true));
    rerender({ plans: [makeScene()] });
    act(() => result.current.setMode("scene_by_scene"));

    expect(result.current.buildRequest().scenes).toHaveLength(1);
  });

  it("persists an explicit toggle-off when plans arrive afterwards", () => {
    const { result, rerender } = renderHook(
      ({ plans }) => useGenerationConfig({ scenePlans: plans }),
      { initialProps: { plans: null as ScenePlan[] | null } },
    );

    act(() => result.current.setUseScenePlans(false));
    rerender({ plans: [makeScene()] });
    act(() => result.current.setMode("scene_by_scene"));

    expect(result.current.useScenePlans).toBe(false);
    expect(result.current.buildRequest().scenes).toBeUndefined();
  });
});
