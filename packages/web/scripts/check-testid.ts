/**
 * Component Marker Gate — data-testid / aria-label checker
 *
 * Scans TSX files for interactive elements (buttons, inputs, selects,
 * action links, role="button") that lack a `data-testid` or `aria-label`
 * attribute. Helps enforce E2E test stability.
 *
 * Usage:
 *   npx tsx scripts/check-testid.ts [options]
 *
 * Options:
 *   --dir <path>   Scan directory (default: src/components + src/app)
 *   --strict       Also check components/ui/ primitives
 *   --json         JSON output
 *   --fail         Exit 1 if any markers are missing
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface MarkerViolation {
  file: string;
  line: number;
  column: number;
  elementType: string;
  snippet: string;
}

interface FileResult {
  file: string;
  violations: MarkerViolation[];
}

interface ScanResult {
  filesChecked: number;
  filesWithViolations: number;
  totalViolations: number;
  results: FileResult[];
}

// ---------------------------------------------------------------------------
// CLI argument parsing
// ---------------------------------------------------------------------------

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(__dirname, "..");

const args = process.argv.slice(2);

function getArgValue(flag: string): string | undefined {
  const idx = args.indexOf(flag);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const hasFlag = (flag: string): boolean => args.includes(flag);

const customDir = getArgValue("--dir");
const strict = hasFlag("--strict");
const jsonOutput = hasFlag("--json");
const failOnError = hasFlag("--fail");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------

/** Directories to scan (relative to WEB_ROOT) */
const DEFAULT_SCAN_DIRS = ["components", "app"];

/** Patterns to always skip */
const SKIP_DIRS = new Set(["node_modules", ".next", "dist", "__tests__", "_archive_"]);

/** In non-strict mode, also skip these */
const LOOSE_SKIP_DIRS = new Set(["ui"]);

/** Interactive input types that need markers */
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

// ---------------------------------------------------------------------------
// Regex patterns for scanning
//
// We use line-by-line regex scanning rather than a full AST parse because:
//   1. Zero external dependencies beyond Node stdlib
//   2. TSX/JSX parsing is complex and ts-morph is heavy for a CI gate
//   3. The patterns we're looking for are simple enough to match reliably
//
// Trade-off: We may produce false positives for commented-out code or string
// literals that look like JSX. This is acceptable because:
//   - The script is advisory (warning gate, not a hard block by default)
//   - Developers can annotate exceptions with an inline comment
// ---------------------------------------------------------------------------

/** Matches opening JSX tags for elements we care about */
const RE_BUTTON_OPEN = /<button[\s>]/i;
const RE_INPUT_OPEN = /<input[\s/>]/i;
const RE_SELECT_OPEN = /<select[\s>]/i;
const RE_ANCHOR_OPEN = /<a[\s>]/i;
const RE_ROLE_BUTTON = /role\s*=\s*["']button["']/i;

/** Matches presence of marker attributes */
const RE_DATA_TESTID = /data-testid\s*=/i;
const RE_ARIA_LABEL = /aria-label\s*=/i;

/** Matches onClick handler */
const RE_ON_CLICK = /onClick\s*=/i;

/** Matches input type attribute */
const RE_TYPE_ATTR = /type\s*=\s*["']([^"']+)["']/i;

/** Matches @ts-nocheck directive */
const RE_TS_NOCHECK = /\/\/\s*@ts-nocheck/;

// ---------------------------------------------------------------------------
// File walking
// ---------------------------------------------------------------------------

function* walkTsxFiles(dir: string): Generator<string> {
  if (!fs.existsSync(dir)) return;

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);

    if (entry.isDirectory()) {
      if (SKIP_DIRS.has(entry.name)) continue;
      if (!strict && LOOSE_SKIP_DIRS.has(entry.name)) continue;
      yield* walkTsxFiles(fullPath);
    } else if (entry.isFile() && entry.name.endsWith(".tsx")) {
      yield fullPath;
    }
  }
}

// ---------------------------------------------------------------------------
// Extract the "snippet" — a short human-readable label from the element
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Check a single file for violations
// ---------------------------------------------------------------------------

