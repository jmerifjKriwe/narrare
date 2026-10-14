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
import { ApiError } from "./core";
import type { SSEStreamError } from "./streaming";

// ---------------------------------------------------------------------------
// Error message map — i18n keys with DE fallbacks
// ---------------------------------------------------------------------------

/**
 * i18n key → default DE message and retryability. Actual text comes from i18n.
 * Keys may come from any `studio.*` sub-namespace (e.g. `aiActions.*` and
 * `generationPanel.*` both live in `studio.json`) — the mapper only needs the
 * suffix form because every consumer resolves under `useTranslations("studio")`.
 */
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
  "aiActions.errorBudgetExceeded": {
    de: "Dein monatliches KI-Budget ist erreicht. Erhöhe oder entferne es in den KI-Einstellungen.",
    retryable: false,
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
  "aiActions.errorDataCorrupt": {
    de: "Die Daten konnten nicht gelesen werden. Möglicherweise ist eine Datei beschädigt. Überprüfe deine Sicherungen oder kontaktiere den Support.",
    retryable: false,
  },
  "generationPanel.validationMissingInput": {
    de: "Mindestens eines der Felder Gliederung, Prompt oder automatisches Fortfahren muss ausgefüllt sein.",
    retryable: false,
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
 *   - SyntaxError    → data-corrupt error (invalid/unreadable KB data, not retryable)
 *   - ApiError (REST) → mapped by status + machine `code` (429 BUDGET_EXCEEDED → budget stop)
 *   - kind="http" + 401  → api key invalid
 *   - kind="http" + 413  → text too long
 *   - kind="http" + 422 + code="MISSING_INPUT" → empty-input validation (not retryable)
 *   - kind="http" + 429 + code="BUDGET_EXCEEDED" → monthly budget stop (not a rate limit)
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

  // Data corruption: JSON parse failure (SyntaxError) → data-corrupt error.
  // A SyntaxError signals invalid/unreadable data (e.g. corrupt KB file),
  // which is not a transient connection issue and is not retryable.
  if (error instanceof SyntaxError) {
    return {
      kind: "parse",
      i18nKey: "aiActions.errorDataCorrupt",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorDataCorrupt"].de,
      retryable: false,
      cause: error,
    };
  }

  // ApiError from fetchApi (REST AI calls): map by HTTP status + machine
  // `code` exactly like SSEStreamError "http" failures (ADR-094: a 429
  // BUDGET_EXCEEDED must reach the budget message, not "connection lost").
  if (error instanceof ApiError) {
    return mapHTTPStatus(error.status, error.code, error);
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
  return mapHTTPStatus(error.status ?? 0, error.code ?? null, error);
}

/** Shared status+code → AIErrorResponse mapping for SSE and REST (ApiError) failures. */
function mapHTTPStatus(status: number, code: string | null, cause: Error): AIErrorResponse {
  if (status === 401) {
    return {
      kind: "http",
      status: 401,
      i18nKey: "aiActions.errorApiKey",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorApiKey"].de,
      retryable: false,
      cause,
    };
  }

  if (status === 413) {
    return {
      kind: "http",
      status: 413,
      i18nKey: "aiActions.errorTextTooLong",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorTextTooLong"].de,
      retryable: false,
      cause,
    };
  }

  if (status === 422 && code === "MISSING_INPUT") {
    // Audit M06: an empty generate form is a validation error, not a
    // connection failure — map it to the panel's honest key (en/de/fr
    // parity already shipped with the panel).
    return {
      kind: "http",
      status: 422,
      i18nKey: "generationPanel.validationMissingInput",
      userMessage: AI_ERROR_MESSAGE_MAP["generationPanel.validationMissingInput"].de,
      retryable: false,
      cause,
    };
  }

  if (status === 429) {
    // Budget stops are NOT rate limits (ADR-094): the block-mode gate is not
    // transient — a retry hits the same stop until the budget is raised, so
    // this is not retryable.
    if (code === "BUDGET_EXCEEDED") {
      return {
        kind: "http",
        status: 429,
        i18nKey: "aiActions.errorBudgetExceeded",
        userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorBudgetExceeded"].de,
        retryable: false,
        cause,
      };
    }
    return {
      kind: "http",
      status: 429,
      i18nKey: "aiActions.errorRateLimit",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorRateLimit"].de,
      retryable: true,
      cause,
    };
  }

  if (status === 408) {
    return {
      kind: "http",
      status: 408,
      i18nKey: "aiActions.errorTimeout",
      userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorTimeout"].de,
      retryable: true,
      cause,
    };
  }

  // 5xx or other HTTP errors
  return {
    kind: "http",
    status,
    i18nKey: "aiActions.errorConnection",
    userMessage: AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de,
    retryable: true,
    cause,
  };
}
