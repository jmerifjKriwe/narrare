/**
 * Component Marker Gate — data-testid / aria-label checker (CLI entry).
 *
 * Scans TSX files for interactive elements (buttons, inputs, selects,
 * action links, role="button") that lack a `data-testid` or `aria-label`
 * attribute. Helps enforce E2E test stability.
 *
 * Architecture (RULE-04 split):
 *   - testid-scanner.ts   — the line-scanner + interactive-element detection
 *   - testid-baseline.ts  — ratchet baseline I/O + comparison
 *   - check-testid.ts     — this file: CLI parsing, output formatting, gate
 *                           orchestration
 *
 * Usage:
 *   npx tsx scripts/check-testid.ts [options]
 *
 * Options:
 *   --dir <path>                Scan directory (default: components + app)
 *   --strict                    Also check components/ui/ primitives
 *   --json                      JSON output (machine-readable)
 *   --fail                      Exit 1 if the gate fails (see modes below)
 *   --ratchet-baseline <file>   Ratchet mode: fail only on growth vs baseline.
 *                               Requires --strict. Without it, --fail is a
 *                               plain hard fail on any violation (back-compat).
 *   --update-baseline <file>    Write current strict-scan per-directory counts
 *                               as the new baseline, then exit 0.
 *
 * Modes (with --fail):
 *   --fail                                → hard fail on ANY violation
 *   --fail --ratchet-baseline <file>      → fail only on GROWTH or NEW violations
 *   --update-baseline <file>              → capture current state, never fails
 *
 * Inline annotation suppression:
 *   A source line containing the literal token `check-testid:ok` — in any
 *   comment syntax, such as a JSX comment or a `// check-testid:ok` line
 *   comment — suppresses every violation detected on that SAME line. Use
 *   sparingly for false positives; prefer adding a real `data-testid` /
 *   `aria-label`.
 */

import * as path from "node:path";
import { fileURLToPath } from "node:url";

import {
  compareBaseline,
  formatRatchetReport,
  loadBaseline,
  type RatchetReport,
  saveBaseline,
} from "./testid-baseline";
import { aggregateByDir, type ScanResult, scan } from "./testid-scanner";

// ---------------------------------------------------------------------------
// Paths & CLI argument parsing
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
const ratchetBaselinePath = getArgValue("--ratchet-baseline");
const updateBaselinePath = getArgValue("--update-baseline");

/**
 * Resolve a baseline path argument: absolute paths are used as-is, relative
 * paths are resolved against WEB_ROOT (so `scripts/testid_baselines.json`
 * works regardless of the current working directory).
 */
function resolveBaselinePath(p: string): string {
  return path.isAbsolute(p) ? p : path.resolve(WEB_ROOT, p);
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

const scanResult = scan({ webRoot: WEB_ROOT, strict, customDir });

// ── --update-baseline: capture current state and exit 0 ──────────────────
if (updateBaselinePath) {
  if (!strict) {
    console.error(
      "\x1b[31m\u274C --update-baseline requires --strict (the baseline must " +
        "reflect the strict scan that the gate enforces).\x1b[0m",
    );
    process.exit(2);
  }
  const counts = aggregateByDir(scanResult.results);
  const baselinePath = resolveBaselinePath(updateBaselinePath);
  const written = saveBaseline(baselinePath, counts);
  const dirCount = Object.keys(written.counts).length;
  console.log(
    `\x1b[32m\u2705 Baseline written to ${baselinePath}\x1b[0m ` +
      `(${dirCount} dir(s) tracked, ${written.total} total violation(s)).`,
  );
  process.exit(0);
}

// ── Normal scan output ───────────────────────────────────────────────────
if (jsonOutput) {
  console.log(formatJson(scanResult));
} else {
  console.log(formatHuman(scanResult));
}

// ── Ratchet comparison (--ratchet-baseline) ──────────────────────────────
let ratchetReport: RatchetReport | null = null;
if (ratchetBaselinePath) {
  if (!strict) {
    console.error(
      "\x1b[31m\u274C --ratchet-baseline requires --strict (the ratchet compares " +
        "against the strict scan).\x1b[0m",
    );
    process.exit(2);
  }
  const baselinePath = resolveBaselinePath(ratchetBaselinePath);
  const baseline = loadBaseline(baselinePath);
  const counts = aggregateByDir(scanResult.results);
  ratchetReport = compareBaseline(counts, baseline);
  if (!jsonOutput) {
    console.log(formatRatchetReport(ratchetReport, baselinePath));
  }
}

// ── Exit decision ────────────────────────────────────────────────────────
if (failOnError) {
  if (ratchetReport) {
    // Ratchet mode: fail only on growth / new violations.
    if (ratchetReport.failed > 0) {
      console.error(
        `\n\x1b[31m\u274C Component marker ratchet failed: ${ratchetReport.failed} ` +
          `dir(s) regressed or new (total ${ratchetReport.currentTotal} ` +
          `> ${ratchetReport.baselineTotal} baseline).\x1b[0m\n`,
      );
      process.exit(1);
    }
    if (ratchetReport.currentTotal > 0) {
      console.warn(
        `\n\x1b[33m\u26A0\uFE0F  Within ratchet: ${ratchetReport.currentTotal} violation(s) ` +
          `present but not growing (baseline ${ratchetReport.baselineTotal}). ` +
          `Fix or annotate them; run --update-baseline after reducing.\x1b[0m`,
      );
    } else {
      console.log(
        "\x1b[32m\u2705 All interactive elements have data-testid or aria-label markers.\x1b[0m",
      );
    }
  } else if (scanResult.totalViolations > 0) {
    // Back-compat hard-fail mode (no ratchet baseline).
    console.error(
      "\n\x1b[31m\u274C Component marker check failed: " +
        `${scanResult.totalViolations} interactive element(s) missing ` +
        `data-testid or aria-label.\x1b[0m\n`,
    );
    process.exit(1);
  } else {
    console.log(
      "\x1b[32m\u2705 All interactive elements have data-testid or aria-label markers.\x1b[0m",
    );
  }
} else if (scanResult.totalViolations === 0) {
  console.log(
    "\x1b[32m\u2705 All interactive elements have data-testid or aria-label markers.\x1b[0m",
  );
}

process.exit(0);
