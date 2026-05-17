import { describe, expect, it } from "vitest";
import { getProviderLabel, PROVIDERS } from "./providers";

describe("getProviderLabel", () => {
  it("should return correct label for known providers", () => {
    expect(getProviderLabel("anthropic")).toBe("Anthropic");
    expect(getProviderLabel("openai")).toBe("OpenAI");
    expect(getProviderLabel("google")).toBe("Google AI");
    expect(getProviderLabel("groq")).toBe("Groq");
    expect(getProviderLabel("ollama")).toBe("Ollama (local)");
    expect(getProviderLabel("openrouter")).toBe("OpenRouter");
    expect(getProviderLabel("zai")).toBe("Z.AI");
  });

  it("should return raw value for unknown provider", () => {
    expect(getProviderLabel("unknown-provider")).toBe("unknown-provider");
    expect(getProviderLabel("custom")).toBe("custom");
    expect(getProviderLabel("")).toBe("");
  });

  it("should handle case-sensitive matching (exact match required)", () => {
    // The implementation uses strict equality, so different case returns raw value
    expect(getProviderLabel("Anthropic")).toBe("Anthropic");
    expect(getProviderLabel("OPENAI")).toBe("OPENAI");
  });

  it("should handle all providers from PROVIDERS constant", () => {
    for (const provider of PROVIDERS) {
      expect(getProviderLabel(provider.value)).toBe(provider.label);
    }
  });
});
