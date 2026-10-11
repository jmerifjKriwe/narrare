/**
 * SceneListEditors tests — beats string-list + present-characters editors.
 *
 * Tests:
 * 1. Beats: render rows
 * 2. Beats: add appends an empty entry
 * 3. Beats: edit a row's text
 * 4. Beats: remove a row
 * 5. Beats: move down / move up reorder
 * 6. Characters: render rows
 * 7. Characters: edit name and goal
 * 8. Characters: add an empty row
 * 9. Characters: remove a row
 */

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { BeatsEditor, CharactersEditor } from "@/components/studio/planning/SceneListEditors";
import type { ScenePresence } from "@/types/planning";

const presences: ScenePresence[] = [
  { id: null, name: "Bob", goal: "Find the map" },
  { id: null, name: "Eve", goal: "" },
];

describe("BeatsEditor", () => {
  it("renders one input per beat", () => {
    render(<BeatsEditor beats={["Arrival", "Argument"]} onChange={vi.fn()} />);

    expect(screen.getAllByLabelText("beats")).toHaveLength(2);
    expect(screen.getAllByLabelText("beats")[0]).toHaveValue("Arrival");
  });

  it("adds an empty beat", () => {
    const onChange = vi.fn();
    render(<BeatsEditor beats={["Arrival"]} onChange={onChange} />);

    fireEvent.click(screen.getByText("addBeat"));

    expect(onChange).toHaveBeenLastCalledWith(["Arrival", ""]);
  });

  it("edits a beat's text", () => {
    const onChange = vi.fn();
    render(<BeatsEditor beats={["Arrival", "Argument"]} onChange={onChange} />);

    fireEvent.change(screen.getAllByLabelText("beats")[0], { target: { value: "Edited" } });

    expect(onChange).toHaveBeenLastCalledWith(["Edited", "Argument"]);
  });

  it("removes a beat", () => {
    const onChange = vi.fn();
    render(<BeatsEditor beats={["Arrival", "Argument", "Extra"]} onChange={onChange} />);

    const removeButtons = screen.getAllByLabelText("removeBeat");
    fireEvent.click(removeButtons[2]);

    expect(onChange).toHaveBeenLastCalledWith(["Arrival", "Argument"]);
  });

  it("moves a beat down", () => {
    const onChange = vi.fn();
    render(<BeatsEditor beats={["Arrival", "Argument"]} onChange={onChange} />);

    fireEvent.click(screen.getAllByLabelText("moveBeatDown")[0]);

    expect(onChange).toHaveBeenLastCalledWith(["Argument", "Arrival"]);
  });

  it("moves a beat up and disables the first row's move-up", () => {
    const onChange = vi.fn();
    render(<BeatsEditor beats={["One", "Two", "Three"]} onChange={onChange} />);

    expect(screen.getAllByLabelText("moveBeatUp")[0]).toBeDisabled();

    fireEvent.click(screen.getAllByLabelText("moveBeatUp")[2]);

    expect(onChange).toHaveBeenLastCalledWith(["One", "Three", "Two"]);
  });
});

describe("CharactersEditor", () => {
  it("renders name and goal inputs per row", () => {
    render(<CharactersEditor characters={presences} onChange={vi.fn()} />);

    expect(screen.getAllByLabelText("characters")).toHaveLength(2);
    expect(screen.getAllByLabelText("characterGoal")).toHaveLength(2);
    expect(screen.getAllByLabelText("characters")[0]).toHaveValue("Bob");
  });

  it("edits a character's name and goal", () => {
    const onChange = vi.fn();
    render(<CharactersEditor characters={presences} onChange={onChange} />);

    fireEvent.change(screen.getAllByLabelText("characters")[1], { target: { value: "Zoe" } });
    expect(onChange).toHaveBeenLastCalledWith([
      { id: null, name: "Bob", goal: "Find the map" },
      { id: null, name: "Zoe", goal: "" },
    ]);

    fireEvent.change(screen.getAllByLabelText("characterGoal")[0], {
      target: { value: "New goal" },
    });
    expect(onChange).toHaveBeenLastCalledWith([
      { id: null, name: "Bob", goal: "New goal" },
      { id: null, name: "Eve", goal: "" },
    ]);
  });

  it("adds an empty character row", () => {
    const onChange = vi.fn();
    render(<CharactersEditor characters={presences} onChange={onChange} />);

    fireEvent.click(screen.getByText("addCharacter"));

    expect(onChange).toHaveBeenLastCalledWith([...presences, { id: null, name: "", goal: "" }]);
  });

  it("removes a character row", () => {
    const onChange = vi.fn();
    render(<CharactersEditor characters={presences} onChange={onChange} />);

    const removeButtons = screen.getAllByLabelText("removeCharacter");
    fireEvent.click(removeButtons[removeButtons.length - 1]);

    expect(onChange).toHaveBeenLastCalledWith([{ id: null, name: "Bob", goal: "Find the map" }]);
  });
});
