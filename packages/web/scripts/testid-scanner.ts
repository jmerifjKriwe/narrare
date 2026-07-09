/**
 * Scanning engine for the component-marker gate.
 *
 * Extracted from check-testid.ts to comply with RULE-04 ("split before you
 * squeeze"). Owns the TSX line-scanner, interactive-element detection, and
 * per-directory aggregation. The CLI entry (check-testid.ts) imports scan() +
 * aggregateByDir(); the ratchet baseline lives in testid-baseline.ts.
 *
 * We use line-by-line regex scanning rather than a full AST parse because:
 *   1. Zero external dependencies beyond Node stdlib.
 *   2. TSX/JSX parsing is complex and ts-morph is heavy for a CI gate.
 *   3. The patterns we look for are simple enough to match reliably.
 *
 * Trade-off: false positives are possible for commented-out code or string
 * literals that look like JSX. This is acceptable because the gate is advisory
 * by default, and false positives can be suppressed with the inline
 * `check-testid:ok` annotation (see ANNOTATION_OK below).
 */

import * as fs from "node:fs";
import * as path from "node:path";

// ── Types ────────────────────────────────────────────────────────────────

export interface MarkerViolation {
  file: string;
  line: number;
  column: number;
  elementType: string;
  snippet: string;
}

export interface FileResult {
  file: string;
  violations: MarkerViolation[];
}

export interface ScanResult {
  filesChecked: number;
  filesWithViolations: number;
  totalViolations: number;
  results: FileResult[];
}

/** Options for scan(); decouples the engine from CLI globals. */
export interface ScanOptions {
  /** Repository web root (scan dirs are resolved against this). */
  webRoot: string;
  /** When true, also scan components/ui/ primitives. */
  strict: boolean;
  /** Override scan directories (relative to webRoot or absolute). */
  customDir?: string;
}

// ── Configuration ────────────────────────────────────────────────────────

/** Directories to scan (relative to webRoot). */
const DEFAULT_SCAN_DIRS = ["components", "app"];

/** Directory names to always skip. */
const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "__tests__", "_archive_"]);

/** In non-strict mode, also skip these. */
const LOOSE_SKIP_DIRS = new Set(["ui"]);

/** Interactive input types that need markers. */
const INTERACTIVE_INPUT_TYPES = new Set([
  "text",
  "email",
  "password",
  "search",
  "tel",
  "url",
  "number",
  "date",
  "time",
  "datetime-local",
  "month",
  "week",
]);

// ── Regex patterns ───────────────────────────────────────────────────────

/** Matches opening JSX tags for elements we care about. */
const RE_BUTTON_OPEN = /<button[\s>]/i;
const RE_INPUT_OPEN = /<input[\s/>]/i;
const RE_SELECT_OPEN = /<select[\s>]/i;
const RE_ANCHOR_OPEN = /<a[\s>]/i;
const RE_ROLE_BUTTON = /role\s*=\s*["']button["']/i;

/** Matches presence of marker attributes. */
const RE_DATA_TESTID = /data-testid\s*=/i;
const RE_ARIA_LABEL = /aria-label\s*=/i;

/** Matches onClick handler. */
const RE_ON_CLICK = /onClick\s*=/i;

/** Matches input type attribute. */
const RE_TYPE_ATTR = /type\s*=\s*["']([^"']+)["']/i;

/** Matches @ts-nocheck directive. */
const RE_TS_NOCHECK = /\/\/\s*@ts-nocheck/;

/**
 * Inline suppression token. Any source line containing this literal token (in
 * any comment syntax) suppresses violations detected on that same line. See
 * the check-testid.ts header docblock for usage and rationale.
 */
export const ANNOTATION_OK = "check-testid:ok";

// ── File walking ─────────────────────────────────────────────────────────

function* walkTsxFiles(dir: string, strict: boolean): Generator<string> {
  if (!fs.existsSync(dir)) return;

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      if (!strict && LOOSE_SKIP_DIRS.has(entry.name)) continue;
      yield* walkTsxFiles(fullPath, strict);
    } else if (entry.isFile() && entry.name.endsWith(".tsx")) {
      yield fullPath;
    }
  }
}

// ── Snippet extraction ───────────────────────────────────────────────────

/** Extract a short human-readable label for a detected element. */
function extractSnippet(line: string, elementType: string): string {
  // Try to find the text content hint between > and <
  const textMatch = line.match(/>\s*([^<]{1,60}?)\s*</);
  if (textMatch?.[1].trim()) {
    return textMatch[1].trim();
  }

  // Try to extract label or title attribute
  const labelMatch = line.match(/(?:label|title|placeholder)\s*=\s*["']([^"']+)["']/i);
  if (labelMatch) {
    return labelMatch[1];
  }

  // Try className hint
  const classMatch = line.match(/className\s*=\s*["']([^"']+)["']/i);
  if (classMatch) {
    return `${elementType} (${classMatch[1].slice(0, 40)})`;
  }

  return elementType;
}

// ── Per-file check ───────────────────────────────────────────────────────

