import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// One origin in the browser, as before: /api is forwarded to the FastAPI
// process. In production FastAPI serves the built files itself, so this proxy
// exists only while developing.
export default defineConfig({
  plugins: [react()],
  server: {
    // Bind to IPv4 localhost explicitly: in CI (and on some hosts) `localhost`
    // resolves to ::1 (IPv6) only, so the E2E stack's http://127.0.0.1:3100
    // probe would never reach a server bound to `localhost`.
    host: "127.0.0.1",
    // strictPort: a busy 3100 must fail loudly. Silently moving to 3101 would
    // let the E2E suite test a different process than the one it started.
    port: 3100,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
