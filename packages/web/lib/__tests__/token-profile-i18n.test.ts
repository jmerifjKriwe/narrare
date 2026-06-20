/**
 * Token-profile i18n contract (CR-08 P1 D2).
 *
 * The retired `conservative` profile must not remain available through locale
 * labels after the TypeScript/API option lists remove it.
 */

import deStudio from "../../../i18n/messages/de/studio.json";
import enStudio from "../../../i18n/messages/en/studio.json";
import frStudio from "../../../i18n/messages/fr/studio.json";

describe("token-profile i18n labels", () => {
  it.each([
    ["en", enStudio],
    ["de", deStudio],
    ["fr", frStudio],
  ])("%s exposes labels for exactly the five public token profiles", (_locale, messages) => {
    const aiMessages = messages.settings.ai;

    expect(Object.keys(aiMessages).filter((key) => key.startsWith("tokenProfile"))).toEqual([
      "tokenProfile",
      "tokenProfileQuick",
      "tokenProfileBalanced",
      "tokenProfileLong",
      "tokenProfileComprehensive",
      "tokenProfileCustom",
    ]);
    expect(aiMessages).not.toHaveProperty("tokenProfileConservative");
    expect(messages.tokenSettings).not.toHaveProperty("profileConservative");
  });
});
