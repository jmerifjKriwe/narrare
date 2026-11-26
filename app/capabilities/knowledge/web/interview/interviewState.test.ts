/**
 * The interview's pure state (W9 Task 10): which face the panel draws from
 * the session, its turns, a running turn and a named failure. The eleven
 * faces of the states reference reduce to six — the chooser, the question,
 * the assistant thinking, a pending suggestion, a named failure and the
 * ended interview — while «answered», «everything suggested», the list and
 * the door are variations of those (a proposal's marks, a local view, the
 * graph's own button). `readyToSave` is the one fact the interface decides
 * itself: a name is present. The pending suggestion is the newest assistant
 * turn the writer has not settled yet.
 */
import { describe, expect, it } from "vitest";

import type { AssistantSession, AssistantTurnRead, Proposal } from "@shell/lib/api/client";

import { interviewFace, ENTITY_TYPE_ORDER, OPENING_KEYS, openingQuestionKey, pendingSuggestion, readyToSave } from "./interviewState";

function turn(overrides: Partial<AssistantTurnRead> & { seq: number }): AssistantTurnRead {
  return {
    role: "assistant",
    text: "",
    act: null,
    suggestion: null,
    suggestion_state: null,
    created_at: "2026-11-24T14:02:00Z",
    ...overrides,
  };
}

function proposal(overrides: Partial<Proposal> = {}): Proposal {
  return {
    name: null,
    name_suggested: false,
    aliases: [],
    tags: [],
    content: "",
    relations: [],
    ...overrides,
  };
}

const open = { closed_at: null } as Pick<AssistantSession, "closed_at">;
const closed = { closed_at: "2026-11-24T14:30:00Z" } as Pick<AssistantSession, "closed_at">;

describe("the face follows the session", () => {
  it("asks for a type while no session stands", () => {
    expect(interviewFace({ session: null, turns: [], pending: false, failure: null })).toBe("chooser");
  });

  it("opens with the first question on a fresh session", () => {
    expect(interviewFace({ session: open, turns: [], pending: false, failure: null })).toBe("question");
  });

  it("thinks while a turn runs, before any other face", () => {
    // A standing failure does not compete with the running turn: the panel
    // says that it is thinking, and the failed face returns only afterwards.
    expect(
      interviewFace({
        session: open,
        turns: [],
        pending: true,
        failure: { code: "provider-error" },
      }),
    ).toBe("thinking");
  });

  it("offers a pending suggestion after the turn that carried it", () => {
    const turns = [
      turn({ seq: 1, role: "user", text: "Keine Ahnung", act: "no-idea" }),
      turn({ seq: 2, suggestion: "Ein Vorschlag.", suggestion_state: "pending" }),
    ];
    expect(interviewFace({ session: open, turns, pending: false, failure: null })).toBe("suggestion");
    expect(pendingSuggestion(turns)?.suggestion).toBe("Ein Vorschlag.");
  });

  it("draws the named failure while it stands", () => {
    expect(
      interviewFace({
        session: open,
        turns: [],
        pending: false,
        failure: { code: "extraction-failed" },
      }),
    ).toBe("failed");
  });

  it("draws the failed face for a refused prompt too", () => {
    expect(
      interviewFace({ session: open, turns: [], pending: false, failure: { code: "prompt-refused" } }),
    ).toBe("failed");
  });

  it("is read-only once the session is closed, whatever else stands", () => {
    expect(
      interviewFace({
        session: closed,
        turns: [],
        pending: false,
        failure: { code: "provider-error" },
      }),
    ).toBe("ended");
  });
});

describe("the pending suggestion is the newest unsettled one", () => {
  it("ignores settled suggestions", () => {
    const turns = [
      turn({ seq: 1, suggestion: "Alt.", suggestion_state: "accepted" }),
      turn({ seq: 2, suggestion: "Neu.", suggestion_state: "pending" }),
      turn({ seq: 3, suggestion: "Verworfen.", suggestion_state: "rejected" }),
    ];
    expect(pendingSuggestion(turns)?.seq).toBe(2);
  });

  it("is absent when nothing is pending", () => {
    expect(pendingSuggestion([turn({ seq: 1, role: "user", text: "Hallo" })])).toBeNull();
  });
});

describe("the opening question follows the type", () => {
  it("names every type's own question", () => {
    for (const type of ENTITY_TYPE_ORDER) {
      expect(openingQuestionKey(type)).toBe(OPENING_KEYS[type]);
    }
  });

  it("falls back to the generic question for a type the contract may add later", () => {
    // The type comes from a contract that may grow: an unknown name, an absent
    // one and an interview without a session all ask the generic question.
    expect(openingQuestionKey("artifact")).toBe("knowledge.interview.opening.generic");
    expect(openingQuestionKey(null)).toBe("knowledge.interview.opening.generic");
    expect(openingQuestionKey(undefined)).toBe("knowledge.interview.opening.generic");
  });
});

describe("ready needs a name", () => {
  it("is not ready without a proposal or with an empty name", () => {
    expect(readyToSave(null)).toBe(false);
    expect(readyToSave(proposal({ name: null }))).toBe(false);
    expect(readyToSave(proposal({ name: "" }))).toBe(false);
    expect(readyToSave(proposal({ name: "   " }))).toBe(false);
  });

  it("is ready once a name stands, whatever else is open", () => {
    expect(readyToSave(proposal({ name: "Resonanz-Transponder LC-89" }))).toBe(true);
  });
});
