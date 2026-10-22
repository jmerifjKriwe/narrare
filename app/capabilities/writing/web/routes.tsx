import { createRoute } from "@tanstack/react-router";
import { lazy } from "react";

import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the page out of the shell's bundle: the capability loads
// as its own chunk, and the shell root's Suspense boundary covers the gap.
const NovelsPage = lazy(async () => {
  const page = await import("./NovelsPage");
  return { default: page.NovelsPage };
});

const NovelPage = lazy(async () => {
  const page = await import("./NovelPage");
  return { default: page.NovelPage };
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: NovelsPage,
});

// Focus depth, same convention as rail: the value is URL state, validated
// tolerantly because the router's default parser hands typed values (a
// linked `?focus=2` arrives as the number 2) while hand-written links may
// arrive as strings. Anything that is not a step is the workbench.
const FOCUS_STEPS = [0, 1, 2] as const;
export type FocusStep = (typeof FOCUS_STEPS)[number];

function focusStep(value: unknown): FocusStep {
  const parsed = typeof value === "string" ? Number(value) : value;
  return FOCUS_STEPS.find((step) => step === parsed) ?? 0;
}

const novelRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$id",
  component: NovelPage,
  // Panel state is URL state. The default search parser hands validateSearch
  // typed values, not raw strings: a linked `?rail=0` arrives as the number 0,
  // and the page's own toggle writes booleans (`?rail=false`). Every collapsed
  // encoding is listed, so a shared link and the toggle agree — and the dock
  // params of later phases extend the same convention. The output is optional:
  // links that don't care open expanded without naming the param, and no new
  // panel param ever makes them name the old ones. Focus follows suit: it is
  // omitted at the workbench depth so ordinary novel URLs stay clean.
  validateSearch: (search: {
    rail?: unknown;
    focus?: unknown;
  }): { rail?: boolean; focus?: FocusStep } => {
    const focus = focusStep(search.focus);
    return {
      rail: !(search.rail === "0" || search.rail === 0 || search.rail === false),
      ...(focus > 0 ? { focus } : {}),
    };
  },
});

// The capability route contract: every route this capability mounts under the
// shell root, as a const tuple. The generated table (web/lib/generated/
// routes.ts) imports this array; a capability without this file mounts
// nothing.
//
// The route consts stand on their own on purpose: a contextual type here
// (a `Route[]` annotation or satisfies) degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [indexRoute, novelRoute] as const;
