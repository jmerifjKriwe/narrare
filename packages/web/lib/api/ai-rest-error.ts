/**
 * REST API error mapper for AI operations.
 *
 * Preserves the original error message from the API response
 * rather than mapping to a generic connection-lost message.
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
 * - Plain Error → preserve message for user display
 * - SSEStreamError or unknown → delegate to mapSSEError for rich mapping
 */
export function mapRestApiError(error: unknown): AIErrorResponse | null {
  // AbortError → swallow (user cancelled)
  if (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  ) {
    return null;
  }
  // Plain Error from fetchApi → preserve message
  if (error instanceof Error) {
    return {
      kind: "http",
      i18nKey: "aiActions.errorDefault",
      userMessage: error.message,
      retryable: true,
      cause: error,
    };
  }
  // SSEStreamError or unknown → rich mapping
  return mapSSEError(error);
}
