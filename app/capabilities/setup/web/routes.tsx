import { createRoute, redirect } from "@tanstack/react-router";
import { lazy } from "react";

import { rootRoute } from "@shell/routes/__root";

import { useSetupStatus } from "./useSetupStatus";

// React.lazy keeps the pages out of the shell's bundle: each loads as its
// own chunk, and the shell root's Suspense boundary covers the gap.
const WelcomePage = lazy(async () => {
  const page = await import("./WelcomePage");
  return { default: page.WelcomePage };
});
const LandingPage = lazy(async () => {
  const page = await import("./LandingPage");
  return { default: page.LandingPage };
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
 * The `/` gate: the welcome while the instance is unset, the landing once
 * it is set up. The status query suspends while its answer is in flight —
 * the root's boundary holds the gap, nothing invented — and every fresh
 * load of `/` asks the status anew, so a browser refresh after setup lands
 * on the landing, never on a remembered welcome.
 */
function HomeGate() {
  const { complete } = useSetupStatus();
  return complete ? <LandingPage /> : <WelcomePage />;
}

const homeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomeGate,
});

// `/setup` is the wizard's door, not a step of its own: it answers with the
// first step. The redirect keeps the current search — the wizard's answers
// ride search params (refresh-safe), and the door must not drop them.
const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup",
  beforeLoad: () => {
    throw redirect({ to: "/setup/basis", search: true });
  },
});

// The four steps, addressable each on its own — a refresh mid-wizard lands
// on the same step. All four are the ported drafts: basis, structure,
// AI-rules and the provisioning step that posts the one setup write.
const basisRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/basis",
  component: BasisStep,
});

const structureRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/structure",
  component: StructureStep,
});

const aiRulesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/ai-rules",
  component: AiRulesStep,
});

const provisioningRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup/provisioning",
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
  homeRoute,
  setupRoute,
  basisRoute,
  structureRoute,
  aiRulesRoute,
  provisioningRoute,
] as const;
