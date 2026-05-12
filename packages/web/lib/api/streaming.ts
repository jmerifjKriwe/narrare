/**
 * SSE streaming client for AI responses.
 * Uses native fetch + ReadableStream — axios cannot do this.
 */

import { getAccessToken } from "./client";

export interface SSEOptions<T> {
  url: string;
  body: unknown;
  onChunk: (chunk: T) => void;
  onComplete?: (result: T) => void;
  onError?: (error: Error) => void;
  signal?: AbortSignal;
}

export async function connectSSE<T>({
  url,
  body,
  onChunk,
  onComplete,
  onError,
  signal,
}: SSEOptions<T>): Promise<void> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };

  const token = getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  try {
    const response = await fetch(`/api/v1${url}`, {
      method: "POST",
      headers,
      credentials: "include",
      body: JSON.stringify(body),
      signal,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const reader = response.body?.getReader();
    if (!reader) throw new Error("No response body");

    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // Parse SSE events
      const lines = buffer.split("\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const data = line.slice(6);
          if (data === "[DONE]") {
            onComplete?.(undefined as T);
            return;
          }
          try {
            const parsed = JSON.parse(data) as T;
            onChunk(parsed);
          } catch {
            // Skip malformed JSON
          }
        }
      }
    }
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") return;
    onError?.(error instanceof Error ? error : new Error(String(error)));
  }
}
