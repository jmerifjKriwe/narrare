import { resolve } from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./setupTests.ts"],
    include: ["**/*.test.{ts,tsx}"],
    globals: true,
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "lcov"],
      include: ["components/**", "lib/**"],
      exclude: ["**/*.d.ts", "**/node_modules/**", "types/**"],
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
        // components/ directory: lower requirements (UI components harder to test)
        "components/**": {
          lines: 15,
          functions: 15,
          branches: 15,
          statements: 15,
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
