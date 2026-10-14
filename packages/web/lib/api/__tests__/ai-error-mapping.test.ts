/**
 * Unit tests for the AI error mapping module.
 *
 * Covers: all error kinds, HTTP status code mapping, abort swallowing,
 * unknown errors, parse errors.
 *
 * @module ai-error-mapping.test
 */

import { describe, expect, it } from "vitest";

import { AI_ERROR_MESSAGE_MAP, mapSSEError } from "@/lib/api/ai-error-mapping";
import { mapRestApiError } from "@/lib/api/ai-rest-error";
import { ApiError } from "@/lib/api/core";
import { SSEStreamError } from "@/lib/api/streaming";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Create an SSEStreamError-like object. */
function createSSEStreamError(message: string, kind: string, status?: number): Error {
  const error = new Error(message);
  Object.assign(error, { kind, ...(status !== undefined ? { status } : {}) });
  return error;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("mapSSEError", () => {
  // -------------------------------------------------------------------------
  // Abort errors → null (swallowed)
  // -------------------------------------------------------------------------

  it("returns null for DOMException AbortError", () => {
    const error = new DOMException("Aborted", "AbortError");
    expect(mapSSEError(error)).toBeNull();
  });

  it("returns null for Error with name AbortError", () => {
    const error = new Error("Aborted");
    error.name = "AbortError";
    expect(mapSSEError(error)).toBeNull();
  });

  // -------------------------------------------------------------------------
  // HTTP status code mapping
  // -------------------------------------------------------------------------

  it("maps HTTP 401 → errorApiKey", () => {
    const error = createSSEStreamError("HTTP 401", "http", 401);
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(401);
    expect(result!.i18nKey).toBe("aiActions.errorApiKey");
    expect(result!.retryable).toBe(false);
  });

  it("maps HTTP 413 → errorTextTooLong", () => {
    const error = createSSEStreamError("HTTP 413", "http", 413);
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(413);
    expect(result!.i18nKey).toBe("aiActions.errorTextTooLong");
    expect(result!.retryable).toBe(false);
  });

  it("maps HTTP 429 → errorRateLimit", () => {
    const error = createSSEStreamError("HTTP 429", "http", 429);
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(429);
    expect(result!.i18nKey).toBe("aiActions.errorRateLimit");
    expect(result!.retryable).toBe(true);
  });

  // -------------------------------------------------------------------------
  // 429 BUDGET_EXCEEDED → budget stop, NOT a rate limit (ADR-094)
  // -------------------------------------------------------------------------

  it("maps SSE HTTP 429 + code BUDGET_EXCEEDED → errorBudgetExceeded (not retryable)", () => {
    const error = new SSEStreamError("HTTP 429", "http", 429, "BUDGET_EXCEEDED");
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(429);
    expect(result!.i18nKey).toBe("aiActions.errorBudgetExceeded");
    expect(result!.retryable).toBe(false);
    expect(result!.userMessage).toBe(AI_ERROR_MESSAGE_MAP["aiActions.errorBudgetExceeded"].de);
  });

  it("maps REST ApiError 429 + BUDGET_EXCEEDED → errorBudgetExceeded (mapRestApiError)", () => {
    const error = new ApiError("Monthly budget exceeded", 429, "BUDGET_EXCEEDED");
    const result = mapRestApiError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(429);
    expect(result!.i18nKey).toBe("aiActions.errorBudgetExceeded");
    expect(result!.retryable).toBe(false);
  });

  it("maps REST ApiError 429 without the budget code → errorRateLimit", () => {
    const result = mapRestApiError(new ApiError("Too many requests", 429, null));
    expect(result).not.toBeNull();
    expect(result!.i18nKey).toBe("aiActions.errorRateLimit");
    expect(result!.retryable).toBe(true);
  });

  it("maps REST ApiError 500 → errorConnection (status-based fallback)", () => {
    const result = mapRestApiError(new ApiError("Boom", 500, null));
    expect(result).not.toBeNull();
    expect(result!.i18nKey).toBe("aiActions.errorConnection");
  });

  it("maps HTTP 408 → errorTimeout", () => {
    const error = createSSEStreamError("HTTP 408", "http", 408);
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(408);
    expect(result!.i18nKey).toBe("aiActions.errorTimeout");
    expect(result!.retryable).toBe(true);
  });

  it("maps HTTP 500 → errorConnection", () => {
    const error = createSSEStreamError("HTTP 500", "http", 500);
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(500);
    expect(result!.i18nKey).toBe("aiActions.errorConnection");
    expect(result!.retryable).toBe(true);
  });

  it("maps HTTP 502 → errorConnection", () => {
    const error = createSSEStreamError("HTTP 502", "http", 502);
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.i18nKey).toBe("aiActions.errorConnection");
  });

  // -------------------------------------------------------------------------
  // Network errors
  // -------------------------------------------------------------------------

  it("maps network kind → errorConnection", () => {
    const error = createSSEStreamError("fetch failed", "network");
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("network");
    expect(result!.i18nKey).toBe("aiActions.errorConnection");
    expect(result!.retryable).toBe(true);
  });

  it("maps generic Error → network → errorConnection", () => {
    const error = new Error("Something went wrong");
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("network");
    expect(result!.i18nKey).toBe("aiActions.errorConnection");
    expect(result!.retryable).toBe(true);
  });

  // -------------------------------------------------------------------------
  // Parse errors
  // -------------------------------------------------------------------------

  it("maps parse kind → errorParse", () => {
    const error = createSSEStreamError("Malformed JSON", "parse");
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("parse");
    expect(result!.i18nKey).toBe("aiActions.errorParse");
    expect(result!.retryable).toBe(true);
  });

  // -------------------------------------------------------------------------
  // Data corruption (SyntaxError from JSON.parse) → errorDataCorrupt
  // -------------------------------------------------------------------------

  it("maps SyntaxError → errorDataCorrupt (data corruption, not retryable)", () => {
    const error = new SyntaxError("Unexpected token < in JSON");
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("parse");
    expect(result!.i18nKey).toBe("aiActions.errorDataCorrupt");
    expect(result!.retryable).toBe(false);
    expect(result!.cause).toBe(error);
  });

  // -------------------------------------------------------------------------
  // Stream errors
  // -------------------------------------------------------------------------

  it("maps stream kind → errorDefault", () => {
    const error = createSSEStreamError("Stream interrupted", "stream");
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("stream");
    expect(result!.i18nKey).toBe("aiActions.errorDefault");
    expect(result!.retryable).toBe(true);
  });

  // -------------------------------------------------------------------------
  // Unknown errors
  // -------------------------------------------------------------------------

  it("maps unknown non-Error → errorDefault", () => {
    const result = mapSSEError("string error");
    expect(result).not.toBeNull();
    expect(result!.kind).toBe("stream");
    expect(result!.i18nKey).toBe("aiActions.errorDefault");
    expect(result!.retryable).toBe(true);
    expect(result!.cause.message).toBe("string error");
  });

  it("maps null → errorDefault", () => {
    const result = mapSSEError(null);
    expect(result).not.toBeNull();
    expect(result!.i18nKey).toBe("aiActions.errorDefault");
  });

  it("maps undefined → errorDefault", () => {
    const result = mapSSEError(undefined);
    expect(result).not.toBeNull();
    expect(result!.i18nKey).toBe("aiActions.errorDefault");
  });

  // -------------------------------------------------------------------------
  // AI_ERROR_MESSAGE_MAP completeness
  // -------------------------------------------------------------------------

  it("AI_ERROR_MESSAGE_MAP has all 9 error keys", () => {
    const expectedKeys = [
      "aiActions.errorApiKey",
      "aiActions.errorTextTooLong",
      "aiActions.errorRateLimit",
      "aiActions.errorBudgetExceeded",
      "aiActions.errorTimeout",
      "aiActions.errorConnection",
      "aiActions.errorParse",
      "aiActions.errorDefault",
      "aiActions.errorDataCorrupt",
    ];

    for (const key of expectedKeys) {
      expect(AI_ERROR_MESSAGE_MAP[key]).toBeDefined();
      expect(AI_ERROR_MESSAGE_MAP[key].de).toBeTruthy();
      expect(typeof AI_ERROR_MESSAGE_MAP[key].retryable).toBe("boolean");
    }
  });

  // -------------------------------------------------------------------------
  // Error response structure
  // -------------------------------------------------------------------------

  it("returns structured AIErrorResponse with cause", () => {
    const error = new Error("test error");
    const result = mapSSEError(error);
    expect(result).not.toBeNull();
    expect(result!.cause).toBe(error);
    expect(typeof result!.userMessage).toBe("string");
    expect(result!.userMessage.length).toBeGreaterThan(0);
  });
});

describe("MISSING_INPUT validation mapping (audit M06)", () => {
  it("maps 422 + MISSING_INPUT to the generationPanel validation key", () => {
    const error = new ApiError(
      "At least one of prompt, outline, or auto_continue must be provided",
      422,
      "MISSING_INPUT",
    );

    const result = mapSSEError(error);

    expect(result).not.toBeNull();
    expect(result!.kind).toBe("http");
    expect(result!.status).toBe(422);
    expect(result!.i18nKey).toBe("generationPanel.validationMissingInput");
    expect(result!.retryable).toBe(false);
  });

  it("keeps the generic connection mapping for 422 without a known code", () => {
    const error = new ApiError("Unprocessable entity", 422, null);

    const result = mapSSEError(error);

    expect(result!.i18nKey).toBe("aiActions.errorConnection");
  });
});