/** Check a single file for marker violations. */
function checkFile(filePath: string): MarkerViolation[] {
  const content = fs.readFileSync(filePath, "utf-8");

  // Skip files with @ts-nocheck
  if (RE_TS_NOCHECK.test(content)) return [];

  const lines = content.split("\n");
  const violations: MarkerViolation[] = [];

  // Handle multi-line JSX elements: check the opening tag line plus a small
  // lookahead for attributes that may sit on following lines.
  const LOOKAHEAD = 8;

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const line = lines[lineIdx];

    // Inline annotation: a `check-testid:ok` token on this line suppresses
    // any violation detected here (false-positive escape hatch).
    if (line.includes(ANNOTATION_OK)) continue;

    // Build a chunk that includes the opening tag + following lines for
    // attribute checking (attributes may be on the next line)
    const chunkEnd = Math.min(lineIdx + 1 + LOOKAHEAD, lines.length);
    const chunk = lines.slice(lineIdx, chunkEnd).join("\n");

    const violationsOnLine: Array<{ type: string; check: boolean }> = [];

    // 1. <button> elements
    if (RE_BUTTON_OPEN.test(line)) {
      violationsOnLine.push({ type: "<button>", check: true });
    }

    // 2. <input> elements (text-like types only)
    if (RE_INPUT_OPEN.test(line)) {
      const typeMatch = chunk.match(RE_TYPE_ATTR);
      const inputType = typeMatch ? typeMatch[1].toLowerCase() : "text"; // default is text
      if (INTERACTIVE_INPUT_TYPES.has(inputType)) {
        violationsOnLine.push({ type: `<input type="${inputType}">`, check: true });
      }
      // Hidden, checkbox, radio, file, range, color, submit, reset, image, button inputs
      // are excluded — they have different UX patterns
    }

    // 3. <select> elements
    if (RE_SELECT_OPEN.test(line)) {
      violationsOnLine.push({ type: "<select>", check: true });
    }

    // 4. <a> elements with onClick (not plain navigation links)
    if (RE_ANCHOR_OPEN.test(line) && RE_ON_CLICK.test(chunk)) {
      violationsOnLine.push({ type: '<a onClick="...">', check: true });
    }

    // 5. Elements with role="button"
    if (RE_ROLE_BUTTON.test(line) && !RE_BUTTON_OPEN.test(line)) {
      violationsOnLine.push({ type: 'role="button"', check: true });
    }

    // Check each detected interactive element for markers
    for (const v of violationsOnLine) {
      if (!v.check) continue;

      const hasTestId = RE_DATA_TESTID.test(chunk);
      const hasAriaLabel = RE_ARIA_LABEL.test(chunk);

      if (!hasTestId && !hasAriaLabel) {
        const snippet = extractSnippet(line, v.type);
        // Calculate column: find the position of the tag
        const tagPattern =
          v.type === "<button>"
            ? /<button/i
            : v.type.startsWith("<input")
              ? /<input/i
              : v.type === "<select>"
                ? /<select/i
                : v.type.startsWith("<a")
                  ? /<a[\s>]/i
                  : /role\s*=\s*["']button["']/i;

        const colMatch = line.match(tagPattern);
        const col = colMatch ? (colMatch.index ?? 0) + 1 : 1;

        violations.push({
          file: "",
          line: lineIdx + 1,
          column: col,
          elementType: v.type,
          snippet,
        });
      }
    }
  }

  return violations;
}

// ── Main scan ────────────────────────────────────────────────────────────

/** Walk the configured scan dirs and return per-file violation results. */
export function scan(opts: ScanOptions): ScanResult {
  const scanDirs = opts.customDir ? [opts.customDir] : DEFAULT_SCAN_DIRS;

  const allFiles: string[] = [];
  for (const dir of scanDirs) {
    const absDir = path.isAbsolute(dir) ? dir : path.resolve(opts.webRoot, dir);
    for (const file of walkTsxFiles(absDir, opts.strict)) {
      allFiles.push(file);
    }
  }

  const results: FileResult[] = [];
  let totalViolations = 0;

  for (const file of allFiles) {
    const violations = checkFile(file);
    const relativePath = path.relative(opts.webRoot, file);

    if (violations.length > 0) {
      for (const v of violations) {
        v.file = relativePath;
      }
      totalViolations += violations.length;
      results.push({ file: relativePath, violations });
    } else {
      results.push({ file: relativePath, violations: [] });
    }
  }

  return {
    filesChecked: allFiles.length,
    filesWithViolations: results.filter((r) => r.violations.length > 0).length,
    totalViolations,
    results,
  };
}

// ── Aggregation ──────────────────────────────────────────────────────────

/** Normalize OS-specific separators to POSIX `/` for stable baseline keys. */
function toPosixPath(p: string): string {
  return p.split(path.sep).join("/");
}

/**
 * Aggregate per-file violations into per-directory counts (relative to
 * webRoot, POSIX separators). Only directories with >=1 violation are
 * included — clean dirs have nothing to ratchet (see testid-baseline.ts).
 */
export function aggregateByDir(results: FileResult[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const fileResult of results) {
    if (fileResult.violations.length === 0) continue;
    const dir = toPosixPath(path.dirname(fileResult.file));
    counts[dir] = (counts[dir] ?? 0) + fileResult.violations.length;
  }
  return counts;
}
