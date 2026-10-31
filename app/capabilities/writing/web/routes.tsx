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

/** Normalize numeric or string depths to 0, 1, or 2; default other values to 0. */
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
  // encoding is listed, so a shared link and the toggle agree — and no new
  // panel param ever makes them name the old ones. The output is optional:
  // links that don't care open expanded without naming the param. Focus
  // follows suit: it is omitted at the workbench depth so ordinary novel URLs
  // stay clean. The dock has no param at all: its open state is the child
  // route itself. `dock` stays in the accepted input so a hand-written
  // `?dock=chat` link still parses without error, but the output never
  // carries it — a key that round-tripped through rail/focus writes would
  // put the dock back in the URL, contradicting the clean-URL contract.
  // Chapter rides the same rules: the selection's address, accepted as any
  // non-empty string (an id is never a number, so the parser's typing can
  // not mangle it) and judged against the book's own rows in the page — a
  // dead id degrades there to the last-touched chapter instead of erroring
  // here. Absent is the ordinary workbench: the server's last-touched
  // choice, and nothing writes it back.
  validateSearch: (search: {
    rail?: unknown;
    focus?: unknown;
    dock?: unknown;
    chapter?: unknown;
  }): { rail?: boolean; focus?: FocusStep; chapter?: string } => {
    const focus = focusStep(search.focus);
    return {
      rail: !(search.rail === "0" || search.rail === 0 || search.rail === false),
      ...(focus > 0 ? { focus } : {}),
      ...(typeof search.chapter === "string" && search.chapter !== ""
        ? { chapter: search.chapter }
        : {}),
    };
  },
});

// The dock convention: the workspace route other capabilities' dockRoutes
// parent under, exported under the name the generator looks for. The
// generated table imports this const and passes it to every dock factory —
// capabilities never import each other; the generator is the one composition
// point.
export const workspaceRoute = novelRoute;

// The capability route contract: every route this capability mounts under the
// shell root, as a const tuple. The generated table (web/lib/generated/
// routes.ts) imports this array; a capability without this file mounts
// nothing.
//
// The route consts stand on their own on purpose: a contextual type here
// (a `Route[]` annotation or satisfies) degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [indexRoute, novelRoute] as const;
