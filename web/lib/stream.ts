/** Read a text/event-stream response and yield its text deltas, in order. */
export async function* readDeltas(response: Response): AsyncGenerator<string> {
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
        const payload: { delta?: string } = JSON.parse(line.slice(6));
        if (payload.delta) yield payload.delta;
      }
      boundary = buffer.indexOf("\n\n");
    }
  }
}
