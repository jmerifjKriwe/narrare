/**
 * VRT Mock Contract Gate — ADR-059 BINDING enforcement (CLI entry).
 *
 * Scans every `packages/web/tests/screenshots/*.spec.ts` for the three
 * Mock Contract requirements defined in ADR-059 §"Mock Contract (BINDING)":
 *
 *   1. Catch-all route: `page.route` with the API-v1 wildcard glob (matches
 *      every `/api/v1/` endpoint) — registered FIRST so Playwright's
 *      reverse-order matching lets specific mocks win.
 *      Catches unmocked calls → prevents ECONNREFUSED→HTTP500→stale-baseline
 *      (the CI-Run-30758014183 lesson documented in ADR-059).
 *   2. `expect.poll` guard: `expect.poll(() => unmockedApiCalls).toEqual([])`
 *      before the screenshot — polled, not one-shot, so late-firing requests
 *      are still caught.
 *   3. `timezoneId` in `test.use({ … })` — prevents Intl.DateTimeFormat
 *      baseline drift across CI-runner local times.
 *
 * A spec missing ANY of these three fails the gate (exit 1). This is a
 * hard-enforce gate — ADR-059 says BINDING, not "ratchet toward compliance".
 * There is no advisory mode and no `--fail` flag: violations always exit 1.
 *
 * Architecture (follows the check-testid.ts precedent):
 *   - Line-by-line / full-content regex scanning, NOT a full TS AST parse.
 *     Rationale (same as testid-scanner.ts): zero external dependencies
 *     beyond Node stdlib, and the three patterns we look for are specific
 *     enough to match reliably without a parser. An AST approach would add
 *     a `typescript` dependency for no gain — the API-v1 catch-all glob,
 *     the `expect.poll(` call, and the `timezoneId:` identifier are
 *     unambiguous tokens that do not appear outside their intended context.
 *   - Single file (no scanner/baseline split): there is no ratchet or
 *     baseline logic — the gate is a binary pass/fail. RULE-04 says "split
 *     before you squeeze"; nothing here is large enough to squeeze.
 *
 * Usage:
 *   npx tsx scripts/check-vrt-mock-contract.ts [options]
 *
 * Options:
 *   --dir <path>   Spec directory to scan (default: tests/screenshots,
 *                  relative to packages/web/ or absolute).
 *   --json         JSON output (machine-readable, for CI tooling).
 *
 * Exit codes:
 *   0   all specs satisfy the Mock Contract
 *   1   one or more specs violate the Mock Contract
 *
 * Reference implementation (all 3 requirements satisfied):
 *   tests/screenshots/adaptive.spec.ts
 *
 * See:
 *   docs/architecture/decisions/ADR-059-vrt-and-design-system-strategy.md
 *   packages/web/tests/screenshots/README.md  (minimal boilerplate)
 */

import * as fs from "node:fs";
import * as path from "node:path";
import { fileURLToPath } from "node:url";

// ── Types ────────────────────────────────────────────────────────────────

/** A single Mock Contract requirement (id + matcher + human guidance). */
interface Requirement {
  readonly id: string;
  readonly description: string;
  /** Multi-line fix hint shown in the violation report. */
  readonly hint: string;
  /** Returns true if *content* satisfies this requirement. */
  readonly check: (content: string) => boolean;
}

/** Per-file scan result. */
interface FileResult {
  file: string;
  compliant: boolean;
  /** IDs of requirements that are missing (empty when compliant). */
  missing: string[];
}

/** Aggregate scan result. */
interface ContractResult {
  filesChecked: number;
  filesWithViolations: number;
  totalMissing: number;
  results: FileResult[];
}

// ── Paths & CLI argument parsing ─────────────────────────────────────────

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = path.resolve(__dirname, "..");
const DEFAULT_SPEC_DIR = "tests/screenshots";

const args = process.argv.slice(2);

function getArgValue(flag: string): string | undefined {
  const idx = args.indexOf(flag);
  if (idx === -1 || idx + 1 >= args.length) return undefined;
  return args[idx + 1];
}

const hasFlag = (flag: string): boolean => args.includes(flag);

const customDir = getArgValue("--dir");
const jsonOutput = hasFlag("--json");

// ── Requirements ─────────────────────────────────────────────────────────

/**
 * The three BINDING requirements from ADR-059 §"Mock Contract (BINDING)".
 *
 * Matching strategy (robustness vs fragility trade-off, same philosophy as
 * testid-scanner.ts): each check operates on the full file content using a
 * targeted pattern that is specific enough to avoid false positives:
 *
 *   - The API-v1 catch-all glob (a Playwright `page.route` pattern that
 *     matches every `/api/v1/` endpoint). This exact string has no other
 *     use; it does not appear in imports, types, or comments unless
 *     documenting the catch-all (and if documented, the route is
 *     almost certainly present).
 *   - `expect.poll(`  — Playwright's polling assertion API. The
 *     `expect` + `.poll` + `(` sequence is unambiguous.
 *   - `timezoneId:`   — a Playwright test-use property. The colon
 *     distinguishes a property assignment from a type reference.
 *
 * Ordering is NOT checked (the catch-all must be "registered FIRST" per
 * ADR-059, but wrong ordering is caught indirectly: if the catch-all is
 * registered last, it shadows every specific mock, every API call lands in
 * `unmockedApiCalls`, and the `expect.poll` guard fails with the full URL
 * list). Checking ordering via regex would be fragile for no additional
 * safety — the guard already catches the consequence.
 */
