/**
 * Unit tests for the REST API error mapper.
 *
 * Regression coverage for CR-AUFG-07-33: a plain `Error` from `fetchApi`
 * must NOT leak its raw `error.message` to the UI. All errors are delegated
 * to `mapSSEError` for structured i18n mapping (§16.5).
 *
 * @module ai-rest-error.test
 */

import { describe, expect, it } from "vitest";

import { AI_ERROR_MESSAGE_MAP } from "@/lib/api/ai-error-mapping";
import { mapRestApiError } from "@/lib/api/ai-rest-error";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create an SSEStreamError-like object (Error with a `kind` property). */
function createSSEStreamError(message: string, kind: string, status?: number): Error {
  const error = new Error(message);
  Object.assign(error, { kind, ...(status !== undefined ? { status } : {}) });
  return error;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("mapRestApiError", () => {
  // -------------------------------------------------------------------------
  // CR-AUFG-07-33: raw error.message must NOT leak to the UI
  // -------------------------------------------------------------------------

  it("does NOT leak raw error.message — maps plain Error to errorConnection", () => {
    const error = new Error("fetch failed: Internal Server Error traceback...");
    const result = mapRestApiError(error);
    expect(result).not.toBeNull();
    // Delegated to mapSSEError → generic Error becomes a network/connection error
    expect(result!.kind).toBe("network");
    expect(result!.i18nKey).toBe("aiActions.errorConnection");
    expect(result!.retryable).toBe(true);
    // The raw backend message must never reach the user
    expect(result!.userMessage).not.toBe(error.message);
    expect(result!.userMessage).toBe(AI_ERROR_MESSAGE_MAP["aiActions.errorConnection"].de);
    expect(result!.cause).toBe(error);
  });

  // -------------------------------------------------------------------------
  // CR-AUFG-07-31: SyntaxError → data corruption (not retryable)
  // -------------------------------------------------------------------------

  it("maps SyntaxError → errorDataCorrupt (delegated to mapSSEError)", () => {
    const error = new SyntaxError("Unexpected token < in JSON");
    const result = mapRestApiError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("parse");
    expect(result!.i18nKey).toBe("aiActions.errorDataCorrupt");
    expect(result!.retryable).toBe(false);
    expect(result!.cause).toBe(error);
  });

  // -------------------------------------------------------------------------
  // AbortError → null (swallowed, user cancelled)
  // -------------------------------------------------------------------------

  it("returns null for DOMException AbortError", () => {
    const error = new DOMException("Aborted", "AbortError");
    expect(mapRestApiError(error)).toBeNull();
  });

  it("returns null for Error with name AbortError", () => {
    const error = new Error("Aborted");
    error.name = "AbortError";
    expect(mapRestApiError(error)).toBeNull();
  });

  // -------------------------------------------------------------------------
  // SSEStreamError delegation (rich mapping passes through unchanged)
  // -------------------------------------------------------------------------

  it("delegates SSEStreamError http 401 → errorApiKey", () => {
    const error = createSSEStreamError("HTTP 401", "http", 401);
    const result = mapRestApiError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(401);
    expect(result!.i18nKey).toBe("aiActions.errorApiKey");
    expect(result!.retryable).toBe(false);
  });

  it("delegates SSEStreamError network kind → errorConnection", () => {
    const error = createSSEStreamError("network down", "network");
    const result = mapRestApiError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("network");
    expect(result!.i18nKey).toBe("aiActions.errorConnection");
    expect(result!.retryable).toBe(true);
  });

  it("delegates SSEStreamError http 429 → errorRateLimit", () => {
    const error = createSSEStreamError("HTTP 429", "http", 429);
    const result = mapRestApiError(error);
    expect(result).not.toBeNull();
    expect(result!.i18nKey).toBe("aiActions.errorRateLimit");
    expect(result!.retryable).toBe(true);
  });
});
