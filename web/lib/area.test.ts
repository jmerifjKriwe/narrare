import { describe, expect, it } from "vitest";
import { AREA_ICON } from "./area";

describe("AREA_ICON", () => {
  it("names one text utility per area", () => {
    expect(AREA_ICON).toEqual({
      writing: "text-area-writing",
      knowledge: "text-area-knowledge",
      chat: "text-area-chat",
      planning: "text-area-planning",
      settings: "text-area-settings",
    });
  });
});
