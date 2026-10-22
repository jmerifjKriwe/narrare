import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// One origin in the browser, as before: /api is forwarded to the FastAPI
// process. In production FastAPI serves the built files itself, so this proxy
// exists only while developing.
export default defineConfig({
  plugins: [react()],
  server: {
    // strictPort: a busy 3100 must fail loudly. Silently moving to 3101 would
    // let the E2E suite test a different process than the one it started.
    port: 3100,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
