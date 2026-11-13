import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// The shell half of the @shell alias: capabilities under
// app/capabilities/*/web import shell code as @shell/lib/…, and the alias
// must resolve identically here (dev and build) and in typecheck
// (web/tsconfig.json paths). It points one way only — a capability imports
// the shell, never another capability.
const shell = fileURLToPath(new URL(".", import.meta.url));

// The ports are configuration on both sides (#621): app/kernel/testing/stack.py
// forwards its environment to `pnpm dev`, so the E2E stack and this dev server
// share NARRE_E2E_API_PORT / NARRE_E2E_WEB_PORT. Unset means 3100/8000.
const webPort = Number(process.env.NARRE_E2E_WEB_PORT ?? "3100");
const apiPort = Number(process.env.NARRE_E2E_API_PORT ?? "8000");

// Vite answers transformed modules with Cache-Control: no-cache, so a hard
// navigation revalidates the whole unbundled graph with 304s. Chromium loses
// cached module bodies once enough of those accumulate — the writer's-day E2E
// sweep, 24 hard navigations in one context, was exactly that shape — and the
// page never renders (#634). The E2E stack sets this flag so its browser never
// revalidates; `just dev-web` leaves it unset and keeps Vite's fast reloads.
const e2eNoHttpCache = process.env.NARRE_E2E_NO_HTTP_CACHE === "1";

// One origin in the browser, as before: /api is forwarded to the FastAPI
// process. In production FastAPI serves the built files itself, so this proxy
// exists only while developing.
export default defineConfig({
  // Per-port cache dir: two Vite instances on different worktrees (different
  // ports) must not share one optimise-deps cache, or they corrupt it.
  cacheDir: `node_modules/.vite-${webPort}`,
  plugins: [react()],
  // Component tests live beside the components they drive, in the capability
  // folders outside web/; the default include (this directory only) would
  // never collect them. The jsdom environment stays a per-file decision —
  // the docblock in each test file — so lib tests keep node semantics.
  test: {
    include: [
      "**/*.{test,spec}.?(c|m)[jt]s?(x)",
      "../app/capabilities/*/web/**/*.{test,spec}.?(c|m)[jt]s?(x)",
    ],
  },
  resolve: {
    alias: {
      "@shell": shell,
    },
  },
  server: {
    // Bind to IPv4 localhost explicitly: in CI (and on some hosts) `localhost`
    // resolves to ::1 (IPv6) only, so the E2E stack's http://127.0.0.1 web
    // probe would never reach a server bound to `localhost`.
    host: "127.0.0.1",
    // strictPort: a busy chosen port must still fail loudly. Silently moving
    // to +1 would let the E2E suite test a different process than the one it
    // started.
    port: webPort,
    strictPort: true,
    proxy: { "/api": `http://127.0.0.1:${apiPort}` },
    // No-store while the E2E stack runs: the browser must never revalidate the
    // dev graph (see the flag's comment above).
    ...(e2eNoHttpCache ? { headers: { "Cache-Control": "no-store" } } : {}),
  },
});
