import { createRoute, redirect } from "@tanstack/react-router";
import { lazy } from "react";

import { queryClient } from "@shell/lib/query";
import { rootRoute } from "@shell/routes/__root";

import { setupStatusQueryOptions } from "./setupStatusQuery";

// React.lazy keeps the pages out of the shell's bundle: each loads as its
// own chunk, and the shell root's Suspense boundary covers the gap.
const WelcomePage = lazy(async () => {
  const page = await import("./WelcomePage");
  return { default: page.WelcomePage };
});
const BasisStep = lazy(async () => {
  const page = await import("./steps/BasisStep");
  return { default: page.BasisStep };
});
const StructureStep = lazy(async () => {
  const page = await import("./steps/StructureStep");
  return { default: page.StructureStep };
});
const AiRulesStep = lazy(async () => {
  const page = await import("./steps/AiRulesStep");
  return { default: page.AiRulesStep };
});
const ProvisioningStep = lazy(async () => {
  const page = await import("./steps/ProvisioningStep");
  return { default: page.ProvisioningStep };
});

/**
 * The inverse gate's load-time check: an installed instance has no wizard.
 * `/setup` and every step ask the status once per navigation and answer with
 * a redirect to the shelf (`/`, the writing capability's gate) when setup is
 * complete; pre-setup they fall through to the welcome or the step.
 *
 * The check lives in `beforeLoad`, not in a render gate, on purpose: the
 * provisioning step flips the status itself when its POST lands, and it must
 * stay mounted to show the bound checklist — a render gate would re-read the
 * invalidated status and kick the user off the bound face mid-step. A loader
 * runs on arrival, so a post-setup deep link redirects while the step that
 * just bound stays. The shared options keep this ask on the same key the
 * hook reads and the write invalidates; a fresh load asks anew (empty cache),
 * so a refresh is honest. A failed ask throws to the root's error screen.
 */
async function redirectIfSetUp(): Promise<void> {
  const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
  if (complete) throw redirect({ to: "/" });
}

// `/setup` is the welcome's home after the W3 handover (the writing capability
// owns `/` now): pre-setup it renders the welcome, whose CTAs already lead to
// `/setup/basis`; post-setup the inverse gate redirects to the shelf.
const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup",
  beforeLoad: redirectIfSetUp,
  component: WelcomePage,
});

// The four steps, addressable each on its own — a refresh mid-wizard lands
// on the same step. All four are the ported drafts: basis, structure,
// AI-rules and the provisioning step that posts the one setup write. Each
// carries the inverse gate: a post-setup deep link redirects to the shelf
// (the 409 story in the provisioning step covers re-runs that race the gate).
const basisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/basis",
  beforeLoad: redirectIfSetUp,
  component: BasisStep,
});

const structureRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/structure",
  beforeLoad: redirectIfSetUp,
  component: StructureStep,
});

const aiRulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/ai-rules",
  beforeLoad: redirectIfSetUp,
  component: AiRulesStep,
});

const provisioningRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/provisioning",
  beforeLoad: redirectIfSetUp,
  component: ProvisioningStep,
});

// The capability route contract: every route this capability mounts under the
// shell root, as a const tuple. The generated table (web/lib/generated/
// routes.ts) imports this array; a capability without this file mounts
// nothing.
//
// The route consts stand on their own on purpose: a contextual type here
// (a `Route[]` annotation or satisfies) degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [
  setupRoute,
  basisRoute,
  structureRoute,
  aiRulesRoute,
  provisioningRoute,
] as const;
