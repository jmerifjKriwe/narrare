/**
 * Test-only API stand-in for the chat panel component tests: a real local
 * HTTP server that answers /api/chat/ask with a scripted event-stream —
 * optionally held open mid-answer — plus the earliest possible re-basing of
 * fetch onto it.
 *
 * The re-base must happen before `@shell/lib/api/client` evaluates —
 * openapi-fetch captures `globalThis.fetch` when `createClient` runs — which
 * is why this module is separate and imported first by the test file. Node's
 * fetch (what jsdom runs on) cannot parse the client's relative URLs, so the
 * wrapper gives them the server's origin instead. Everything else about a
 * request stays real: the same openapi-fetch serialization, a real socket, a
 * real response body the test can leave unfinished.
 */
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";

/** One recorded ask: where it went, what it carried, and its connection. */
export type RecordedAsk = {
  url: string;
  body: string;
  /** Resolves when the connection goes away. A held answer is never ended
   *  by the server, so within a test this is the client aborting the ask. */
  closed: Promise<void>;
  /** End the held answer — test teardown, never a mid-test need. */
  finish: () => void;
  /** Destroy the held answer's connection: the wire dies mid-answer, after
   *  what was written has reached the client. A network failure, not a
   *  refusal — the fetch or its body read rejects on the client side. */
  break: () => void;
};

export const chatServer = {
  origin: "",
  asks: [] as RecordedAsk[],
  /** The SSE body the next ask is answered with; null answers as the empty
   *  JSON save. One shot: the first ask consumes it. */
  answerWith: null as string | null,
  /** Hold the answer open after writing its body: the stream stays
   *  mid-answer until the client aborts it or the test finishes it. */
  hold: false,
};

const realFetch = globalThis.fetch.bind(globalThis);
globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => {
  // A Request instance is already absolute — openapi-fetch builds it with
  // the re-based Request below — so it passes through untouched; only bare
  // relative URLs gain the origin here.
  if (typeof input !== "string" && !(input instanceof URL)) {
    return realFetch(input as Request, init);
  }
  return realFetch(new URL(String(input), chatServer.origin), init);
}) as typeof fetch;

// openapi-fetch builds a Request object before it fetches, and Node's
// Request — unlike a browser's — refuses the client's relative URL right
// there. Re-based the same way as fetch, one origin for both.
const RealRequest = globalThis.Request;
globalThis.Request = class RebasedRequest extends RealRequest {
  constructor(input: string | URL | Request, init?: RequestInit) {
    super(input instanceof Request ? input : new URL(String(input), chatServer.origin), init);
  }
} as typeof Request;

let server: Server | null = null;

/** Bind the server on an ephemeral port and remember its origin. */
export async function startChatServer(): Promise<void> {
  server = createServer((request, response) => {
    // An aborted ask tears the connection down under the response; the
    // no-op listeners keep that teardown from crashing the test worker.
    response.on("error", () => {});
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      const sse = chatServer.answerWith;
      chatServer.answerWith = null;
      const record: RecordedAsk = {
        url: request.url ?? "",
        body: Buffer.concat(chunks).toString("utf8"),
        closed: new Promise<void>((resolve) => response.on("close", () => resolve())),
        finish: () => {
          if (!response.writableEnded && !response.destroyed) response.end();
        },
        break: () => {
          response.destroy();
        },
      };
      chatServer.asks.push(record);
      if (sse === null) {
        response.writeHead(200, { "content-type": "application/json" });
        response.end("{}");
        return;
      }
      response.writeHead(200, { "content-type": "text/event-stream" });
      response.write(sse);
      if (!chatServer.hold) response.end();
    });
  });
  await new Promise<void>((resolve) => server!.listen(0, "127.0.0.1", resolve));
  chatServer.origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
}

/** Close the server; held answers are ended first so sockets drain. */
export async function stopChatServer(): Promise<void> {
  for (const ask of chatServer.asks) ask.finish();
  if (!server) return;
  server.closeAllConnections();
  await new Promise<void>((resolve) => server!.close(() => resolve()));
  server = null;
}
