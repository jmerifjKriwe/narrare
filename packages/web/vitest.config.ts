import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    // happy-dom: 3-5x faster DOM setup than jsdom (see ADR-optimization)
    environment: "happy-dom",
    setupFiles: ["./setupTests.ts"],
    // Single-project config: test.projects was evaluated (2026-06-10) but
    // caused ~17% runtime regression (112s → 131s) due to duplicate
    // environment setup overhead across parallel projects. See
    // docs/architecture/INCOMPLETE-FEATURES-PLAN.md for details.
    include: ["**/*.test.{ts,tsx}"],
    globals: true,
    testTimeout: 30_000, // default 5_000 → 30_000 (prevents premature timeout)
    slowTestThreshold: 2_000, // Warn when individual test takes >2s
    // Parallelize across CPU cores via worker threads (faster than forks
    // due to shared memory; safe because tests use isolated environments)
    pool: "threads",
    maxWorkers: 6,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["components/**", "lib/**"],
      exclude: ["**/*.d.ts", "**/node_modules/**", "types/**", "**/*.md"],
      thresholds: {
        // Overall thresholds
        global: {
          lines: 25,
          functions: 25,
          branches: 25,
          statements: 25,
        },
        // lib/ directory: stricter requirements
        "lib/**": {
          lines: 80,
          functions: 80,
          branches: 80,
          statements: 80,
        },
        // components/ directory: UI components harder to test.
        // Ratcheted 2026-07 from 15% → 65% after adding controller-hook and
        // EditorToolbar tests (review §1/§5 untested hotspots). Measured at
        // this step: lines 77.1 / statements 75.3 / functions 69.9 / branches
        // 70.6 — 65% sits ~5 pts below the lowest metric (functions) as a
        // safety margin against churn. Next ratchet step toward the eventual
        // ~80% target: keep covering high-degree, low-coverage components
        // (KnowledgeGraphView, ChatPanel, editor-view shells) and raise in
        // ~5-pt increments. Do NOT set above the lowest measured metric.
        "components/**": {
          lines: 65,
          functions: 65,
          branches: 65,
          statements: 65,
        },
      },
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "."),
    },
  },
});
