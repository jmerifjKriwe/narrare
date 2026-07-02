import { describe, expect, it } from "vitest";
import { parseAnalysisPanelParam, serializeAnalysisPanelParam } from "./analysisUrlState";

describe("analysis URL state", () => {
  it("parses readability panel", () =>
    expect(parseAnalysisPanelParam("readability")).toBe("readability"));
  it("returns null for invalid panel", () => expect(parseAnalysisPanelParam("missing")).toBeNull());
  it("serializes null by removing panel", () =>
    expect(serializeAnalysisPanelParam(null)).toBeNull());
});
