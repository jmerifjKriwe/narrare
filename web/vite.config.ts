import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The shell half of the @shell alias: capabilities under
// app/capabilities/*/web import shell code as @shell/lib/…, and the alias
// must resolve identically here (dev and build) and in typecheck
// (web/tsconfig.json paths). It points one way only — a capability imports
// the shell, never another capability.
const shell = fileURLToPath(new URL(".", import.meta.url));

// One origin in the browser, as before: /api is forwarded to the FastAPI
// process. In production FastAPI serves the built files itself, so this proxy
// exists only while developing.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@shell": shell,
    },
  },
  server: {
    // strictPort: a busy 3100 must fail loudly. Silently moving to 3101 would
    // let the E2E suite test a different process than the one it started.
    port: 3100,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
