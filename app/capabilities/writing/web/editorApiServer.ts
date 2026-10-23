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

export const editorServer = {
  origin: "",
  requests: [] as RecordedRequest[],
  /** How many of the next incoming requests to hold without answering — the
   *  in-flight save a test wants to accept into. */
  holdNext: 0,
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
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(chunk));
    request.on("end", () => {
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

/** Close the server; held requests are answered first so sockets drain. */
export async function stopEditorServer(): Promise<void> {
  for (const request of editorServer.requests) request.respond();
  if (!server) return;
  server.closeAllConnections();
  await new Promise<void>((resolve) => server!.close(() => resolve()));
  server = null;
}
