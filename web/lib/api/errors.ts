import { useCallback } from "react";

import { isErrorCode, type ErrorCode } from "../generated/errorCodes";
import { useTranslation, type MessageKey } from "../i18n";

/**
 * One failure shape for every request the client makes. The wire's stable code
 * is kept as the typed member it is, the response's status beside it, and the
 * body's detail for the face that names the refusal. The console keeps the
 * message today's throws carried (`create refused: 422`); a failure without a
 * response reads `what: transport`.
 */
export class ApiError extends Error {
  readonly status: number | null;
  readonly code: ErrorCode | null;
  readonly detail: unknown;
  /** The refusal's own facts beyond its code: a relation row's index, the
   *  field a validation named. */
  readonly extra: Record<string, unknown>;

  constructor(
    what: string,
    init: {
      status?: number | null;
      code?: unknown;
      detail?: unknown;
      extra?: Record<string, unknown>;
    } = {},
  ) {
    const status = init.status ?? null;
    super(status === null ? `${what}: transport` : `${what}: ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.code = isErrorCode(init.code) ? init.code : null;
    this.detail = init.detail;
    this.extra = init.extra ?? {};
  }
}

/**
 * The request threw before there was a response. A `TypeError` also stays
 * recognisable in its own right (`isNetworkFailure`), and `cause` keeps the
 * browser's own error when the console asks what happened.
 */
export class TransportError extends ApiError {
  constructor(what: string, cause: unknown) {
    super(what);
    this.name = "TransportError";
    (this as Error).cause = cause;
  }
}

/** The stable code a response body carries: `{"detail": {"code"}}` or a bare
 *  `{"code"}`. A code outside the kernel's list is no code. */
export function wireCode(body: unknown): ErrorCode | null {
  if (typeof body !== "object" || body === null) return null;
  const detail = (body as { detail?: unknown }).detail;
  const nested =
    typeof detail === "object" && detail !== null
      ? (detail as { code?: unknown }).code
      : undefined;
  const candidate = nested ?? (body as { code?: unknown }).code;
  return isErrorCode(candidate) ? candidate : null;
}

/** The code a failure carries: its own when it is an `ApiError`, else the one
 *  in its `detail` or `body`. */
export function codeOf(error: unknown): ErrorCode | null {
  if (error instanceof ApiError) return error.code;
  const carrier = error as { detail?: unknown; body?: unknown } | null | undefined;
  return wireCode(carrier?.detail) ?? wireCode(carrier?.body);
}

/** The HTTP status a failure carries, when it carries one. */
export function statusOf(error: unknown): number | null {
  if (error instanceof ApiError) return error.status;
  const status = (error as { status?: unknown } | null | undefined)?.status;
  return typeof status === "number" ? status : null;
}

/** A request that never reached the server: the browser's own `TypeError`, or
 *  the wrap this seam puts around it. */
export function isNetworkFailure(error: unknown): boolean {
  return error instanceof TransportError || error instanceof TypeError;
}

/**
 * Every wire code the kernel can send, and the one sentence that speaks it.
 * Exhaustive by type: a new code cannot arrive without a sentence.
 */
export const CODE_KEY: Record<ErrorCode, MessageKey> = {
  archive_invalid: "errors.refused",
  "embedding-mismatch": "errors.embeddingMismatch",
  "entity-invalid": "errors.refused",
  "entity-type-required": "errors.refused",
  "entity-type-unknown": "errors.refused",
  "extraction-failed": "errors.answerUnreadable",
  "key-unavailable": "errors.keyUnavailable",
  "mode-unknown": "errors.refused",
  "model-not-found": "errors.modelNotFound",
  "no-context": "errors.noContext",
  "not-found": "errors.notFound",
  order_mismatch: "errors.changedMeanwhile",
  "prompt-refused": "errors.promptUnavailable",
  "provider-auth": "errors.providerAuth",
  "provider-error": "errors.providerFailed",
  "provider-unavailable": "errors.providerUnavailable",
  "rate-limited": "errors.rateLimited",
  "relation-duplicate": "errors.refused",
  "relation-limit": "errors.refused",
  "relation-target-invalid": "errors.refused",
  "session-closed": "errors.closed",
  "suggestion-mismatch": "errors.changedMeanwhile",
  target_not_empty: "errors.refused",
  unknown: "errors.unexpected",
};

/**
 * The catalog key that names a failure: its stable code first, then its
 * status family, then a request that never reached the server, then the
 * caller's own fallback (or the generic sentence).
 */
export function failureKey(
  error: unknown,
  fallback: MessageKey = "errors.unexpected",
): MessageKey {
  const code = codeOf(error);
  if (code !== null) return CODE_KEY[code];
  const status = statusOf(error);
  if (status === 404) return "errors.notFound";
  if (status === 429) return "errors.rateLimited";
  if (status !== null && status >= 500 && status <= 599) return "errors.server";
  if (status !== null) return "errors.refused";
  if (isNetworkFailure(error)) return "errors.network";
  return fallback;
}

/**
 * The render-time reader: it returns a function that names a failure in the
 * active language, so a language switch re-renders the sentence rather than
 * freezing the language a failure was caught in.
 */
export function useLocalizedError(): (error: unknown, fallback?: MessageKey) => string {
  const t = useTranslation();
  return useCallback(
    (error: unknown, fallback?: MessageKey) => t(failureKey(error, fallback)),
    [t],
  );
}
