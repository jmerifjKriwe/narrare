/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";
import { vi } from "vitest";
import { server } from "./mocks/server";

// Mock styled-jsx (Next.js CSS-in-JS) for test environment
vi.mock("styled-jsx", () => ({
  style: ({ children }: { children: React.ReactNode }) => children,
}));

// ---------------------------------------------------------------------------
// Zustand Store Mocks - NOT IMPLEMENTED
// ---------------------------------------------------------------------------
// NOTE: Global zustand store mocks are NOT implemented because:
// 1. The stores (editorStore, wizardStore, themeStore, authStore) have no
//    problematic top-level code - they only define state via create().
// 2. Some tests need the real store (e.g., wizard.test.tsx uses setState).
// 3. The actual failure in tests is missing QueryClientProvider, not stores.
//
// If a specific component fails due to store access at module load time,
// add a targeted mock in that component's test file.
// See: docs/development/testing-standards.md for guidance.

// ---------------------------------------------------------------------------
// next-intl Mock (centralized)
// ---------------------------------------------------------------------------
// All tests use useTranslations() — this global mock ensures consistency.
// Individual test mocks can still override if needed.
vi.mock("next-intl", () => ({
  useTranslations: () => (key: string, params?: Record<string, unknown>) => {
    if (params) {
      return Object.entries(params).reduce((str, [k, v]) => str.replace(`{${k}}`, String(v)), key);
    }
    return key;
  },
  useLocale: () => "en",
  useNow: () => new Date("2024-01-01"),
  useTimeZone: () => "UTC",
}));

// Establish API mocking before all tests
beforeAll(() => server.listen({ onUnhandledRequest: "bypass" }));

// Reset any request handlers that are declared during the tests
afterEach(() => server.resetHandlers());

// Clean up after the tests are finished
afterAll(() => server.close());
