import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useMemo } from "react";

interface UseUrlParamOptions {
  /** Search-param name, e.g. "q" or "category". */
  readonly paramName: string;
  /** Optional allow-list; values outside it fall back to defaultValue. */
  readonly allowed?: readonly string[];
  /** Value used when the param is absent or invalid. */
  readonly defaultValue: string;
}

/**
 * One-adapter-per-surface URL search-param sync (spec §6, Phase C §8.3).
 *
 * Defaults to `replace` (transient typing must not pollute history); callers
 * pass `"push"` for explicit selection changes (Phase C §16). Fail-safe:
 * invalid values normalise to `defaultValue`. One adapter instance per
 * surface avoids two components fighting over the same search params.
 */
export function useUrlParam({ paramName, allowed, defaultValue }: UseUrlParamOptions): {
  value: string;
  setValue: (next: string, mode?: "replace" | "push") => void;
} {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const value = useMemo(
    () => normaliseParam(searchParams.get(paramName), allowed, defaultValue),
    [searchParams, paramName, allowed, defaultValue],
  );

  const setValue = useCallback(
    (next: string, mode: "replace" | "push" = "replace") => {
      const params = new URLSearchParams(searchParams.toString());
      // Clear the param when the value is empty or back at the default so the
      // URL stays clean and shareable.
      if (next === defaultValue || next === "") {
        params.delete(paramName);
      } else {
        params.set(paramName, next);
      }
      const query = params.toString();
      const url = query ? `${pathname}?${query}` : pathname;
      if (mode === "push") router.push(url as never);
      else router.replace(url as never);
    },
    [searchParams, paramName, defaultValue, pathname, router],
  );

  return { value, setValue };
}

/**
 * Pure normaliser — unit-testable without a router. Returns `defaultValue`
 * for absent/empty values and for values outside the optional allow-list.
 */
export function normaliseParam(
  value: string | null,
  allowed: readonly string[] | undefined,
  defaultValue: string,
): string {
  if (value === null || value === "") return defaultValue;
  if (allowed && !allowed.includes(value)) return defaultValue;
  return value;
}