const REQUIREMENTS: readonly Requirement[] = [
  {
    id: "catch-all-route",
    description: 'Catch-all route `page.route("**/api/v1/**", …)` registered FIRST',
    hint: [
      'Add `await page.route("**/api/v1/**", async (route) => { … })` as the',
      "             FIRST `page.route(…)` call inside `test.beforeEach(…)`. Playwright",
      "             matches routes in reverse registration order — specific mocks",
      "             must be registered AFTER the catch-all to win. Record unmocked",
      "             URLs into an array (e.g. `unmockedApiCalls`).",
    ].join("\n"),
    check: (c) => c.includes("**/api/v1/**"),
  },
  {
    id: "expect-poll-guard",
    description: "`expect.poll(…)` guard before the screenshot",
    hint: [
      "Add `await expect.poll(() => unmockedApiCalls).toEqual([])` BEFORE",
      "             every `toHaveScreenshot(…)` call. Polled (not one-shot) so a",
      "             request that fires slightly later is still caught. See the",
      "             reference implementation in adaptive.spec.ts.",
    ].join("\n"),
    check: (c) => /expect\s*\.\s*poll\s*\(/.test(c),
  },
  {
    id: "timezone-id",
    description: '`timezoneId` in `test.use({ timezoneId: "UTC" })`',
    hint: [
      'Add `test.use({ timezoneId: "UTC" })` inside the `test.describe(…)`',
      "             block. Prevents Intl.DateTimeFormat baseline drift between CI",
      "             runners (UTC) and local machines (local timezone). Even if the",
      "             current component does not format dates, a future change might,",
      "             and pinning costs one line.",
    ].join("\n"),
    check: (c) => /timezoneId\s*:/.test(c),
  },
] as const;

const ADR_REF = "docs/architecture/decisions/ADR-059-vrt-and-design-system-strategy.md";
const REFERENCE_SPEC = "tests/screenshots/adaptive.spec.ts";

// ── File walking ─────────────────────────────────────────────────────────

/**
 * Yield every `*.spec.ts` file under *dir*, skipping `*-snapshots/`
 * directories (Playwright baseline images) and `node_modules`.
 *
 * Recursive so that future subdirectory layouts (e.g. grouping specs by
 * feature) are covered without needing to update this walker.
 */
function* walkSpecFiles(dir: string): Generator<string> {
  if (!fs.existsSync(dir)) return;
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name.endsWith("-snapshots")) {
        continue;
      }
      yield* walkSpecFiles(fullPath);
    } else if (entry.isFile() && entry.name.endsWith(".spec.ts")) {
      yield fullPath;
    }
  }
}

// ── Per-file check ───────────────────────────────────────────────────────

/** Return the IDs of requirements that *filePath* fails to satisfy. */
function checkSpec(filePath: string): string[] {
  const content = fs.readFileSync(filePath, "utf-8");
  const missing: string[] = [];
  for (const req of REQUIREMENTS) {
    if (!req.check(content)) missing.push(req.id);
  }
  return missing;
}

// ── Main scan ────────────────────────────────────────────────────────────

/** Scan *specDirAbs* and return per-file + aggregate contract results. */
function scan(specDirAbs: string): ContractResult {
  const results: FileResult[] = [];
  let filesChecked = 0;
  let filesWithViolations = 0;
  let totalMissing = 0;

  const allFiles = [...walkSpecFiles(specDirAbs)].sort();

  for (const file of allFiles) {
    filesChecked += 1;
    const missing = checkSpec(file);
    const relativePath = path.relative(WEB_ROOT, file);
    if (missing.length > 0) {
      filesWithViolations += 1;
      totalMissing += missing.length;
      results.push({ file: relativePath, compliant: false, missing });
    } else {
      results.push({ file: relativePath, compliant: true, missing: [] });
    }
  }

  return { filesChecked, filesWithViolations, totalMissing, results };
}

// ── Output formatting ────────────────────────────────────────────────────

function formatHuman(result: ContractResult): string {
  const lines: string[] = [];

  lines.push("");
  lines.push("VRT MOCK CONTRACT CHECK (ADR-059 BINDING)");
  lines.push("=========================================");
  lines.push("");

  for (const r of result.results) {
    if (r.compliant) {
      lines.push(`\u2705 ${r.file} \u2014 contract compliant`);
    } else {
      lines.push(`\u26A0\uFE0F  ${r.file}`);
      for (const id of r.missing) {
        const req = REQUIREMENTS.find((q) => q.id === id);
        if (!req) continue;
        lines.push(`    Missing: ${req.description}`);
        lines.push(`             ${req.hint}`);
      }
      lines.push("");
    }
  }

  lines.push(
    `Summary: ${result.filesChecked} spec(s) checked, ` +
      `${result.filesWithViolations} with violations, ` +
      `${result.totalMissing} requirement(s) missing`,
  );
  lines.push("");

  return lines.join("\n");
}

function formatJson(result: ContractResult): string {
  return JSON.stringify(result, null, 2);
}

// ── Entry point ──────────────────────────────────────────────────────────

const specDir = customDir
  ? path.isAbsolute(customDir)
    ? customDir
    : path.resolve(WEB_ROOT, customDir)
  : path.resolve(WEB_ROOT, DEFAULT_SPEC_DIR);

const result = scan(specDir);

if (jsonOutput) {
  console.log(formatJson(result));
} else {
  console.log(formatHuman(result));
}

if (result.filesWithViolations > 0) {
  console.error(
    `\n\x1b[31m\u274C VRT mock contract check failed: ${result.filesWithViolations} ` +
      `spec(s) violate ADR-059 Mock Contract (BINDING).\x1b[0m\n` +
      `   Reference implementation: ${REFERENCE_SPEC}\n` +
      `   See: ${ADR_REF}\n`,
  );
  process.exit(1);
}

console.log(
  `\x1b[32m\u2705 All ${result.filesChecked} VRT spec(s) satisfy the ADR-059 Mock Contract (BINDING).\x1b[0m`,
);
process.exit(0);
