/**
 * ghost-text-suggestions — Suggestion generator for the GhostText extension.
 *
 * Extracted from ghost-text-helpers for RULE-04 modularity.
 * Contains the built-in simulated suggestion generator for development/demo.
 * Phase 3 will replace this with real SSE streaming.
 *
 * @module ghost-text-suggestions
 */

// ── Simulated Suggestion Generator (Phase 2 Built-in) ─────────────────────────

/**
 * Simulated AI suggestion generator — trigger-based completions.
 *
 * Produces hardcoded completions for known trigger phrases for development
 * and demo use. Accepts an AbortSignal for cancellation and simulates
 * AI inference latency (300–600 ms).
 */
export async function simulateSuggestion(params: {
  textBefore: string;
  textAfter: string;
  signal: AbortSignal;
}): Promise<string> {
  const { textBefore, signal } = params;

  // Simulate AI inference latency (300-600ms)
  const delay = 300 + Math.random() * 300;
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(resolve, delay);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(new DOMException("Aborted", "AbortError"));
      },
      { once: true },
    );
  });

  if (signal.aborted) throw new DOMException("Aborted", "AbortError");

  // Trigger-based completions. Leading space provides natural gap between
  // the user's last word and the suggestion.
  const trimmed = textBefore.trimEnd();
  if (trimmed.endsWith("The old house")) {
    return " stood at the end of the lane, its windows dark.";
  }
  if (trimmed.endsWith("She walked")) {
    return " slowly towards the door, her footsteps echoing.";
  }
  if (trimmed.endsWith("It was a")) {
    return " cold and misty morning when they finally arrived.";
  }

  return " continued on their journey through the dark forest.";
}
