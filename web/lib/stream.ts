export type Source = {
  chunk_id: string;
  document_title: string;
  text: string;
};

export type Frame = {
  delta?: string;
  sources?: Source[];
  error?: string;
};

/** Read a text/event-stream response and yield its parsed frames, in order.
 * An `event:` line names the frame's kind: the routers end a dead provider
 * with `event: error`, and the reader must carry that into the frame.
 * Frames end at two LF characters; an incomplete trailing frame is ignored.
 * A missing body yields nothing. Invalid JSON and stream read errors propagate;
 * an error event is yielded as a frame rather than thrown.
 */
export async function* readFrames(response: Response): AsyncGenerator<Frame> {
  const body = response.body;
  if (!body) return;
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      let event: string | undefined;
      const data: string[] = [];
      for (const line of frame.split("\n")) {
        if (line.startsWith("event: ")) event = line.slice(7);
        else if (line.startsWith("data: ")) data.push(line.slice(6));
      }
      // A frame with neither field — a comment, a keep-alive — is no fact.
      if (data.length === 0 && event === undefined) continue;
      const parsed = (data.length === 0 ? {} : JSON.parse(data.join("\n"))) as Frame;
      // The failure lives in the event, not the payload: a reader that
      // dropped `event:` parsed this frame to `{}`, and a truncation looked
      // like a clean end of the stream.
      if (event === "error") parsed.error ??= "stream failed";
      yield parsed;
      boundary = buffer.indexOf("\n\n");
    }
  }
}

/** Read a text/event-stream response and yield its text deltas, in order. */
export async function* readDeltas(response: Response): AsyncGenerator<string> {
  for await (const frame of readFrames(response)) {
    if (frame.delta) yield frame.delta;
  }
}
