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
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const WEB_ROOT = resolve(__dirname, "..");

/** Recursively collect all .ts/.tsx file paths, skipping unwanted dirs. */
function collectSourceFiles(dir: string, files: string[] = []): string[] {
  const entries = readdirSync(dir);
  for (const entry of entries) {
    const fullPath = join(dir, entry);
    // Skip directories we don't want to scan
    if (entry === "node_modules" || entry === ".next" || entry === "__tests__") {
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
