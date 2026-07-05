/**
 * use-url-param hook tests (Task 5).
 *
 * Covers the pure `normaliseParam` helper (unit-testable without a router)
 * and the `useUrlParam` hook (router integration via a controllable mock).
 *
 * The global setupTests mock for `next/navigation` uses plain arrows that
 * `vi.mocked()` cannot target, so this file re-mocks `next/navigation` with
 * real `vi.fn()` instances hoisted ahead of the mock factory.
 */

import { act, renderHook } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { normaliseParam, useUrlParam } from "@/lib/hooks/use-url-param";

// Hoisted, per-test-controllable router + search-params state. `vi.hoisted`
// guarantees these exist before the (hoisted) `vi.mock` factory executes.
const env = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: env.push, replace: env.replace }),
  useSearchParams: () => env.searchParams,
  usePathname: () => "/studio/novels/novel-1/kb",
  useParams: () => ({ id: "novel-1" }),
}));

describe("normaliseParam", () => {
  it("returns the value when it is in the allow-list", () => {
    expect(normaliseParam("general", ["general", "ai"], "general")).toBe("general");
  });

  it("falls back to default when value is null", () => {
    expect(normaliseParam(null, ["general"], "general")).toBe("general");
  });

  it("falls back to default when value is not allowed", () => {
    expect(normaliseParam("evil", ["general"], "general")).toBe("general");
  });

  it("passes any non-empty value through when no allow-list is given", () => {
    expect(normaliseParam("free text", undefined, "")).toBe("free text");
  });

  it("returns default for empty string when an allow-list is enforced", () => {
    expect(normaliseParam("", ["general"], "general")).toBe("general");
  });
});

describe("useUrlParam", () => {
  beforeEach(() => {
    env.push.mockReset();
    env.replace.mockReset();
    env.searchParams = new URLSearchParams();
  });

  it("reads the current value from the search params", () => {
    env.searchParams = new URLSearchParams("q=dragons");
    const { result } = renderHook(() => useUrlParam({ paramName: "q", defaultValue: "" }));
    expect(result.current.value).toBe("dragons");
  });

  it("falls back to the default value when the param is absent", () => {
    const { result } = renderHook(() => useUrlParam({ paramName: "q", defaultValue: "all" }));
    expect(result.current.value).toBe("all");
  });

  it("setValue replaces the URL with the new param by default", () => {
    const { result } = renderHook(() => useUrlParam({ paramName: "q", defaultValue: "" }));
    act(() => {
      result.current.setValue("dragons");
    });
    expect(env.replace).toHaveBeenCalledTimes(1);
    expect(env.replace).toHaveBeenCalledWith("/studio/novels/novel-1/kb?q=dragons");
    expect(env.push).not.toHaveBeenCalled();
  });

  it("setValue uses push mode when explicitly requested", () => {
    const { result } = renderHook(() =>
      useUrlParam({ paramName: "category", defaultValue: "general" }),
    );
    act(() => {
      result.current.setValue("ai", "push");
    });
    expect(env.push).toHaveBeenCalledTimes(1);
    expect(env.push).toHaveBeenCalledWith("/studio/novels/novel-1/kb?category=ai");
    expect(env.replace).not.toHaveBeenCalled();
  });

  it("deletes the param when the value equals the default (keeps URLs clean)", () => {
    env.searchParams = new URLSearchParams("q=dragons");
    const { result } = renderHook(() => useUrlParam({ paramName: "q", defaultValue: "" }));
    act(() => {
      result.current.setValue("");
    });
    expect(env.replace).toHaveBeenCalledWith("/studio/novels/novel-1/kb");
  });

  it("normalises disallowed values to the default on read", () => {
    env.searchParams = new URLSearchParams("category=evil");
    const { result } = renderHook(() =>
      useUrlParam({
        paramName: "category",
        allowed: ["general", "ai"],
        defaultValue: "general",
      }),
    );
    expect(result.current.value).toBe("general");
  });
});
