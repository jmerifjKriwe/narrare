import { describe, expect, it } from "vitest";
import { parseSettingsCategory, serializeSettingsCategory } from "./settingsUrlState";

describe("settings URL state", () => {
  it("parses valid category", () => expect(parseSettingsCategory("ai")).toBe("ai"));
  it("falls back for invalid category", () =>
    expect(parseSettingsCategory("missing")).toBe("novel-details"));
  it("serializes default as null", () =>
    expect(serializeSettingsCategory("novel-details")).toBeNull());
});
