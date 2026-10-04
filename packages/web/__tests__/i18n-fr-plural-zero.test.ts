/**
 * CLDR French plural regression (F3 closure rider, T5 re-review): 0 belongs
 * to the `one` category in French, so the dedup card's `one` branches must
 * substitute the real count via the ICU `#` placeholder. They hardcoded a
 * literal `1`, rendering "1 doublon possible" for a zero count — exactly the
 * zero-count pass CLDR routes into `one`.
 *
 * Pinned at the i18n test layer rather than BulkExtractionPanel.test.tsx
 * (whose next-intl mock is locale-pinned to "en", where 0 falls in `other`
 * and the literal was count-identical anyway): the REAL fr studio catalog
 * must render the actual number for counts 0 and 1 in both plural strings
 * consumed by DedupCard (`kb.resolution.dedupFound` / `dedupRefreshed`).
 *
 * @module i18n-fr-plural-zero
 */
import { createTranslator } from "next-intl";
import { describe, expect, it, vi } from "vitest";

// setupTests.ts replaces next-intl with a factory mock (key echo, no
// importOriginal) — restore the REAL module: this test IS the catalog pin.
vi.mock("next-intl", async (importOriginal) => importOriginal());

describe("fr studio catalog — dedup plurals substitute the real count (CLDR: 0 ∈ one)", () => {
  it("renders a zero count as 0, never the hardcoded 1, in the fr one-category", async () => {
    const { default: studio } = await import("../../i18n/messages/fr/studio.json");
    const t = createTranslator({ locale: "fr", messages: { studio }, namespace: "studio" });

    expect(t("kb.resolution.dedupFound", { count: 0 })).toBe(
      "0 doublon possible a été signalé à la fin du passage — avant l'application des éléments.",
    );
    expect(t("kb.resolution.dedupRefreshed", { count: 0 })).toBe(
      "Nouvelle vérification de la base de connaissances actuelle : 0 doublon possible.",
    );
    // Sanity: the placeholder also substitutes the canonical singular count.
    expect(t("kb.resolution.dedupRefreshed", { count: 1 })).toBe(
      "Nouvelle vérification de la base de connaissances actuelle : 1 doublon possible.",
    );
  });
});
