/**
 * Ratchet baseline support for the component-marker gate.
 *
 * Extracted from check-testid.ts to comply with RULE-04 ("split before you
 * squeeze — modularity over minification"). This module owns baseline I/O and
 * the ratchet comparison; check-testid.ts owns scanning + the CLI surface.
 *
 * Mirrors the ratchet CLI ergonomics of scripts/check_module_coverage.py and
 * scripts/_coverage_model.py:
 *
 *   --update-baseline <file>    capture current strict-scan counts as baseline
 *   --ratchet-baseline <file>   fail (with --fail) only on growth vs baseline
 *
 * ── Baseline file (JSON), co-located with the tool ───────────────────────
 *
 *   {
 *     "_comment": "Ratcheted component-marker baseline. ...",
 *     "updated": "2026-07-09",
 *     "mode": "strict",
 *     "counts": { "components/ui": 1, "components/studio": 2 },
 *     "total": 3
 *   }
 *
 * `counts` maps each directory (relative to WEB_ROOT, POSIX separators) that
 * currently has one or more violations to its violation count. Clean
 * directories are intentionally omitted: they have nothing to ratchet, and a
 * future violation there is caught by the NEW rule below.
 *
 * ── Ratchet rule (compareBaseline) ───────────────────────────────────────
 *
 *   current count > baseline count            → GROWTH  (FAIL in --fail mode)
 *   dir has violations but absent from counts → NEW     (FAIL in --fail mode)
 *   current count <= baseline count           → PASS
 *
 * The NEW rule is what protects against a reduced-scope `--update-baseline`:
 * if a previously-tracked violating directory is dropped from the baseline,
 * its still-present violations resurface as NEW on the next gate run and fail
 * it. Coverage's BaselineShrinkError (subset guard) is therefore unnecessary
 * here — coverage needs it because coverage is a continuous metric that
 * silently degrades, whereas testid violations are discrete and any untracked
 * violation is immediately classified NEW.
 */

import * as fs from "node:fs";

// ── Types ────────────────────────────────────────────────────────────────

/** On-disk baseline representation. */
export interface BaselineData {
  _comment: string;
  updated: string; // ISO date (YYYY-MM-DD)
  mode: string; // always "strict"
  counts: Record<string, number>;
  total: number;
}

/** Status of a single directory vs the baseline. */
export type DirStatus = "PASS" | "GROWTH" | "NEW";

/** One directory compared against the baseline. */
export interface DirComparison {
  dir: string;
  current: number;
  baseline: number;
  status: DirStatus;
}

/** Result of comparing current per-directory counts against a baseline. */
export interface RatchetReport {
  dirs: DirComparison[];
  currentTotal: number;
  baselineTotal: number;
  passed: number;
  failed: number;
  /** Baseline dirs that are clean now (improvement) — advisory, non-blocking. */
  resolved: string[];
}

// ── Constants ────────────────────────────────────────────────────────────

const BASELINE_COMMENT =
  "Ratcheted component-marker baseline. Updated via check-testid.ts --update-baseline. " +
  "Only directories with >=1 violation are tracked; growth or any new violating " +
  "directory fails the gate (see testid-baseline.ts).";

// ── Helpers ──────────────────────────────────────────────────────────────

function sumValues(counts: Record<string, number>): number {
  return Object.values(counts).reduce((acc, n) => acc + n, 0);
}

function sortByKey(record: Record<string, number>): Record<string, number> {
  const sorted: Record<string, number> = {};
  for (const key of Object.keys(record).sort()) sorted[key] = record[key];
  return sorted;
}

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

// ── Baseline I/O ─────────────────────────────────────────────────────────

/**
 * Load a baseline from *file*. Returns null if the file is missing or does not
 * have the expected shape (so callers can treat a missing baseline as "everything
 * is NEW" rather than crashing).
 */
