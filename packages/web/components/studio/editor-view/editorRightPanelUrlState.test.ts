import { describe, expect, it } from "vitest";
import {
  parseEditorRightPanelParam,
  serializeEditorRightPanelParam,
} from "./editorRightPanelUrlState";

describe("editor right panel URL state", () => {
  it("parses safe deep-linkable panels", () => {
    expect(parseEditorRightPanelParam("metadata")).toBe("metadata");
    expect(parseEditorRightPanelParam("readability")).toBe("readability");
    expect(parseEditorRightPanelParam("voice_check")).toBe("voice_check");
  });

  it("does not deep-link unsafe session recovery without explicit recovery contract", () => {
    expect(parseEditorRightPanelParam("session")).toBeNull();
  });

  it("serializes null by removing the param", () => {
    expect(serializeEditorRightPanelParam(null)).toBeNull();
  });
});
