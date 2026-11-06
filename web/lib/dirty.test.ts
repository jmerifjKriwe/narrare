import { describe, expect, it } from "vitest";
import { dirtyFields } from "./dirty";

describe("dirtyFields", () => {
  it("finds nothing in an unchanged form", () => {
    expect(dirtyFields({ name: "a", key: "" }, { name: "a", key: "" })).toEqual([]);
  });

  it("names the field that changed", () => {
    expect(dirtyFields({ name: "a", key: "x" }, { name: "a", key: "" })).toEqual(["key"]);
  });

  it("compares shallowly and by value", () => {
    expect(dirtyFields({ a: 1, b: [1] }, { a: 1, b: [1] })).toEqual([]);
  });
});
