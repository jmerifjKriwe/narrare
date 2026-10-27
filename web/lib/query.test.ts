import { describe, expect, it } from "vitest";

import { sameNovelPlaceholder } from "./query";

/**
 * The entity list's placeholder patience: the previous answer stays on
 * screen only while the ask is still the same novel's — a narrowed filter
 * must not blank the list it narrows, but a switch to another novel must
 * not carry the previous novel's rows across. Those rows are selectable,
 * with merge, edit and delete offered on them, so showing them for a
 * story they do not belong to is a lie the next click would carry out.
 */
describe("sameNovelPlaceholder", () => {
  const placeholder = sameNovelPlaceholder("novel-1");
  const previous = [{ id: "e1" }];

  it("keeps the previous answer while the novel is the same", () => {
    expect(
      placeholder(previous, { queryKey: ["knowledge", "entities", "novel-1", {}] }),
    ).toBe(previous);
  });

  it("answers undefined when the previous answer was another novel's", () => {
    expect(
      placeholder(previous, { queryKey: ["knowledge", "entities", "novel-2", {}] }),
    ).toBeUndefined();
  });

  it("answers undefined when there is no previous query", () => {
    expect(placeholder(previous, undefined)).toBeUndefined();
  });
});
