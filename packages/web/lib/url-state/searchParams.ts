import type { Route } from "next";

export function cloneSearchParams(searchParams: URLSearchParams): URLSearchParams {
  return new URLSearchParams(searchParams.toString());
}

export function setOptionalSearchParam(
  searchParams: URLSearchParams,
  key: string,
  value: string | null,
): URLSearchParams {
  const next = cloneSearchParams(searchParams);
  if (value === null || value === "") next.delete(key);
  else next.set(key, value);
  return next;
}

export function searchParamsHref(pathname: string, searchParams: URLSearchParams): Route {
  const query = searchParams.toString();
  return (query.length > 0 ? `${pathname}?${query}` : pathname) as Route;
}
