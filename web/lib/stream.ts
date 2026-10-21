export type Source = {
  chunk_id: string;
  document_title: string;
  text: string;
};

export type Frame = {
  delta?: string;
  sources?: Source[];
};

/** Read a text/event-stream response and yield its parsed data payloads, in order. */
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
      for (const line of frame.split("\n")) {
        if (!line.startsWith("data: ")) continue;
        yield JSON.parse(line.slice(6)) as Frame;
      }
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
