/**
 * Slash-command parser tests (CR-AUFG-07-20).
 *
 * Covers: command detection, escaping (space/second slash → prose),
 * alias matching, and prose dismissal. The parser is a pure,
 * locale-independent function over the textblock text before the cursor.
 */
import { describe, expect, it } from "vitest";
import { filterCommands, parseSlashInput, type SlashTokenized } from "../parser";

describe("parseSlashInput", () => {
  it("activates when `/` is the first character of an empty paragraph", () => {
    const result = parseSlashInput("/", 0);
    expect(result).toEqual({ active: true, query: "", slashPos: 0 });
  });

  it("captures the query typed after the slash", () => {
    expect(parseSlashInput("/rew", 0)?.query).toBe("rew");
  });

  it("treats the slash position relative to the textblock start", () => {
    expect(parseSlashInput("/continue", 42)?.slashPos).toBe(42);
  });

  it("activates when leading whitespace precedes the slash", () => {
    const result = parseSlashInput("  /draft", 10);
    expect(result).toEqual({ active: true, query: "draft", slashPos: 12 });
  });

  it("does NOT activate when text precedes the slash (mid-paragraph)", () => {
    expect(parseSlashInput("hello /rew", 0)).toBeNull();
  });

  it("does NOT activate on an empty string", () => {
    expect(parseSlashInput("", 0)).toBeNull();
  });

  it("dismisses to prose when a space is typed after the slash+query", () => {
    // typing a space means the user is writing prose, not a command
    expect(parseSlashInput("/rewrite me", 0)).toBeNull();
  });

  it("dismisses to prose when a second slash is typed", () => {
    expect(parseSlashInput("/a/b", 0)).toBeNull();
  });

  it("activates with an empty query for a bare slash", () => {
    expect(parseSlashInput("/", 0)?.query).toBe("");
  });
});

describe("filterCommands", () => {
  const commands: SlashTokenized[] = [
    { id: "continue", tokens: ["continue", "extend", "keep writing"] },
    { id: "draft", tokens: ["draft", "generate", "write"] },
    { id: "rewrite", tokens: ["rewrite", "rephrase"] },
    { id: "coauthor", tokens: ["coauthor", "co-author", "collaborate"] },
    { id: "chat", tokens: ["chat", "ask"] },
    { id: "explain", tokens: ["explain", "clarify"] },
  ];

  it("returns all commands when the query is empty", () => {
    expect(filterCommands(commands, "")).toHaveLength(6);
  });

  it("matches by the canonical id (prefix)", () => {
    const result = filterCommands(commands, "rew");
    expect(result.map((c) => c.id)).toEqual(["rewrite"]);
  });

  it("matches by an alias token (substring)", () => {
    const result = filterCommands(commands, "rephr");
    expect(result.map((c) => c.id)).toEqual(["rewrite"]);
  });

  it("matches case-insensitively", () => {
    const result = filterCommands(commands, "DRAFT");
    expect(result.map((c) => c.id)).toEqual(["draft"]);
  });

  it("matches a hyphenated alias", () => {
    const result = filterCommands(commands, "co-aut");
    expect(result.map((c) => c.id)).toEqual(["coauthor"]);
  });

  it("returns an empty list when nothing matches", () => {
    expect(filterCommands(commands, "zzz")).toEqual([]);
  });

  it("returns multiple commands when the query is ambiguous", () => {
    // "co" matches coauthor and co-author alias of the same command;
    // "a" is ambiguous — assert it still returns matches containing "a"
    const result = filterCommands(commands, "a");
    expect(result.length).toBeGreaterThan(0);
    expect(result.map((c) => c.id)).toContain("chat");
  });
});
