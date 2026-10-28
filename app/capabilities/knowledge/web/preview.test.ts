/**
 * The entity card's preview text: display-only decoding of the stored
 * Markdown. The store keeps the serializer's canonical bytes (`&amp;`,
 * `\_`, …); the glance must read like the document, not like the storage
 * format — so entities decode to their characters and the backslash
 * escapes lose the backslash, while the stored value itself is untouched
 * (a pure string in, string out — nothing here edits an entity).
 */
import { describe, expect, it } from "vitest";

import { previewText } from "./preview";

describe("the entity card's preview text", () => {
  it("decodes the serializer's HTML entities", () => {
    expect(previewText("# Communication Systems &amp; Protocols")).toBe(
      "# Communication Systems & Protocols",
    );
    expect(previewText("kleiner &lt; als &gt; dort")).toBe("kleiner < als > dort");
  });

  it("strips the serializer's backslash escapes", () => {
    expect(previewText("## word\\_count")).toBe("## word_count");
    expect(previewText("ein \\* Stern, ein \\[ Klammer, ein \\~ Tilde")).toBe(
      "ein * Stern, ein [ Klammer, ein ~ Tilde",
    );
    expect(previewText("Code \\`x\\`")).toBe("Code `x`");
  });

  it("reads like the document when the store carries both shapes", () => {
    expect(previewText("Mira &amp; der \\_Waldgeist\\_")).toBe("Mira & der _Waldgeist_");
  });

  it("leaves plain prose untouched", () => {
    const body = "# Herkunft\n\nMira wuchs an der Bucht auf.";
    expect(previewText(body)).toBe(body);
  });
});
