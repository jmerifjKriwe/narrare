/**
 * Test-only API stand-in for the editor component tests: a real local HTTP
 * server that records the autosave's PUTs, plus the earliest possible
 * re-basing of fetch onto it.
 *
 * The re-base must happen before `@shell/lib/api/client` evaluates —
 * openapi-fetch captures `globalThis.fetch` when `createClient` runs — which
 * is why this module is separate and imported first by the test file. Node's
 * fetch (what jsdom runs on) cannot parse the client's relative URLs, so the
 * wrapper gives them the server's origin instead. Everything else about a
 * request stays real: the same openapi-fetch serialization, a real socket, a
 * real response the test can hold and release.
 */
import { createServer, type Server } from "node:http";
import type { AddressInfo } from "node:net";

/** One recorded request: where it went, what it carried, the power to answer late. */
export type RecordedRequest = { url: string; body: string; respond: () => void };

/** A continuation held open mid-stream: the ghost is on screen, the stream
 *  is still arriving, and the test decides how it ends. */
export type HeldContinuation = {
  /** Resolves when the connection goes away — within a test, the client
   *  aborting the stream. */
  closed: Promise<void>;
  /** End the held stream — test teardown, never a mid-test need. */
  finish: () => void;
  /** Destroy the connection: the wire dies mid-continuation, after what was
   *  written has reached the client. The fetch or its body read rejects. */
  break: () => void;
};

export const editorServer = {
  origin: "",
  requests: [] as RecordedRequest[],
  /** How many of the next incoming requests to hold without answering — the
   *  in-flight save a test wants to accept into. */
  holdNext: 0,
  /** The SSE body the next continuation POST will be answered with — the
   *  frames a test wants the real stream reader to read. One shot: the
   *  first /continue POST consumes it; null answers everything as the
   *  empty JSON save, as before. */
  continueWith: null as string | null,
  /** Answer the next continuation POST with a 503 instead of a stream —
   *  the request refused before a single word. One shot, like the body. */
  refuseContinue: false,
  /** Answer the next autosave PUT with a 500 — a refused write, one shot. */
  refuseSave: false,
  /** Answer the next autosave PUT with an empty 502 — the proxy's shape of a
   *  refusal, where openapi-fetch finds no error body to parse. One shot. */
  refuseSaveEmpty: false,
  /** Hold the continuation stream open after writing its body: the ghost is
   *  on screen and the stream is still mid-flight until the client aborts,
   *  the test finishes it or breaks the wire. One shot, like the body. */
  holdContinue: false,
  /** Destroy the continuation's connection right after the head, before a
   *  word of the body: the POST itself meets a dead wire — a rejected
   *  request, not a refusal. One shot, like the body. */
  breakContinue: false,
  /** The held continuation of the moment, when holdContinue was set. */
  continuation: null as HeldContinuation | null,
};

const realFetch = globalThis.fetch.bind(globalThis);
globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) => {
  // A Request instance is already absolute — openapi-fetch builds it with
  // the re-based Request below — so it passes through untouched; only bare
  // relative URLs gain the origin here.
  if (typeof input !== "string" && !(input instanceof URL)) {
    return realFetch(input as Request, init);
  }
  return realFetch(new URL(String(input), editorServer.origin), init);
}) as typeof fetch;

// openapi-fetch builds a Request object before it fetches, and Node's
// Request — unlike a browser's — refuses the client's relative URL right
// there. Re-based the same way as fetch, one origin for both.
const RealRequest = globalThis.Request;
globalThis.Request = class RebasedRequest extends RealRequest {
  constructor(input: string | URL | Request, init?: RequestInit) {
    super(input instanceof Request ? input : new URL(String(input), editorServer.origin), init);
  }
} as typeof Request;

let server: Server | null = null;

/** Bind the server on an ephemeral port and remember its origin. */
export async function startEditorServer(): Promise<void> {
  server = createServer((request, response) => {
    // An aborted continuation tears the connection down under the response;
    // the no-op listener keeps that teardown from crashing the test worker.
    response.on("error", () => {});
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
      // The continuation endpoint speaks its own protocol: a scripted body
      // is answered as the event-stream it is, immediately and unrecorded —
      // the stream tests assert on announcements and ghost text, not on the
      // request log the saves live in.
      if ((request.url ?? "").endsWith("/continue") && editorServer.breakContinue) {
        editorServer.breakContinue = false;
        response.writeHead(200, { "content-type": "text/event-stream" });
        response.destroy();
        return;
      }
      if ((request.url ?? "").endsWith("/continue") && editorServer.continueWith !== null) {
        const body = editorServer.continueWith;
        editorServer.continueWith = null;
        response.writeHead(200, { "content-type": "text/event-stream" });
        response.write(body);
        if (editorServer.holdContinue) {
          editorServer.holdContinue = false;
          editorServer.continuation = {
            closed: new Promise<void>((resolve) => response.on("close", () => resolve())),
            finish: () => {
              if (!response.writableEnded && !response.destroyed) response.end();
            },
            break: () => {
              response.destroy();
            },
          };
          return;
        }
        response.end();
        return;
      }
      if ((request.url ?? "").endsWith("/continue") && editorServer.refuseContinue) {
        editorServer.refuseContinue = false;
        response.writeHead(503, { "content-type": "application/json" });
        response.end("{}");
        return;
      }
      // Gated on the save's own shape — a PUT to a chapter path, the
      // autosave's request — so only that request can spend the one-shot;
      // a continuation POST falling through the guards above must reach
      // its own generic answer with the refusal still armed.
      if (
        editorServer.refuseSave &&
        request.method === "PUT" &&
        (request.url ?? "").startsWith("/api/writing/chapters/")
      ) {
        editorServer.refuseSave = false;
        response.writeHead(500, { "content-type": "application/json" });
        response.end('{"detail":"refused"}');
        return;
      }
      // The same refusal as it reaches the browser through a proxy: a 502
      // with no body at all. openapi-fetch parses `error` from the body, so
      // this answer arrives with `error === undefined` while saving nothing —
      // the status line, not the body, is what makes it a success.
      if (
        editorServer.refuseSaveEmpty &&
        request.method === "PUT" &&
        (request.url ?? "").startsWith("/api/writing/chapters/")
      ) {
        editorServer.refuseSaveEmpty = false;
        response.writeHead(502, { "content-length": "0" });
        response.end();
        return;
      }
      let responded = false;
      const record: RecordedRequest = {
        url: request.url ?? "",
        body: Buffer.concat(chunks).toString("utf8"),
        respond: () => {
          if (responded) return;
          responded = true;
          response.writeHead(200, { "content-type": "application/json" });
          response.end("{}");
        },
      };
      editorServer.requests.push(record);
      if (editorServer.holdNext > 0) editorServer.holdNext -= 1;
      else record.respond();
    });
  });
  await new Promise<void>((resolve) => server!.listen(0, "127.0.0.1", resolve));
  editorServer.origin = `http://127.0.0.1:${(server.address() as AddressInfo).port}`;
}

/** Close the server; held requests and continuations are answered first so
 * sockets drain. */
export async function stopEditorServer(): Promise<void> {
  for (const request of editorServer.requests) request.respond();
  editorServer.continuation?.finish();
  if (!server) return;
  server.closeAllConnections();
  await new Promise<void>((resolve) => server!.close(() => resolve()));
  server = null;
}