export function loadBaseline(file: string): BaselineData | null {
  let raw: string;
  try {
    raw = fs.readFileSync(file, "utf-8");
  } catch {
    return null;
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }

  if (typeof parsed !== "object" || parsed === null) return null;
  const obj = parsed as Record<string, unknown>;

  const rawCounts = obj.counts;
  if (typeof rawCounts !== "object" || rawCounts === null) return null;

  const counts: Record<string, number> = {};
  for (const [dir, value] of Object.entries(rawCounts as Record<string, unknown>)) {
    if (typeof value === "number" && Number.isFinite(value)) {
      counts[dir] = Math.trunc(value);
    }
  }

  return {
    _comment: typeof obj._comment === "string" ? obj._comment : BASELINE_COMMENT,
    updated: typeof obj.updated === "string" ? obj.updated : "",
    mode: typeof obj.mode === "string" ? obj.mode : "strict",
    counts,
    total: typeof obj.total === "number" ? obj.total : sumValues(counts),
  };
}

/**
 * Persist *counts* as the new baseline at *file*.
 *
 * Only directories with >=1 violation should be present in *counts* (the
 * scanner is responsible for omitting clean dirs). The file is written with a
 * trailing newline and sorted keys for deterministic diffs.
 */
export function saveBaseline(file: string, counts: Record<string, number>): BaselineData {
  const data: BaselineData = {
    _comment: BASELINE_COMMENT,
    updated: todayIso(),
    mode: "strict",
    counts: sortByKey(counts),
    total: sumValues(counts),
  };
  fs.writeFileSync(file, `${JSON.stringify(data, null, 2)}\n`, "utf-8");
  return data;
}

// ── Comparison ───────────────────────────────────────────────────────────

/**
 * Compare current per-directory violation counts against *baseline*.
 *
 * Failure conditions (counted toward `failed`):
 *   - GROWTH: current count exceeds the baseline count for that directory.
 *   - NEW:    the directory has violations but is absent from the baseline.
 *
 * Baseline directories that are no longer violating are returned in `resolved`
 * (an improvement — advisory only, never a failure).
 */
export function compareBaseline(
  current: Record<string, number>,
  baseline: BaselineData | null,
): RatchetReport {
  const baselineCounts: Record<string, number> = baseline?.counts ?? {};
  const dirs: DirComparison[] = [];
  let passed = 0;
  let failed = 0;

  for (const dir of Object.keys(current).sort()) {
    const currentCount = current[dir] ?? 0;
    if (currentCount === 0) continue; // clean dir — not tracked, nothing to report

    const baselineCount = baselineCounts[dir];
    if (baselineCount === undefined) {
      dirs.push({ dir, current: currentCount, baseline: 0, status: "NEW" });
      failed += 1;
    } else if (currentCount > baselineCount) {
      dirs.push({ dir, current: currentCount, baseline: baselineCount, status: "GROWTH" });
      failed += 1;
    } else {
      dirs.push({ dir, current: currentCount, baseline: baselineCount, status: "PASS" });
      passed += 1;
    }
  }

  const resolved = Object.keys(baselineCounts)
    .filter((dir) => (current[dir] ?? 0) === 0)
    .sort();

  return {
    dirs,
    currentTotal: sumValues(current),
    baselineTotal: baseline?.total ?? sumValues(baselineCounts),
    passed,
    failed,
    resolved,
  };
}

/**
 * Format a ratchet comparison as a compact human-readable block. Mirrors the
 * summary-line style of scripts/check_module_coverage.py.
 */
export function formatRatchetReport(report: RatchetReport, baselinePath: string): string {
  const lines: string[] = [];
  lines.push("");
  lines.push("RATCHET (component markers vs baseline)");
  lines.push("=======================================");

  for (const d of report.dirs) {
    const tag = d.status === "PASS" ? " ok " : d.status === "GROWTH" ? "GROW" : "NEW ";
    const comparison =
      d.status === "NEW" ? "(not in baseline)" : `${d.current} now vs ${d.baseline} baseline`;
    lines.push(`  [${tag}] ${d.dir}: ${comparison}`);
  }

  lines.push("");
  lines.push(
    `Summary: ${report.passed} within ratchet, ${report.failed} regressed/new ` +
      `(total ${report.currentTotal} now vs ${report.baselineTotal} baseline; ` +
      `baseline: ${baselinePath})`,
  );

  if (report.resolved.length > 0) {
    lines.push(
      `Resolved: ${report.resolved.length} baseline dir(s) now clean ` +
        `(${report.resolved.slice(0, 5).join(", ")}` +
        `${report.resolved.length > 5 ? `, +${report.resolved.length - 5} more` : ""}). ` +
        `Run --update-baseline to lock in the improvement.`,
    );
  }

  lines.push("");
  return lines.join("\n");
}
