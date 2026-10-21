import { describe, expect, it } from "vitest";

import de from "../../i18n/de.json";
import en from "../../i18n/en.json";
import fr from "../../i18n/fr.json";

describe("i18n catalogs", () => {
  it("carry the same keys in every locale", () => {
    const expected = Object.keys(en).sort();
    expect(Object.keys(de).sort()).toEqual(expected);
    expect(Object.keys(fr).sort()).toEqual(expected);
  });

  it("have no empty strings", () => {
    for (const [key, value] of Object.entries(en)) {
      expect(value.trim(), key).not.toBe("");
    }
  });
});
