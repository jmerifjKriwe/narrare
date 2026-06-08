/**
 * Default error mapper for AI operations.
 *
 * Maps SSEStreamError and HTTP status codes to structured, i18n-ready
 * AIErrorResponse objects using studio.aiActions.* keys (§16.5, §16.8).
 *
 * Machine-checkable: all error messages use i18n keys, never raw strings.
 *
 * @module ai-error-mapping
 */

import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import type { SSEStreamError } from "./streaming";

// ---------------------------------------------------------------------------
// Error message map — i18n keys with DE fallbacks
// ---------------------------------------------------------------------------

/** i18n key → default DE message and retryability. Actual text comes from i18n. */
export const AI_ERROR_MESSAGE_MAP: Record<string, { de: string; retryable: boolean }> = {
  "aiActions.errorApiKey": {
    de: "Dein API-Schlüssel ist ungültig. Überprüfe deine KI-Einstellungen.",
    retryable: false,
  },
  "aiActions.errorTextTooLong": {
    de: "Der Text ist zu lang für die KI. Kürze die Auswahl und versuche es erneut.",
    retryable: false,
  },
  "aiActions.errorRateLimit": {
    de: "Du hast zu viele Anfragen gesendet. Warte einen Moment.",
    retryable: true,
  },
  "aiActions.errorTimeout": {
    de: "Die KI braucht zu lange. Versuche es mit weniger Kontext erneut.",
    retryable: true,
  },
  "aiActions.errorConnection": {
    de: "Verbindung verloren. Prüfe deine Internetverbindung.",
    retryable: true,
  },
  "aiActions.errorParse": {
    de: "Die KI-Antwort war fehlerhaft. Versuche es erneut.",
    retryable: true,
  },
  "aiActions.errorDefault": {
    de: "Ein unerwarteter Fehler ist aufgetreten. Versuche es erneut.",
    retryable: true,
  },
};

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Map an SSEStreamError (or any error) to a structured AIErrorResponse.
 *
 * Mapping rules (§16.5):
 *   - AbortError     → null (swallowed, returns to idle)
 *   - kind="http" + 401  → api key invalid
 *   - kind="http" + 413  → text too long
 *   - kind="http" + 429  → rate limit
 *   - kind="http" + 408  → timeout
 *   - kind="http" + 5xx  → connection/server error
 *   - kind="network"     → connection lost
 *   - kind="parse"       → parse error
 *   - kind="stream"      → stream error
 *   - kind="timeout"     → timeout
 *   - Generic Error      → connection error
 *   - Unknown            → default error
 */
export function mapSSEError(error: unknown): AIErrorResponse | null {
  // Abort errors are swallowed — not an error state
  if (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  ) {
    return null;
  }

  // SSEStreamError or any error with a "kind" property
  if (error instanceof Error && "kind" in error) {
    const sse = error as SSEStreamError;
    return mapSSEStreamError(sse);
  }

  // Generic Error → connection error
  if (error instanceof Error) {
    return {
      kind: "network",
      i18nKey: "aiActions.errorConnection",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de,
      retryable: true,
      cause: error,
    };
  }

  // Completely unknown → default error
  return {
    kind: "stream",
    i18nKey: "aiActions.errorDefault",
    userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorDefault"].de,
    retryable: true,
    cause: new Error(String(error)),
  };
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

function mapSSEStreamError(error: SSEStreamError): AIErrorResponse {
  if (error.kind === "abort") {
    return {
      kind: "abort",
      i18nKey: "aiActions.errorDefault",
      userMessage: "",
      retryable: false,
      cause: error,
    };
  }

  if (error.kind === "http") {
    return mapHTTPError(error);
  }

  if (error.kind === "network") {
    return {
      kind: "network",
      i18nKey: "aiActions.errorConnection",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de,
      retryable: true,
      status: error.status,
      cause: error,
    };
  }

  if (error.kind === "parse") {
    return {
      kind: "parse",
      i18nKey: "aiActions.errorParse",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorParse"].de,
      retryable: true,
      cause: error,
    };
  }

  // "stream" or unknown
  return {
    kind: "stream",
    i18nKey: "aiActions.errorDefault",
    userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorDefault"].de,
    retryable: true,
    cause: error,
  };
}

function mapHTTPError(error: SSEStreamError): AIErrorResponse {
  const status = error.status ?? 0;

  if (status === 401) {
    return {
      kind: "http",
      status: 401,
      i18nKey: "aiActions.errorApiKey",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorApiKey"].de,
      retryable: false,
      cause: error,
    };
  }

  if (status === 413) {
    return {
      kind: "http",
      status: 413,
      i18nKey: "aiActions.errorTextTooLong",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorTextTooLong"].de,
      retryable: false,
      cause: error,
    };
  }

  if (status === 429) {
    return {
      kind: "http",
      status: 429,
      i18nKey: "aiActions.errorRateLimit",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorRateLimit"].de,
      retryable: true,
      cause: error,
    };
  }

  if (status === 408) {
    return {
      kind: "http",
      status: 408,
      i18nKey: "aiActions.errorTimeout",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorTimeout"].de,
      retryable: true,
      cause: error,
    };
  }

  // 5xx or other HTTP errors
  return {
    kind: "http",
    status,
    i18nKey: "aiActions.errorConnection",
    userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de,
    retryable: true,
    cause: error,
  };
}
