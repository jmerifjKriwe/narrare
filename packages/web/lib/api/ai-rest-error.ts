/**
 * REST API error mapper for AI operations.
 *
 * Delegates to `mapSSEError` for structured error mapping. Never passes the
 * raw underlying error text through to the UI — doing so could leak backend
 * internals (tracebacks, database errors) per §16.5.
 * Used by hooks that wrap useAIOperation for REST (non-SSE) calls.
 *
 * @module ai-rest-error
 */

import type { AIErrorResponse } from "@/lib/hooks/use-ai-operation";
import { mapSSEError } from "./ai-error-mapping";

/**
 * Map a REST API error (from fetchApi) to a structured AIErrorResponse.
 *
 * - AbortError → null (swallowed, user cancelled)
 * - All other errors → delegate to mapSSEError for structured i18n mapping (§16.5)
 */
export function mapRestApiError(error: unknown): AIErrorResponse | null {
  // AbortError → swallow (user cancelled)
  if (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  ) {
    return null;
  }
  // Plain Error, SSEStreamError, or unknown → delegate to mapSSEError
  // for structured i18n mapping (§16.5). The raw underlying message is
  // never used as userMessage — it could leak backend internals.
  return mapSSEError(error);
}
