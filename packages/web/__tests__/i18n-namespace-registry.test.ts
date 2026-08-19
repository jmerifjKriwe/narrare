/**
 * Regression test: Missing i18n namespace registration
 *
 * Bug: The `namespaces` array in `lib/i18n/request.ts` must include every
 * namespace that components reference via `useTranslations("X")`. When a
 * namespace is omitted, next-intl silently returns raw keys instead of
 * translated strings — no runtime crash, just broken UI.
 *
 * Previously the "generation" namespace was used in components but missing
 * from the registry, causing untranslated labels in the NameGenerator UI.
 *
 * Note: The current app uses a single "studio" namespace for all translations.
 */

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const WEB_ROOT = resolve(__dirname, "..");
// packages/i18n/messages — the base message catalogs (locale dirs ONLY).
// packages/i18n/overlays/formality — the sparse formality overlays. Kept out of
//   messages/ on purpose: validate-i18n scans every messages/ subdir as a locale,
//   and `formality` is a register, not a locale (Feature Spec I-Copy-001).
const I18N_MESSAGES = resolve(WEB_ROOT, "..", "i18n", "messages");
const I18N_OVERLAYS = resolve(WEB_ROOT, "..", "i18n", "overlays");
const FORMALITY_DIR = join(I18N_OVERLAYS, "formality");

/** Directories to skip when scanning for source files. */
const SKIP_DIRS = new Set([
  "node_modules",
  ".next",
  "__tests__",
  "_archive_app",
  "_archive_components",
  "_archive_styles",
  "_archive_tests",
]);

/** Recursively collect all .ts/.tsx file paths, skipping unwanted dirs. */
function collectSourceFiles(dir: string, files: string[] = []): string[] {
  const entries = readdirSync(dir);
  for (const entry of entries) {
    const fullPath = join(dir, entry);
    // Skip directories we don't want to scan
    if (SKIP_DIRS.has(entry)) {
      continue;
    }
    const stat = statSync(fullPath);
    if (stat.isDirectory()) {
      collectSourceFiles(fullPath, files);
    } else if (
      (fullPath.endsWith(".ts") || fullPath.endsWith(".tsx")) &&
      !fullPath.endsWith(".test.ts") &&
      !fullPath.endsWith(".test.tsx") &&
      !fullPath.endsWith("request.ts")
    ) {
      files.push(fullPath);
    }
  }
  return files;
}

