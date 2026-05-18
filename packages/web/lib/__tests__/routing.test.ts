import { describe, expect, it } from "vitest";
import { routing } from "@/lib/i18n/routing";

describe("routing", () => {
  it("has English, German, and French locales", () => {
    expect(routing.locales).toEqual(["en", "de", "fr"]);
  });

  it("has English as default locale", () => {
    expect(routing.defaultLocale).toBe("en");
  });
});
