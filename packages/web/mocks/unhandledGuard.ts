import type { SetupServer } from "msw/node";
import { afterEach, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// MSW — unhandled requests fail tests MECHANICALLY (layer 2)
// ---------------------------------------------------------------------------
// PO directive after the ECONNREFUSED incident (commit 0006ec86): the "all
// endpoints handled" invariant must be enforced, not assumed. Two layers:
//
// 1. `onUnhandledRequest: "error"` (configured at the `server.listen` call
//    site in setupTests.ts) — the fetch itself REJECTS. Necessary but NOT
//    sufficient: consumers that catch (React Query puts the rejection into
//    error state) swallow it, and the test still passes (proven by mutation
//    probe: a test rendering ExportPanel with the formats handler removed
//    logs "[MSW] Error: intercepted a request without a matching request
//    handler" on stderr yet stays green — and vitest's default reporter hides
//    console output of passing tests entirely).
//
// 2. This guard — `request:unhandled` event bookkeeping + afterEach
//    assertion. Records every unhandled request during a test and FAILS that
//    test afterwards, regardless of how the application code handles the
//    rejection. This is the mechanical guard; layer 1 keeps the runtime
//    behaviour honest.
//
// Requests captured between tests (in-flight queries outliving a test, module
// import time) are attributed to the next test — a failure either way.
export function installUnhandledRequestGuard(server: SetupServer): void {
  let unhandledRequests: string[] = [];
  server.events.on("request:unhandled", ({ request }) => {
    const url = new URL(request.url);
    unhandledRequests.push(`${request.method} ${url.pathname}${url.search}`);
  });

  beforeEach(() => {
    unhandledRequests = [];
  });

  // Enforce the handled-requests invariant for the test that just ran.
  afterEach(() => {
    if (unhandledRequests.length > 0) {
      const listing = unhandledRequests.map((r) => `\n  • ${r}`).join("");
      throw new Error(
        `[MSW] unhandled request(s) during this test (add a handler to mocks/handlers/ or a per-test server.use override):${listing}`,
      );
    }
  });
}
