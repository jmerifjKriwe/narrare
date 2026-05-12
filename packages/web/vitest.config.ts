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
    },
  },
  resolve: {
    alias: {
      "@": resolve(__dirname, "."),
    },
  },
});
