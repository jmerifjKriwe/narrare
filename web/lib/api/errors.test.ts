import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { catalogs, locales } from "../generated/catalogs";
import { ERROR_CODES } from "../generated/errorCodes";
import {
  ApiError,
  CODE_KEY,
  TransportError,
  codeOf,
  failureKey,
  isNetworkFailure,
} from "./errors";

const WEB = new URL("../..", import.meta.url).pathname;

describe("the one failure shape", () => {
  it("reads the code from each carrier the client builds", () => {
    expect(codeOf(new ApiError("x", { code: "rate-limited" }))).toBe("rate-limited");
    expect(
      codeOf(
        Object.assign(new Error("e"), {
          status: 422,
          detail: { code: "entity-invalid", detail: "…" },
        }),
      ),
    ).toBe("entity-invalid");
    expect(
      codeOf(
        Object.assign(new Error("e"), {
          status: 422,
          body: { detail: { code: "prompt-refused" } },
        }),
      ),
    ).toBe("prompt-refused");
    expect(codeOf(new ApiError("x", { code: "transport" }))).toBeNull();
  });

  it("names a failure by its code first, then its status family", () => {
    expect(failureKey(new ApiError("x", { status: 429, code: "rate-limited" }))).toBe(
      "errors.rateLimited",
    );
    expect(failureKey(new ApiError("x", { status: 404 }))).toBe("errors.notFound");
    expect(failureKey(new ApiError("x", { status: 422 }))).toBe("errors.refused");
    expect(failureKey(new ApiError("x", { status: 503 }))).toBe("errors.server");
  });

  it("names a request that never reached the server", () => {
    expect(failureKey(new TypeError("Failed to fetch"))).toBe("errors.network");
  });

  it("keeps a transport failure recognisable after it is wrapped", () => {
    const transport = new TransportError("x", new TypeError("Failed to fetch"));
    expect(codeOf(transport)).toBeNull();
    expect(isNetworkFailure(transport)).toBe(true);
    expect(failureKey(transport)).toBe("errors.network");
    expect(isNetworkFailure(new ApiError("no job to poll"))).toBe(false);
  });

  it("falls back when nothing names the failure", () => {
    expect(failureKey(new Error("bug"), "writing.shelf.error.title")).toBe(
      "writing.shelf.error.title",
    );
    expect(failureKey(new ApiError("no job to poll"))).toBe("errors.unexpected");
  });

  it("gives every code a sentence in every language", () => {
    for (const code of ERROR_CODES) {
      for (const language of locales) expect(catalogs[language][CODE_KEY[code]]).toMatch(/\S/);
    }
  });

  it("lets no request client throw a bare Error", () => {
    for (const file of ["lib/query.ts", "lib/updates.ts"]) {
      const source = readFileSync(join(WEB, file), "utf8");
      expect(source).not.toMatch(/throw new Error\(/);
    }
  });
});
