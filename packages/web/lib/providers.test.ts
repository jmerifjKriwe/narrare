import { describe, expect, it } from "vitest";
import deAi from "../../i18n/messages/de/settings-ai.json";
import enAi from "../../i18n/messages/en/settings-ai.json";
import frAi from "../../i18n/messages/fr/settings-ai.json";
import { getProviderLabel, PROVIDERS } from "./providers";

/** Identity translator: a resolved key surfaces verbatim, an unresolved one stays raw. */
const t = (key: string) => key;

describe("getProviderLabel", () => {
  it("should resolve known providers through the translator (i18n key, RULE-16)", () => {
    expect(getProviderLabel("anthropic", t)).toBe("settings-ai.providers.anthropic");
    expect(getProviderLabel("openai", t)).toBe("settings-ai.providers.openai");
    expect(getProviderLabel("google", t)).toBe("settings-ai.providers.google");
    expect(getProviderLabel("groq", t)).toBe("settings-ai.providers.groq");
    expect(getProviderLabel("ollama", t)).toBe("settings-ai.providers.ollama");
    expect(getProviderLabel("openrouter", t)).toBe("settings-ai.providers.openrouter");
    expect(getProviderLabel("zai", t)).toBe("settings-ai.providers.zai");
  });

  it("should return raw value for unknown provider", () => {
    expect(getProviderLabel("unknown-provider", t)).toBe("unknown-provider");
    expect(getProviderLabel("custom", t)).toBe("custom");
    expect(getProviderLabel("", t)).toBe("");
  });

  it("should handle case-sensitive matching (exact match required)", () => {
    // The implementation uses strict equality, so different case returns raw value
    expect(getProviderLabel("Anthropic", t)).toBe("Anthropic");
    expect(getProviderLabel("OPENAI", t)).toBe("OPENAI");
  });

  it("should handle all providers from PROVIDERS constant", () => {
    for (const provider of PROVIDERS) {
      expect(getProviderLabel(provider.value, t)).toBe(provider.labelKey);
    }
  });
});

// ---------------------------------------------------------------------------
// Locale resolution guard (coordinator ruling T4-R2)
// ---------------------------------------------------------------------------
// The global next-intl mock is an identity translator, so no component test can
// detect an off-namespace provider key: `settings-ai.providers.<id>` resolved
// through a `useTranslations("studio")` translator would render the raw dotted
// string in the real UI while every test stays green. This suite resolves each
// provider's real key against the real message trees instead.
//
// The sanity check that this guard can fail: the ruling's regression case is the
// key form `settings.providers.<id>`. `resolveProviderKey` rejects it on the
// namespace-prefix check (it does not begin with `settings-ai.`). That prefix
// check is this guard's ONLY discriminator for that regression: the tree walk
// here indexes the `settings-ai.json` trees imported at the top of this file,
// where `providers.ollama` DOES resolve, so a `settings.providers.<id>` key would
// still walk to a truthy, non-key string if the prefix check were removed. (The
// production next-intl lookup would fail on `settings.json`, whose `providers`
// entry is the section-title string `"Providers"`, not an object — but that tree
// is not the one walked here.) Deleting the prefix check therefore silently
// drops the protection. Verified by mutation: switching a label key back to
// `settings.providers.<id>` turned this suite red (4 failures) before the change
// was reverted.

type MessageTree = Record<string, unknown>;

/**
 * Resolve a fully-qualified `settings-ai.providers.<id>` key against one
 * locale's `settings-ai.json` tree, mirroring the namespace mapping the real
 * next-intl request config applies (`lib/i18n/request.ts`). A key without the
 * `settings-ai.` namespace prefix resolves to null by design.
 */
function resolveProviderKey(tree: MessageTree, key: string): string | null {
  const namespace = "settings-ai.";
  if (!key.startsWith(namespace)) {
    return null;
  }
  let node: unknown = tree;
  for (const segment of key.slice(namespace.length).split(".")) {
    if (typeof node !== "object" || node === null) {
      return null;
    }
    node = (node as MessageTree)[segment];
  }
  return typeof node === "string" ? node : null;
}

const LOCALE_TREES: { locale: string; tree: MessageTree }[] = [
  { locale: "en", tree: enAi },
  { locale: "de", tree: deAi },
  { locale: "fr", tree: frAi },
];

describe("provider label keys resolve against the real locale trees", () => {
  function expectAllProvidersResolve(locale: string, tree: MessageTree): void {
    for (const provider of PROVIDERS) {
      const label = resolveProviderKey(tree, provider.labelKey) ?? "";
      expect(label, `${locale}:${provider.value} must resolve to text`).toBeTruthy();
      expect(label, `${locale}:${provider.value} must not stay a key`).not.toBe(provider.labelKey);
    }
  }

  it("resolves every provider label as human-readable text (en)", () => {
    expectAllProvidersResolve("en", enAi);
  });

  it("resolves every provider label as human-readable text (de)", () => {
    expectAllProvidersResolve("de", deAi);
  });

  it("resolves every provider label as human-readable text (fr)", () => {
    expectAllProvidersResolve("fr", frAi);
  });

  it("covers exactly the seven canonical provider ids", () => {
    expect(LOCALE_TREES).toHaveLength(3);
    expect(PROVIDERS.map((p) => p.value)).toEqual([
      "anthropic",
      "openai",
      "google",
      "groq",
      "ollama",
      "openrouter",
      "zai",
    ]);
  });
});
