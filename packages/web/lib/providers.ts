import type { AIProvider } from "@/types";

/** Shared provider list with display labels — single source of truth. */
export const PROVIDERS: { value: AIProvider; label: string }[] = [
  { value: "anthropic", label: "Anthropic" },
  { value: "openai", label: "OpenAI" },
  { value: "google", label: "Google AI" },
  { value: "groq", label: "Groq" },
  { value: "ollama", label: "Ollama (local)" },
  { value: "openrouter", label: "OpenRouter" },
  { value: "zai", label: "Z.AI" },
];

/** Return the display label for a provider value, or the raw value if unknown. */
export function getProviderLabel(value: AIProvider | string): string {
  return PROVIDERS.find((p) => p.value === value)?.label ?? value;
}
