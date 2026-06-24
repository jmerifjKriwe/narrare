/**
 * Slash-command registry + inventory-consistency tests (CR-AUFG-07-20).
 *
 * Covers: command set, operation-id validity (spec §57/§81), requiresSelection
 * flags, alias presence, and that each command's dispatch routes to the correct
 * {@link SlashCommandDispatchContext} method (never to transport/API directly).
 */
import { describe, expect, it, vi } from "vitest";
import {
  AI_SLASH_COMMANDS,
  type AISlashCommandDefinition,
  defaultAvailability,
  KNOWN_OPERATION_IDS,
  type SlashCommandDispatchContext,
} from "../registry";

/** A recording dispatch context: every handler is a spy. */
function recordingContext(): SlashCommandDispatchContext & { calls: string[] } {
  const calls: string[] = [];
  const mark = (name: string) => () => {
    calls.push(name);
  };
  return {
    calls,
    rewriteSelection: vi.fn(mark("rewriteSelection")),
    continueWriting: vi.fn(mark("continueWriting")),
    generateDraft: vi.fn(mark("generateDraft")),
    coAuthorSelection: vi.fn(mark("coAuthorSelection")),
    askChat: vi.fn((q?: string) => calls.push(`askChat:${q ?? ""}`)),
    explainSelection: vi.fn(mark("explainSelection")),
  };
}

describe("AI_SLASH_COMMANDS command set", () => {
  it("exposes the six spec commands", () => {
    const ids = AI_SLASH_COMMANDS.map((c) => c.id);
    expect(ids).toEqual(
      expect.arrayContaining(["continue", "draft", "rewrite", "coauthor", "chat", "explain"]),
    );
    expect(AI_SLASH_COMMANDS).toHaveLength(6);
  });

  it("each command has at least one alias for discoverability", () => {
    for (const cmd of AI_SLASH_COMMANDS) {
      expect(cmd.aliases.length).toBeGreaterThan(0);
    }
  });

  it("commands requiring a selection are flagged", () => {
    const byId = Object.fromEntries(AI_SLASH_COMMANDS.map((c) => [c.id, c]));
    expect(byId.rewrite.requiresSelection).toBe(true);
    expect(byId.coauthor.requiresSelection).toBe(true);
    expect(byId.explain.requiresSelection).toBe(true);
    expect(byId.continue.requiresSelection).toBe(false);
    expect(byId.draft.requiresSelection).toBe(false);
    expect(byId.chat.requiresSelection).toBe(false);
  });

  it("label/description keys live under the slashCommands i18n namespace", () => {
    for (const cmd of AI_SLASH_COMMANDS) {
      expect(cmd.labelKey.startsWith("slashCommands.")).toBe(true);
      expect(cmd.descriptionKey.startsWith("slashCommands.")).toBe(true);
    }
  });
});

describe("inventory consistency (spec §57/§81)", () => {
  it("every command references a known operation id", () => {
    for (const cmd of AI_SLASH_COMMANDS) {
      expect(KNOWN_OPERATION_IDS.has(cmd.operationId)).toBe(true);
    }
  });

  it("exposes the documented writing/chat operation ids", () => {
    for (const id of [
      "writing.continue",
      "writing.generation",
      "writing.rewrite",
      "writing.co_author",
      "chat.free_assistant",
    ]) {
      expect(KNOWN_OPERATION_IDS.has(id)).toBe(true);
    }
  });
});

describe("dispatch routing (no direct transport calls)", () => {
  it("continue dispatches to continueWriting", () => {
    const ctx = recordingContext();
    AI_SLASH_COMMANDS.find((c) => c.id === "continue")!.dispatch(ctx);
    expect(ctx.continueWriting).toHaveBeenCalledOnce();
    expect(ctx.calls).toEqual(["continueWriting"]);
  });

  it("draft dispatches to generateDraft", () => {
    const ctx = recordingContext();
    AI_SLASH_COMMANDS.find((c) => c.id === "draft")!.dispatch(ctx);
    expect(ctx.generateDraft).toHaveBeenCalledOnce();
  });

  it("rewrite dispatches to rewriteSelection", () => {
    const ctx = recordingContext();
    AI_SLASH_COMMANDS.find((c) => c.id === "rewrite")!.dispatch(ctx);
    expect(ctx.rewriteSelection).toHaveBeenCalledOnce();
  });

  it("coauthor dispatches to coAuthorSelection", () => {
    const ctx = recordingContext();
    AI_SLASH_COMMANDS.find((c) => c.id === "coauthor")!.dispatch(ctx);
    expect(ctx.coAuthorSelection).toHaveBeenCalledOnce();
  });

  it("chat dispatches to askChat", () => {
    const ctx = recordingContext();
    AI_SLASH_COMMANDS.find((c) => c.id === "chat")!.dispatch(ctx);
    expect(ctx.askChat).toHaveBeenCalledOnce();
  });

  it("explain dispatches to explainSelection", () => {
    const ctx = recordingContext();
    AI_SLASH_COMMANDS.find((c) => c.id === "explain")!.dispatch(ctx);
    expect(ctx.explainSelection).toHaveBeenCalledOnce();
  });
});

describe("defaultAvailability", () => {
  const requiresSelectionCmd: Pick<AISlashCommandDefinition, "requiresSelection"> = {
    requiresSelection: true,
  };
  const noSelectionCmd: Pick<AISlashCommandDefinition, "requiresSelection"> = {
    requiresSelection: false,
  };

  it("returns 'unavailable' when the host did not wire the handler", () => {
    const avail = defaultAvailability(noSelectionCmd.requiresSelection);
    expect(avail({ hasSelection: false, wired: false })).toBe("unavailable");
  });

  it("returns 'no-selection' for selection commands without a selection", () => {
    const avail = defaultAvailability(requiresSelectionCmd.requiresSelection);
    expect(avail({ hasSelection: false, wired: true })).toBe("no-selection");
  });

  it("returns 'available' when wired and selection requirements are met", () => {
    expect(
      defaultAvailability(requiresSelectionCmd.requiresSelection)({
        hasSelection: true,
        wired: true,
      }),
    ).toBe("available");
    expect(
      defaultAvailability(noSelectionCmd.requiresSelection)({ hasSelection: false, wired: true }),
    ).toBe("available");
  });
});
