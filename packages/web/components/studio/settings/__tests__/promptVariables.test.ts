/**
 * Unit tests for the pure prompt-id parsing helpers.
 *
 * These helpers feed the PROMPT-003 preview/live-test request bodies, so the
 * parser contract (3-segment layout, safe fallback, no fabricated project
 * variables) must be locked down independently of the React hooks.
 */

import { describe, expect, it } from "vitest";
import { buildSystemVariables, parsePromptId } from "@/components/studio/settings/promptVariables";

describe("parsePromptId", () => {
  it("parses a canonical {category}/{language}/{mode} id", () => {
    expect(parsePromptId("writing/en/new_chapter")).toEqual({
      category: "writing",
      language: "en",
      mode: "new_chapter",
    });
  });

  it("returns the safe fallback for a two-segment id", () => {
    expect(parsePromptId("generation/names")).toEqual({
      category: "",
      language: "en",
      mode: "",
    });
  });

  it("returns the safe fallback for an empty string", () => {
    expect(parsePromptId("")).toEqual({ category: "", language: "en", mode: "" });
  });

  it("returns the safe fallback when a segment is empty", () => {
    expect(parsePromptId("writing//new_chapter")).toEqual({
      category: "",
      language: "en",
      mode: "",
    });
    expect(parsePromptId("/en/new_chapter")).toEqual({
      category: "",
      language: "en",
      mode: "",
    });
    expect(parsePromptId("writing/en/")).toEqual({
      category: "",
      language: "en",
      mode: "",
    });
  });

  it("returns the safe fallback for a four-segment id", () => {
    expect(parsePromptId("writing/en/new/chapter")).toEqual({
      category: "",
      language: "en",
      mode: "",
    });
  });
});

describe("buildSystemVariables", () => {
  it("derives language and mode for a canonical id", () => {
    expect(buildSystemVariables("writing/de/new_chapter", "de")).toEqual({
      language: "de",
      mode: "new_chapter",
    });
  });

  it("uses the caller-supplied language prop (not the id segment) for variables.language", () => {
    // The UI language is the source of truth for the request body; the id
    // segment is informational only. Both happen to match in production.
    expect(buildSystemVariables("writing/en/new_chapter", "de")).toEqual({
      language: "de",
      mode: "new_chapter",
    });
  });

  it("omits mode when the id is malformed", () => {
    expect(buildSystemVariables("generation/names", "en")).toEqual({ language: "en" });
  });

  it("never fabricates project-context variables", () => {
    const vars = buildSystemVariables("writing/en/new_chapter", "en");
    expect(Object.keys(vars).sort()).toEqual(["language", "mode"]);
    expect(vars).not.toHaveProperty("project_title");
    expect(vars).not.toHaveProperty("storyboard");
    expect(vars).not.toHaveProperty("kb_summary");
  });
});
