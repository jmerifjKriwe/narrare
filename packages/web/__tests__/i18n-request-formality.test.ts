/**
 * Loader-level behavior tests for the formality overlay seam in
 * `lib/i18n/request.ts` (Feature Spec I-Copy-001 — program item B closure).
 *
 * The neighbouring files already pin the other three seams:
 *   - `i18n-mergeOverlay.test.ts`       — the deep-merge helper itself
 *   - `i18n-namespace-registry.test.ts` — overlay governance (orphan/parity/no-en)
 *   - `formality-switcher.test.tsx`     — the UI control (cookie write + refresh)
 * This file pins the LOADER: NEXT_FORMALITY cookie → conditional deep-merge →
 * the message object next-intl receives. A second describe block pins the
 * locale-resolution fallback chain (requestLocale → default) that engages
 * whenever the NEXT_LOCALE cookie is absent or invalid.
 *
 * Test mechanics (empirically probed 2026-08-18): `next/headers` is mocked
 * with an in-memory cookie store; `next-intl/server`'s `getRequestConfig` is
 * mocked as an IDENTITY PASSTHROUGH — under happy-dom the package's browser
 * export condition resolves to its client shim, whose `getRequestConfig`
 * throws ("not supported in Client Components"). The real server-side
 * registration is next-intl plumbing, not loader logic, so passing the config
 * function through exercises 100 % of the loader's own code. The loader's
 * dynamic JSON imports from `packages/i18n/` resolve natively in vitest.
 *
 * RULE-02 boundary (by construction): the loader seam is UI-copy-only —
 * `formality` never leaves the message-merge layer.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

const cookieStore = new Map<string, string>();

vi.mock("next/headers", () => ({
  cookies: vi.fn(async () => ({
    get: (name: string) =>
      cookieStore.has(name) ? { value: cookieStore.get(name) as string } : undefined,
  })),
}));

vi.mock("next-intl/server", () => ({
  getRequestConfig: <T>(fn: T) => fn,
}));

import loadRequestConfigDefault from "@/lib/i18n/request";

type ResolvedConfig = { locale: string; messages: Record<string, unknown> };
type RequestConfigFn = (args: { requestLocale: Promise<string> }) => Promise<ResolvedConfig>;

const loadRequestConfig = loadRequestConfigDefault as unknown as RequestConfigFn;

function loadMessages(requestLocale: string): Promise<ResolvedConfig> {
  return loadRequestConfig({ requestLocale: Promise.resolve(requestLocale) });
}

/** Narrow one namespace out of the merged messages object. */
function ns(messages: Record<string, unknown>, namespace: string): Record<string, unknown> {
  return messages[namespace] as Record<string, unknown>;
}

describe("request.ts formality overlay seam (I-Copy-001)", () => {
  beforeEach(() => {
    cookieStore.clear();
  });

  it("de + NEXT_FORMALITY=formal serves the formal overlay value", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { locale, messages } = await loadMessages("de");
    expect(locale).toBe("de");
    // Overlay leaf (auth.displayNamePlaceholder: du→Sie form).
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir Sie nennen?");
    // A second, nested overlay leaf (wizard.step1.title).
    const wizardStep1 = ns(messages, "wizard").step1 as Record<string, unknown>;
    expect(wizardStep1.title).toBe("Ihr Projekt");
  });

  it("tone-neutral keys fall through to the base in the formal register", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { messages } = await loadMessages("de");
    // `common.save` is tone-neutral and deliberately NOT in the overlay.
    expect(ns(messages, "common").save).toBe("Speichern");
  });

  it("de + no NEXT_FORMALITY cookie defaults to the informal base", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    const { messages } = await loadMessages("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });

  it("de + NEXT_FORMALITY=informal keeps the informal base (explicit)", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "informal");
    const { messages } = await loadMessages("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });

  it("de + an undocumented NEXT_FORMALITY value falls back to informal", async () => {
    cookieStore.set("NEXT_LOCALE", "de");
    cookieStore.set("NEXT_FORMALITY", "FORMAL"); // case-sensitive: not honoured
    const { messages } = await loadMessages("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });

  it("en + NEXT_FORMALITY=formal is byte-identical to the en base (no overlay ever)", async () => {
    cookieStore.set("NEXT_LOCALE", "en");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { locale, messages } = await loadMessages("en");
    expect(locale).toBe("en");
    const baseAuth = (await import("../../i18n/messages/en/auth.json")).default;
    expect(messages.auth).toEqual(baseAuth);
  });

  it("fr + NEXT_FORMALITY=formal merges cleanly; FR overlay equals the base (documented no-op)", async () => {
    cookieStore.set("NEXT_LOCALE", "fr");
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { messages } = await loadMessages("fr");
    // The FR base catalog already uses vouvoiement; the parity-required
    // overlay's values are byte-equal to the base (forward-correct for a
    // future tutoiement base). The merge must be a clean no-op, never a crash.
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Comment devons-nous vous appeler ?");
  });
});

describe("request.ts locale resolution fallback (requestLocale path)", () => {
  // These tests never set NEXT_LOCALE, so the loader's step 2 (requestLocale
  // from URL routing / middleware) and step 3 (default locale) actually run —
  // the first describe block always short-circuits via the cookie.
  beforeEach(() => {
    cookieStore.clear();
  });

  it("no cookie + valid requestLocale=de resolves de and serves the de base", async () => {
    const { locale, messages } = await loadMessages("de");
    expect(locale).toBe("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });

  it("no cookie + valid requestLocale=de + formal still applies the overlay", async () => {
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { locale, messages } = await loadMessages("de");
    expect(locale).toBe("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir Sie nennen?");
  });

  it("no cookie + invalid requestLocale falls back to the default locale (en)", async () => {
    const { locale, messages } = await loadMessages("xx"); // not in routing.locales
    expect(locale).toBe("en");
    expect(ns(messages, "common").save).toBe("Save");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("How should we call you?");
  });

  it("no cookie + empty requestLocale falls back to the default locale (en)", async () => {
    const { locale, messages } = await loadMessages("");
    expect(locale).toBe("en");
    expect(ns(messages, "common").save).toBe("Save");
  });

  it("default-locale fallback (en) + formal never applies an overlay", async () => {
    cookieStore.set("NEXT_FORMALITY", "formal");
    const { locale, messages } = await loadMessages("xx");
    expect(locale).toBe("en");
    const baseAuth = (await import("../../i18n/messages/en/auth.json")).default;
    expect(messages.auth).toEqual(baseAuth);
  });

  it("an invalid NEXT_LOCALE cookie value falls through to requestLocale", async () => {
    cookieStore.set("NEXT_LOCALE", "es"); // not in routing.locales → ignored
    const { locale, messages } = await loadMessages("de");
    expect(locale).toBe("de");
    expect(ns(messages, "auth").displayNamePlaceholder).toBe("Wie sollen wir dich nennen?");
  });
});
