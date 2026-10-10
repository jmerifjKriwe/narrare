/**
 * SceneForm tests — scene plan field editing + AI refine apply.
 *
 * (Beat/character list-editor behaviour is covered in SceneListEditors.test.tsx.)
 *
 * Tests:
 * 1. Renders all fields with the scene's values
 * 2. Text field edits emit onChange with the patched scene
 * 3. Status select emits onChange
 * 4. POV + location refs: name edits, empty name clears the ref
 * 5. List editors are wired to the scene's beats / present_characters
 * 6. Refine with AI: proposal applied to the draft (id/position/status kept)
 * 7. Refine with AI unavailable: no onChange, aiUnavailable message
 * 8. Edits typed mid-flight survive the refine apply (status; regression T12)
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { delay, HttpResponse, http } from "msw";
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SceneForm } from "@/components/studio/planning/SceneForm";
import { server } from "@/mocks/server";
import type { ScenePlan } from "@/types/planning";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const scene: ScenePlan = {
  id: "scene-1",
  position: 2,
  title: "The Meeting",
  pov_character_ref: { id: "char-1", name: "Alice" },
  location_ref: null,
  present_characters: [{ id: null, name: "Bob", goal: "Find the map" }],
  purpose: "Introduce the rivalry",
  conflict: "Alice vs. Bob",
  resolution: "Uneasy truce",
  beats: ["Arrival", "Argument"],
  status: "planned",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Test wrapper (real planning hooks — only the API boundary is mocked via MSW)
// ---------------------------------------------------------------------------

function renderForm(current: ScenePlan = scene) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  const onChange = vi.fn();
  // Controlled-parent host: feeds each emitted scene back into the prop, so the
  // component sees the same latest-state lifecycle as under SceneCard/ScenePlanEditor.
  function Host() {
    const [value, setValue] = useState<ScenePlan>(current);
    return (
      <SceneForm
        scene={value}
        novelId="novel-1"
        chapterId="chapter-1"
        onChange={(next) => {
          onChange(next);
          setValue(next);
        }}
      />
    );
  }
  render(
    <QueryClientProvider client={queryClient}>
      <Host />
    </QueryClientProvider>,
  );
  return { onChange };
}

describe("SceneForm", () => {
  beforeEach(() => {
    server.use(
      http.post("*/api/v1/planning/scenes/:novelId/:chapterId/refine", async () => {
        return HttpResponse.json({
          proposal: {
            title: "Rewritten Scene",
            pov_character_ref: { id: null, name: "Claire" },
            location_ref: { id: null, name: "Harbor" },
            present_characters: [{ id: null, name: "Dave", goal: "" }],
            purpose: "New purpose",
            conflict: "New conflict",
            resolution: "New resolution",
            beats: ["Beat A", "Beat B", "Beat C"],
          },
          ai_unavailable: false,
        });
      }),
    );
  });

  it("renders all fields with the scene's values", () => {
    renderForm();

    expect(screen.getByLabelText("sceneTitle")).toHaveValue("The Meeting");
    expect(screen.getByLabelText("purpose")).toHaveValue("Introduce the rivalry");
    expect(screen.getByLabelText("conflict")).toHaveValue("Alice vs. Bob");
    expect(screen.getByLabelText("resolution")).toHaveValue("Uneasy truce");
    expect(screen.getByLabelText("pov")).toHaveValue("Alice");
    expect(screen.getByLabelText("status")).toHaveValue("planned");
  });

  it("emits onChange when the title is edited", () => {
    const { onChange } = renderForm();

    fireEvent.change(screen.getByLabelText("sceneTitle"), { target: { value: "Changed" } });

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ title: "Changed" }));
  });

  it("emits onChange when the status select changes", () => {
    const { onChange } = renderForm();

    fireEvent.change(screen.getByLabelText("status"), { target: { value: "complete" } });

    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ status: "complete" }));
  });

  it("edits the location ref and clears refs when the name is emptied", () => {
    const { onChange } = renderForm();

    fireEvent.change(screen.getByLabelText("location"), { target: { value: "Harbor" } });
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ location_ref: { id: null, name: "Harbor" } }),
    );

    fireEvent.change(screen.getByLabelText("pov"), { target: { value: "" } });
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ pov_character_ref: null }));
  });

  it("wires the list editors to the scene's beats and present_characters", () => {
    const { onChange } = renderForm();

    fireEvent.click(screen.getByText("addBeat"));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ beats: ["Arrival", "Argument", ""] }),
    );

    fireEvent.click(screen.getByText("addCharacter"));
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({
        present_characters: [
          { id: null, name: "Bob", goal: "Find the map" },
          { id: null, name: "", goal: "" },
        ],
      }),
    );
  });

  it("applies the refine proposal to the draft keeping identity", async () => {
    const { onChange } = renderForm();

    fireEvent.change(screen.getByLabelText("instruction"), { target: { value: "More tension" } });
    fireEvent.click(screen.getByText("refineWithAi"));

    await waitFor(() => {
      expect(onChange).toHaveBeenCalledWith(
        expect.objectContaining({
          id: "scene-1",
          position: 2,
          status: "planned",
          title: "Rewritten Scene",
          purpose: "New purpose",
          beats: ["Beat A", "Beat B", "Beat C"],
          pov_character_ref: { id: null, name: "Claire" },
        }),
      );
    });
  });

  it("keeps edits typed while the refine call is in flight (no snapshot revert)", async () => {
    server.use(
      http.post("*/api/v1/planning/scenes/:novelId/:chapterId/refine", async () => {
        await delay(50);
        return HttpResponse.json({
          proposal: {
            title: "Rewritten Scene",
            pov_character_ref: null,
            location_ref: null,
            present_characters: [],
            purpose: "New purpose",
            conflict: "",
            resolution: "",
            beats: [],
          },
          ai_unavailable: false,
        });
      }),
    );
    const { onChange } = renderForm();

    fireEvent.click(screen.getByText("refineWithAi"));
    // Proposal lands after this edit; proposal CONTENT fields win by design,
    // but fields outside the proposal payload (status, identity) must survive.
    fireEvent.change(screen.getByLabelText("status"), { target: { value: "in_progress" } });

    await waitFor(() => {
      expect(onChange).toHaveBeenLastCalledWith(
        expect.objectContaining({
          id: "scene-1",
          position: 2,
          status: "in_progress",
          purpose: "New purpose",
        }),
      );
    });
  });

  it("shows aiUnavailable and does not touch the draft when AI is unavailable", async () => {
    server.use(
      http.post("*/api/v1/planning/scenes/:novelId/:chapterId/refine", async () => {
        return HttpResponse.json({ proposal: null, ai_unavailable: true });
      }),
    );
    const { onChange } = renderForm();

    fireEvent.click(screen.getByText("refineWithAi"));

    await waitFor(() => {
      expect(screen.getByText("aiUnavailable")).toBeDefined();
    });
    expect(onChange).not.toHaveBeenCalled();
  });
});
