/**
 * Tests for the CharacterArcPanel component.
 *
 * Mocks only the API boundary (@/lib/api/character-arc) and next-intl,
 * letting the real useAIOperation hook exercise the lifecycle so the
 * tests verify actual integration behavior (loading → complete → error).
 */
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

// The deferred-promise pattern lets us assert the loading state before
// resolving, then assert the result state after.
let resolveGenerate: (value: unknown) => void;
let rejectGenerate: (reason?: unknown) => void;

vi.mock("@/lib/api/character-arc", () => ({
  generateCharacterArc: vi.fn(
    () =>
      new Promise((resolve, reject) => {
        resolveGenerate = resolve;
        rejectGenerate = reject;
      }),
  ),
}));

// Mock next-intl — returns the key path so assertions are deterministic.
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

import { CharacterArcPanel } from "@/components/studio/planning/CharacterArcPanel";
import { generateCharacterArc } from "@/lib/api/character-arc";

const MOCK_RESPONSE = {
  character_name: "Alice",
  starting_state: "Afraid and uncertain",
  ending_state: "Confident leader",
  arc_type: "growth",
  phases: [
    {
      phase_name: "The Call",
      description: "Alice faces her first challenge",
      emotional_state: "Fearful but determined",
      turning_point: "Accepts the quest",
      chapters_suggested: "1-3",
    },
  ],
  key_relationships: ["Mentor: Gandalf", "Rival: Bob"],
  internal_conflict: "Doubt vs. duty",
  resolution: "Embraces her role",
};

describe("CharacterArcPanel", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // --- 1. Form renders with all inputs ---

  it("renders the form with character name, states, and generate button", () => {
    render(<CharacterArcPanel novelId="novel-1" />);

    expect(screen.getByText("characterArc.title")).toBeDefined();
    expect(screen.getByLabelText("characterArc.characterName")).toBeDefined();
    expect(screen.getByLabelText("characterArc.currentState")).toBeDefined();
    expect(screen.getByLabelText("characterArc.goalState")).toBeDefined();
    expect(screen.getByText("characterArc.generate")).toBeDefined();
  });

  // --- 2. Character name is required (validation) ---

  it("disables the generate button until a character name is entered", () => {
    render(<CharacterArcPanel novelId="novel-1" />);

    const generateButton = screen.getByText("characterArc.generate").closest("button");
    expect(generateButton?.disabled).toBe(true);

    const nameInput = screen.getByLabelText("characterArc.characterName");
    fireEvent.change(nameInput, { target: { value: "Alice" } });

    expect(generateButton?.disabled).toBe(false);
  });

  // --- 3. Loading state while generating, then results ---

  it("shows loading state then displays results on success", async () => {
    render(<CharacterArcPanel novelId="novel-1" />);

    // Fill the form
    fireEvent.change(screen.getByLabelText("characterArc.characterName"), {
      target: { value: "Alice" },
    });
    fireEvent.change(screen.getByLabelText("characterArc.currentState"), {
      target: { value: "afraid" },
    });

    // Submit
    fireEvent.click(screen.getByText("characterArc.generate"));

    // Loading state — button disabled, loading text shown
    await waitFor(() => {
      expect(screen.getByText("characterArc.loading")).toBeDefined();
    });

    // The API was called with the form values + novelId
    expect(generateCharacterArc).toHaveBeenCalledWith(
      "novel-1",
      {
        character_name: "Alice",
        character_current_state: "afraid",
        character_goal_state: "",
      },
      expect.any(AbortSignal),
    );

    // Resolve the deferred promise
    act(() => {
      resolveGenerate(MOCK_RESPONSE);
    });

    // Results appear
    await waitFor(() => {
      expect(screen.getByText("Alice")).toBeDefined();
    });
    expect(screen.getByText("characterArc.arcType.growth")).toBeDefined();
    expect(screen.getByText("Afraid and uncertain")).toBeDefined();
    expect(screen.getByText("Confident leader")).toBeDefined();
    expect(screen.getByText("The Call")).toBeDefined();
    expect(screen.getByText("Mentor: Gandalf")).toBeDefined();
    expect(screen.getByText("Doubt vs. duty")).toBeDefined();
    expect(screen.getByText("Embraces her role")).toBeDefined();
  });

  // --- 4. Error handling ---

  it("displays an error message when generation fails", async () => {
    render(<CharacterArcPanel novelId="novel-1" />);

    fireEvent.change(screen.getByLabelText("characterArc.characterName"), {
      target: { value: "Alice" },
    });
    fireEvent.click(screen.getByText("characterArc.generate"));

    await waitFor(() => {
      expect(screen.getByText("characterArc.loading")).toBeDefined();
    });

    act(() => {
      rejectGenerate(new Error("Server exploded"));
    });

    await waitFor(() => {
      // Error rendered in an alert region
      const alert = screen.getByRole("alert");
      expect(alert.textContent).toContain("Server exploded");
    });
  });

  // --- 5. Reset allows generating again after error ---

  it("can generate again after an error", async () => {
    render(<CharacterArcPanel novelId="novel-1" />);

    fireEvent.change(screen.getByLabelText("characterArc.characterName"), {
      target: { value: "Alice" },
    });
    fireEvent.click(screen.getByText("characterArc.generate"));

    await waitFor(() => expect(screen.getByText("characterArc.loading")).toBeDefined());
    act(() => {
      rejectGenerate(new Error("fail"));
    });

    await waitFor(() => expect(screen.getByRole("alert")).toBeDefined());

    // Generate button is enabled again (error state is retryable)
    const generateButton = screen.getByText("characterArc.generate").closest("button");
    expect(generateButton?.disabled).toBe(false);
  });
});