describe("i18n namespace registry completeness", () => {
  /** Extract the namespaces array from request.ts */
  function getRegisteredNamespaces(): string[] {
    const requestPath = resolve(WEB_ROOT, "lib", "i18n", "request.ts");
    const source = readFileSync(requestPath, "utf-8");

    // Match the array literal assigned to `const namespaces`
    const arrayMatch = source.match(/const namespaces\s*=\s*\[([\s\S]*?)\]\s*as\s*const/);
    if (!arrayMatch) {
      throw new Error("Could not find namespaces array in request.ts");
    }

    return arrayMatch[1]
      .split(",")
      .map((s: string) => s.trim().replace(/"/g, "").replace(/'/g, ""))
      .filter((s: string) => s.length > 0);
  }

  /** Find all useTranslations("X") namespace references in source files. */
  function findUsedNamespaces(): Set<string> {
    const files = collectSourceFiles(WEB_ROOT);
    const namespaces = new Set<string>();

    // Regex: captures the string argument inside useTranslations("xxx")
    const useTranslationsRe = /useTranslations\s*\(\s*["']([^"']+)["']\s*\)/g;

    for (const filePath of files) {
      const source = readFileSync(filePath, "utf-8");
      // Reset lastIndex for global regex
      useTranslationsRe.lastIndex = 0;
      let match: RegExpExecArray | null = useTranslationsRe.exec(source);
      while (match !== null) {
        // Use only the root namespace (before any dot) — dotted access like
        // "settings-ai.categories" is nested next-intl key access, not a
        // separate namespace file.
        namespaces.add(match[1].split(".")[0]);
        match = useTranslationsRe.exec(source);
      }
    }
    return namespaces;
  }

  it("every useTranslations namespace is registered in request.ts", () => {
    const registered = getRegisteredNamespaces();
    const used = findUsedNamespaces();

    const missing: string[] = [];
    for (const ns of used) {
      if (!registered.includes(ns)) {
        missing.push(ns);
      }
    }

    if (missing.length > 0) {
      // This assertion will fail, showing which namespaces are missing
      expect(
        missing,
        `The following namespaces are used via useTranslations() but not registered in lib/i18n/request.ts: ${missing.join(", ")}. ` +
          `Add them to the 'namespaces' array in request.ts.`,
      ).toEqual([]);
    }

    // Also verify we actually found some namespaces (sanity check)
    expect(used.size).toBeGreaterThan(0);
    expect(registered.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Formality overlay governance (Feature Spec I-Copy-001)
// ---------------------------------------------------------------------------
// The sparse `overlays/formality/{de,fr}.json` overlays deep-merge over the base
// catalog. These assertions keep the overlay honest:
//   1. de + fr overlays exist, NO en overlay (en is byte-identical).
//   2. Every overlay key path resolves to a real base key (no orphaned
//      overrides — e.g. a typo, or a key removed from the base).
//   3. The de and fr override key-path sets match (parity — the same strings
//      need a formal variant in both languages).
//   4. Every FR overlay value byte-equals its base value: the FR overlay is a
//      documented no-op pin (the base already uses vouvoiement). This makes
//      the pin self-maintaining — a base edit that diverges from a stale pin
//      would otherwise be silently shadowed by the overlay at merge time.

/** Parse a JSON file as a generic message object. */
function readJson(filePath: string): Record<string, unknown> {
  return JSON.parse(readFileSync(filePath, "utf-8")) as Record<string, unknown>;
}

/**
 * Collect every LEAF path (dotted, e.g. "wizard.step1.description") in a
 * message object. Leaves are the override targets; nested branch objects are
 * not themselves overrides.
 */
function collectLeafPaths(obj: unknown, prefix = ""): string[] {
  const paths: string[] = [];
  if (obj === null || typeof obj !== "object" || Array.isArray(obj)) {
    return paths;
  }
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      paths.push(...collectLeafPaths(value, path));
    } else {
      paths.push(path);
    }
  }
  return paths;
}

/** Walk `obj` along `segments`; return the value, or undefined when missing. */
function getPath(obj: unknown, segments: string[]): unknown {
  let current: unknown = obj;
  for (const segment of segments) {
    if (current === null || typeof current !== "object" || Array.isArray(current)) {
      return undefined;
    }
    current = (current as Record<string, unknown>)[segment];
    if (current === undefined) {
      return undefined;
    }
  }
  return current;
}

/** Walk `obj` along `segments`; return true iff the full path exists. */
function pathExists(obj: unknown, segments: string[]): boolean {
  return getPath(obj, segments) !== undefined;
}

/**
 * Verify every overlay leaf path resolves to a key in the base catalog for the
 * given locale. Returns the list of orphaned paths (empty when all resolve).
 */
function findOrphanedOverrides(locale: string): string[] {
  const overlayPath = join(FORMALITY_DIR, `${locale}.json`);
  const overlay = readJson(overlayPath);
  const orphans: string[] = [];
  for (const dotted of collectLeafPaths(overlay)) {
    const [namespace, ...rest] = dotted.split(".");
    const baseFile = join(I18N_MESSAGES, locale, `${namespace}.json`);
    if (!existsSync(baseFile) || !pathExists(readJson(baseFile), rest)) {
      orphans.push(dotted);
    }
  }
  return orphans;
}

describe("formality overlay governance", () => {
  it("provides de + fr overlays and NO en overlay (en is byte-identical)", () => {
    expect(existsSync(join(FORMALITY_DIR, "de.json"))).toBe(true);
    expect(existsSync(join(FORMALITY_DIR, "fr.json"))).toBe(true);
    expect(existsSync(join(FORMALITY_DIR, "en.json"))).toBe(false);
  });

  it("has no orphaned overrides in the de overlay (every key exists in the base)", () => {
    const orphans = findOrphanedOverrides("de");
    expect(
      orphans,
      `de formality overlay keys with no matching base key: ${orphans.join(", ")}. ` +
        "Remove them or fix the typo/path.",
    ).toEqual([]);
  });

  it("has no orphaned overrides in the fr overlay (every key exists in the base)", () => {
    const orphans = findOrphanedOverrides("fr");
    expect(
      orphans,
      `fr formality overlay keys with no matching base key: ${orphans.join(", ")}. ` +
        "Remove them or fix the typo/path.",
    ).toEqual([]);
  });

  it("de and fr overlay key-path sets match (parity)", () => {
    const dePaths = collectLeafPaths(readJson(join(FORMALITY_DIR, "de.json"))).sort();
    const frPaths = collectLeafPaths(readJson(join(FORMALITY_DIR, "fr.json"))).sort();
    expect(
      frPaths,
      "de/fr formality overlay parity drift — the same strings need a formal " +
        `variant in both languages. Only in de: ${dePaths
          .filter((p) => !frPaths.includes(p))
          .join(", ")}. Only in fr: ${frPaths.filter((p) => !dePaths.includes(p)).join(", ")}.`,
    ).toEqual(dePaths);
  });

  it("every fr overlay value byte-equals its base value (self-maintaining no-op pin)", () => {
    const overlay = readJson(join(FORMALITY_DIR, "fr.json"));
    const overlayPaths = collectLeafPaths(overlay);
    // Sanity guard: an emptied overlay would make this test vacuously green.
    expect(overlayPaths.length).toBeGreaterThan(0);

    const diverged: string[] = [];
    for (const dotted of overlayPaths) {
      const [namespace, ...rest] = dotted.split(".");
      const baseFile = join(I18N_MESSAGES, "fr", `${namespace}.json`);
      // Orphaned paths (missing base file/key) are reported by the orphan
      // tests above; here a missing base counts as divergence, not a crash.
      const baseValue = existsSync(baseFile) ? getPath(readJson(baseFile), rest) : undefined;
      const overlayValue = getPath(overlay, dotted.split("."));
      if (overlayValue !== baseValue) {
        diverged.push(
          `${dotted} (overlay=${JSON.stringify(overlayValue)}, base=${JSON.stringify(baseValue)})`,
        );
      }
    }

    expect(
      diverged,
      "fr formality overlay is a documented no-op: the fr base catalog already " +
        "uses vouvoiement, so every overlay pin MUST byte-equal its base value. " +
        "A diverged pin silently shadows the edited base value at merge time — " +
        "update the overlay pin to match the new base value (or deliberately " +
        "diverge only if the FR overlay stops being a no-op, and update this " +
        `test's rationale). Diverged pins: ${diverged.join(" | ")}.`,
    ).toEqual([]);
  });
});
