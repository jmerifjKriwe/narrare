/**
 * The SSE frame reader (W4 Task 16) — the shell's transport seam for the
 * kernel's streaming contract (`app/kernel/llm/streaming.py`): `data:` frames
 * carry JSON payloads, one terminal `event: done` or `event: error` closes
 * the stream. Writing's continuation is the first consumer; chat's stream
 * speaks the same frames.
 *
 * fetch, not the typed client: openapi-fetch buffers the whole answer before
 * it parses, and a continuation must arrive piece by piece — the ghost
 * preview grows with the wire. The reader owns only the framing (the SSE
 * field grammar the kernel spells); what a frame's payload means belongs to
 * the capability that asked.
 */

/** One frame as the wire delivers it: the event name (`message` when the
 *  frame carries none — the SSE default) and the raw data payload. */
export interface SseFrame {
  event: string;
  data: string;
}

/** The value after a field's colon, minus the one optional leading space
 *  the SSE grammar allows (`data: x` and `data:x` carry the same value). */
function fieldValue(line: string, colon: number): string {
  const value = line.slice(colon + 1);
  return value.startsWith(" ") ? value.slice(1) : value;
}

/**
 * Read an SSE response body frame by frame. Lines arrive as the network
 * delivers them — a frame may split across any number of chunks — and a
 * blank line dispatches what accumulated. Comments (`:`) and the fields the
 * kernel never sends (`id:`, `retry:`) are ignored; multi-line `data:` joins
 * with newlines, the SSE grammar's own rule. A stream that closes holding an
 * unterminated frame dispatches it at the end: the kernel always terminates
 * its frames, but a reader that drops the last one on a truncation would
 * hide the terminal event exactly when it matters most.
 */
export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<SseFrame> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "";
  let data: string[] = [];

  /** One accumulated frame, or null when nothing accumulated. */
  const dispatch = (): SseFrame | null => {
    if (data.length === 0 && event === "") return null;
    const frame = { event: event === "" ? "message" : event, data: data.join("\n") };
    event = "";
    data = [];
    return frame;
  };

  /** Consume every whole line the buffer holds; the remainder stays. */
  function* lines(): Generator<SseFrame> {
    for (;;) {
      const at = buffer.indexOf("\n");
      if (at === -1) return;
      const line = buffer.slice(0, at).replace(/\r$/, "");
      buffer = buffer.slice(at + 1);
      if (line === "") {
        const frame = dispatch();
        if (frame !== null) yield frame;
      } else if (line.startsWith(":")) {
        // A comment — the keep-alive the SSE grammar reserves.
      } else if (line.startsWith("data:")) {
        data.push(fieldValue(line, 4));
      } else if (line.startsWith("event:")) {
        event = fieldValue(line, 5);
      }
      // Unknown fields (id:, retry:) carry no meaning for this contract.
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      yield* lines();
    }
    buffer += decoder.decode();
    // The close may leave a last line without its newline — read it too.
    if (buffer !== "") buffer += "\n";
    yield* lines();
    const last = dispatch();
    if (last !== null) yield last;
  } finally {
    reader.releaseLock();
  }
}
