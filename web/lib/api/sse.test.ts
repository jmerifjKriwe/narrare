/**
 * The SSE frame reader (W4 Task 16) — the shell's transport seam for the
 * kernel's streaming contract (`app/kernel/llm/streaming.py`): `data:` frames
 * carry the JSON deltas, one terminal `event: done` or `event: error` closes
 * the stream. The reader parses exactly those bytes — frames split across
 * network chunks included — and nothing else: no buffering of the whole
 * answer (the typed client's shape), no invented events.
 */
import { describe, expect, it } from "vitest";

import { readSse, type SseFrame } from "./sse";

const encoder = new TextEncoder();

/** A stream that delivers the given chunks in order, then closes. */
function streamOf(chunks: readonly string[]): ReadableStream<Uint8Array> {
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

async function framesOf(chunks: readonly string[]): Promise<SseFrame[]> {
  const frames: SseFrame[] = [];
  for await (const frame of readSse(streamOf(chunks))) frames.push(frame);
  return frames;
}

describe("readSse — the kernel's frame contract", () => {
  it("reads data frames as the default message event, one per blank line", async () => {
    const frames = await framesOf([
      'data: {"delta": "Der Nebel hob sich "}\n\n',
      'data: {"delta": "vom See."}\n\n',
      "event: done\ndata: {}\n\n",
    ]);
    expect(frames).toEqual([
      { event: "message", data: '{"delta": "Der Nebel hob sich "}' },
      { event: "message", data: '{"delta": "vom See."}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("reads the coded error frame — the event name and the JSON payload", async () => {
    const frames = await framesOf([
      'event: error\ndata: {"code": "key-unavailable"}\n\n',
    ]);
    expect(frames).toEqual([{ event: "error", data: '{"code": "key-unavailable"}' }]);
  });

  it("a frame split across chunks arrives whole — the network decides the pieces", async () => {
    const frames = await framesOf([
      'data: {"del',
      'ta": "eins"}\n',
      '\ndata: {"delta": "zwei"}\n\nevent: do',
      "ne\ndata: {}\n\n",
    ]);
    expect(frames).toEqual([
      { event: "message", data: '{"delta": "eins"}' },
      { event: "message", data: '{"delta": "zwei"}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("multi-line data joins with newlines, the event line names the frame", async () => {
    const frames = await framesOf(["event: custom\ndata: eins\ndata: zwei\n\n"]);
    expect(frames).toEqual([{ event: "custom", data: "eins\nzwei" }]);
  });

  it("comments and unknown fields never become frames", async () => {
    const frames = await framesOf([
      ": keep-alive\n\n",
      "id: 7\nretry: 1000\ndata: {}\n\n",
    ]);
    expect(frames).toEqual([{ event: "message", data: "{}" }]);
  });

  it("CRLF line endings parse as LF ones", async () => {
    const frames = await framesOf(['data: {"delta": "x"}\r\n\r\nevent: done\r\ndata: {}\r\n\r\n']);
    expect(frames).toEqual([
      { event: "message", data: '{"delta": "x"}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("a trailing frame without its final blank line still dispatches at close", async () => {
    const frames = await framesOf(['data: {"delta": "x"}\n\nevent: done\ndata: {}']);
    expect(frames).toEqual([
      { event: "message", data: '{"delta": "x"}' },
      { event: "done", data: "{}" },
    ]);
  });

  it("an empty stream yields no frames", async () => {
    expect(await framesOf([])).toEqual([]);
    expect(await framesOf(["\n\n"])).toEqual([]);
  });

  it("strips exactly one leading space after the field colon", async () => {
    const frames = await framesOf(["data:  zwei Leerzeichen\n\n"]);
    expect(frames).toEqual([{ event: "message", data: " zwei Leerzeichen" }]);
  });
});
