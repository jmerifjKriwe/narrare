/**
 * Shared SSE streaming transport for AI responses.
 * Uses native fetch + ReadableStream — axios cannot do this.
 */

import { getAccessToken } from "./client";

export type SSEMethod = "GET" | "POST";

export type SSEErrorKind = "abort" | "http" | "network" | "parse" | "stream";

export class SSEStreamError extends Error {
  constructor(
    message: string,
    public readonly kind: SSEErrorKind,
    public readonly status?: number,
    public readonly cause?: unknown,
  ) {
    super(message);
    this.name = "SSEStreamError";
  }
}

export interface SSEOptions<T> {
  url: string;
  method?: SSEMethod;
  body?: unknown;
  onChunk: (chunk: T) => void;
  onComplete?: (result: T | undefined) => void;
  onError?: (error: SSEStreamError) => void;
  signal?: AbortSignal;
  /** Maximum time in ms to wait for the initial HTTP response. Default: 30_000 (30s). */
  connectTimeoutMs?: number;
}

interface ParsedSSEEvent {
  data: string;
}

function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}

export function normalizeSSEError(error: unknown): SSEStreamError {
  if (error instanceof SSEStreamError) return error;
  if (isAbortError(error)) return new SSEStreamError("Stream aborted", "abort", undefined, error);
  if (error instanceof Error) return new SSEStreamError(error.message, "network", undefined, error);
  return new SSEStreamError(String(error), "network", undefined, error);
}

function buildHeaders(hasBody: boolean): Record<string, string> {
  const headers: Record<string, string> = { Accept: "text/event-stream" };
  if (hasBody) headers["Content-Type"] = "application/json";

  const token = getAccessToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function parseSSEBuffer(buffer: string): { events: ParsedSSEEvent[]; remainder: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const remainder = blocks.pop() ?? "";
  const events = blocks.flatMap((block) => {
    const dataLines = block
      .split("\n")
      .filter((line) => line.startsWith("data:"))
      .map((line) => line.slice(5).trimStart());
    return dataLines.length > 0 ? [{ data: dataLines.join("\n") }] : [];
  });
  return { events, remainder };
}

function parseSingleLineEvents(buffer: string): { events: ParsedSSEEvent[]; remainder: string } {
  const lines = buffer.split("\n");
  const remainder = lines.pop() ?? "";
  const events = lines.flatMap((line) => {
    if (!line.startsWith("data:")) return [];
    return [{ data: line.slice(5).trimStart() }];
  });
  return { events, remainder };
}

async function processSSEStream<T>(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  options: Pick<SSEOptions<T>, "onChunk" | "onComplete" | "onError">,
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const parsed = buffer.includes("\n\n") ? parseSSEBuffer(buffer) : parseSingleLineEvents(buffer);
    buffer = parsed.remainder;

    for (const event of parsed.events) {
      if (event.data === "[DONE]") {
        options.onComplete?.(undefined);
        return;
      }

      try {
        options.onChunk(JSON.parse(event.data) as T);
      } catch (error) {
        options.onError?.(
          new SSEStreamError("Malformed SSE JSON event", "parse", undefined, error),
        );
      }
    }
  }

  options.onComplete?.(undefined);
}

/** Default connect timeout — 30 seconds for initial HTTP response. */
export const DEFAULT_CONNECT_TIMEOUT_MS = 30_000;

export async function connectSSE<T>({
  url,
  method = "POST",
  body,
  onChunk,
  onComplete,
  onError,
  signal,
  connectTimeoutMs = DEFAULT_CONNECT_TIMEOUT_MS,
}: SSEOptions<T>): Promise<void> {
  const hasBody = method !== "GET" && body !== undefined;

  // Internal AbortController for the connect timeout.
  // Combines with the caller's signal via AbortSignal.any() so either can abort.
  const timeoutController = new AbortController();
  const combinedSignal = signal
    ? AbortSignal.any([signal, timeoutController.signal])
    : timeoutController.signal;

  const timeoutId = setTimeout(() => timeoutController.abort(), connectTimeoutMs);

  try {
    const response = await fetch(`/api/v1${url}`, {
      method,
      headers: buildHeaders(hasBody),
      credentials: "include",
      body: hasBody ? JSON.stringify(body) : undefined,
      signal: combinedSignal,
    });

    if (!response.ok) {
      throw new SSEStreamError(`HTTP ${response.status}`, "http", response.status);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new SSEStreamError("No response body", "stream");

    await processSSEStream(reader, { onChunk, onComplete, onError });
  } catch (error) {
    const normalized = normalizeSSEError(error);
    if (normalized.kind === "abort") return;
    onError?.(normalized);
  } finally {
    clearTimeout(timeoutId);
  }
}
