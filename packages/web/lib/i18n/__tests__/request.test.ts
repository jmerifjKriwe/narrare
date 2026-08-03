/**
 * i18n request config tests — locale resolution for next-intl.
 *
 * Tests the getRequestConfig callback in lib/i18n/request.ts:
 * 1. NEXT_LOCALE cookie wins when it holds a valid locale
 * 2. invalid cookie value falls back to requestLocale
 * 3. cookies() throwing (e.g. static generation) falls back to requestLocale
 * 4. no cookie + invalid requestLocale falls back to default ("en")
 * 5. no cookie + undefined requestLocale falls back to default ("en")
 * 6. requestLocale is used when no cookie is set
 * 7. all configured namespaces are loaded into messages
 *
 * The mock for getRequestConfig returns the callback unchanged so we can invoke
 * it directly with a controlled { requestLocale } argument.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

// next-intl/server: return the config callback unchanged so the default export
// of request.ts IS the callback we can call directly.
vi.mock("next-intl/server", () => ({
  getRequestConfig: (configFn: unknown) => configFn,
}));

// next/headers: mock cookies() — real implementation is async.
vi.mock("next/headers", () => ({ cookies: vi.fn() }));

import { cookies } from "next/headers";
import requestConfig from "@/lib/i18n/request";

const cookiesMock = vi.mocked(cookies);

// The callback signature: ({ requestLocale }) => Promise<{ locale, messages }>
type RequestConfig = (ctx: { requestLocale: Promise<string | undefined> }) => Promise<{
  locale: string;
  messages: Record<string, unknown>;
}>;

const getConfig = requestConfig as unknown as RequestConfig;

// biome-ignore lint/suspicious/noExplicitAny: mocking Next.js cookies internals — ReadonlyRequestCookies has many members; a partial structural stub is intentional and a full interface would couple the test to Next.js internals.
type AnyCookieJar = any;

function mockCookies(cookieMap: Record<string, string> = {}): void {
  const jar: AnyCookieJar = {
    get: (name: string) => (name in cookieMap ? { name, value: cookieMap[name] } : undefined),
    has: (name: string) => name in cookieMap,
    getAll: () => Object.entries(cookieMap).map(([name, value]) => ({ name, value })),
    [Symbol.iterator]: undefined,
    size: Object.keys(cookieMap).length,
    set: vi.fn(),
    delete: vi.fn(),
  };
  cookiesMock.mockResolvedValue(jar);
}

beforeEach(() => {
  vi.clearAllMocks();
  // Default: no NEXT_LOCALE cookie.
  mockCookies();
});

describe("i18n getRequestConfig — locale priority", () => {
  it("uses NEXT_LOCALE cookie when it holds a valid locale", async () => {
    mockCookies({ NEXT_LOCALE: "de" });

    const result = await getConfig({ requestLocale: Promise.resolve("fr") });

    expect(result.locale).toBe("de");
  });

  it("ignores an invalid cookie value and falls back to requestLocale", async () => {
    mockCookies({ NEXT_LOCALE: "es" });

    const result = await getConfig({ requestLocale: Promise.resolve("fr") });

    expect(result.locale).toBe("fr");
  });

  it("falls back to requestLocale when cookies() throws", async () => {
    cookiesMock.mockRejectedValue(new Error("not available"));

    const result = await getConfig({ requestLocale: Promise.resolve("de") });

    expect(result.locale).toBe("de");
  });

  it("falls back to default when no cookie and requestLocale is invalid", async () => {
    const result = await getConfig({ requestLocale: Promise.resolve("xx") });

    expect(result.locale).toBe("en");
  });

  it("falls back to default when requestLocale is undefined", async () => {
    const result = await getConfig({ requestLocale: Promise.resolve(undefined) });

    expect(result.locale).toBe("en");
  });

  it("uses requestLocale when no cookie is set", async () => {
    const result = await getConfig({ requestLocale: Promise.resolve("de") });

    expect(result.locale).toBe("de");
  });
});

describe("i18n getRequestConfig — message loading", () => {
  it("loads all configured namespaces for the resolved locale", async () => {
    const result = await getConfig({ requestLocale: Promise.resolve("en") });

    const expectedNamespaces = [
      "common",
      "auth",
      "wizard",
      "dashboard",
      "editor",
      "errors",
      "generation",
      "settings",
      "settings-ai",
      "settings-appearance",
      "studio",
      "analysis",
      "timeline",
    ];

    expect(result.locale).toBe("en");
    for (const ns of expectedNamespaces) {
      expect(result.messages[ns], `namespace "${ns}" should be loaded`).toBeDefined();
    }
  });

  it("loads messages for a non-default locale", async () => {
    const result = await getConfig({ requestLocale: Promise.resolve("de") });

    expect(result.locale).toBe("de");
    expect(result.messages.common).toBeDefined();
    expect(result.messages.editor).toBeDefined();
  });
});