function checkFile(filePath: string): MarkerViolation[] {
  const content = fs.readFileSync(filePath, "utf-8");

  // Skip files with @ts-nocheck
  if (RE_TS_NOCHECK.test(content)) return [];

  const lines = content.split("\n");
  const violations: MarkerViolation[] = [];

  // We need to handle multi-line JSX elements — collect the full element
  // starting from the opening tag. For simplicity, we check the opening tag
  // line plus a small lookahead for attributes on the next few lines.
  const LOOKAHEAD = 3;

  for (let lineIdx = 0; lineIdx < lines.length; lineIdx++) {
    const line = lines[lineIdx];

    // Build a chunk that includes the opening tag + following lines for
    // attribute checking (attributes may be on the next line)
    const chunkEnd = Math.min(lineIdx + 1 + LOOKAHEAD, lines.length);
    const chunk = lines.slice(lineIdx, chunkEnd).join("\n");

    const violationsOnLine: Array<{
      type: string;
      check: boolean;
      needsOnClick?: boolean;
    }> = [];

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
        const col = colMatch ? colMatch.index! + 1 : 1;

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

// ---------------------------------------------------------------------------
// Main scan
// ---------------------------------------------------------------------------

function scan(): ScanResult {
  const scanDirs = customDir ? [customDir] : DEFAULT_SCAN_DIRS;

  const allFiles: string[] = [];
  for (const dir of scanDirs) {
    const absDir = path.isAbsolute(dir) ? dir : path.resolve(WEB_ROOT, dir);
    for (const file of walkTsxFiles(absDir)) {
      allFiles.push(file);
    }
  }

  const results: FileResult[] = [];
  let totalViolations = 0;

  for (const file of allFiles) {
    const violations = checkFile(file);
    const relativePath = path.relative(WEB_ROOT, file);

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

// ---------------------------------------------------------------------------
// Output formatting
// ---------------------------------------------------------------------------

function formatHuman(scanResult: ScanResult): string {
  const lines: string[] = [];

  lines.push("");
  lines.push("COMPONENT MARKER CHECK");
  lines.push("======================");
  lines.push("");

  const filesWithViolations = scanResult.results.filter((r) => r.violations.length > 0);
  const cleanFiles = scanResult.results.filter((r) => r.violations.length === 0);

  // Show files with violations
  for (const fileResult of filesWithViolations) {
    lines.push(`\u26A0\uFE0F  ${fileResult.file}`);
    for (const v of fileResult.violations) {
      lines.push(
        `    Line ${v.line}: ${v.elementType} without data-testid or aria-label: "${v.snippet}"`,
      );
    }
    lines.push("");
  }

  // Show clean files (compact)
  for (const fileResult of cleanFiles) {
    lines.push(`\u2705 ${fileResult.file} \u2014 all interactive elements have markers`);
  }

  lines.push("");
  lines.push(
    `Summary: ${scanResult.filesChecked} files checked, ` +
      `${scanResult.filesWithViolations} files with missing markers, ` +
      `${scanResult.totalViolations} interactive elements uncovered`,
  );
  lines.push("");

  return lines.join("\n");
}

function formatJson(scanResult: ScanResult): string {
  return JSON.stringify(scanResult, null, 2);
}

// ---------------------------------------------------------------------------
// Entry point
// ---------------------------------------------------------------------------

const scanResult = scan();

if (jsonOutput) {
  console.log(formatJson(scanResult));
} else {
  console.log(formatHuman(scanResult));
}

if (scanResult.totalViolations > 0 && failOnError) {
  console.error(
    "\n\x1b[31m\u274C Component marker check failed: " +
      `${scanResult.totalViolations} interactive element(s) missing data-testid or aria-label.\x1b[0m\n`,
  );
  process.exit(1);
}

if (scanResult.totalViolations === 0) {
  console.log(
    "\x1b[32m\u2705 All interactive elements have data-testid or aria-label markers.\x1b[0m",
  );
}

process.exit(0);
