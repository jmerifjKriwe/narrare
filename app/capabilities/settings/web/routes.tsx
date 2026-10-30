import { createRoute } from "@tanstack/react-router";
import { lazy } from "react";

import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the pages out of the shell's bundle: the capability loads
// as its own chunk, and the shell root's Suspense boundary covers the gap.
const SettingsLayout = lazy(async () => {
  const page = await import("./SettingsLayout");
  return { default: page.SettingsLayout };
});

const SettingsHub = lazy(async () => {
  const page = await import("./SettingsPage");
  return { default: page.SettingsPage };
});

const LanguagePage = lazy(async () => {
  const page = await import("./LanguagePage");
  return { default: page.LanguagePage };
});

const ProviderPage = lazy(async () => {
  const page = await import("./ProviderPage");
  return { default: page.ProviderPage };
});

// The area's frame: title, back door, cluster nav, and the outlet every
// child renders into.
const settingsLayoutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: SettingsLayout,
});

// The index child is the hub: one card per cluster, the gear's landing.
const settingsIndexRoute = createRoute({
  getParentRoute: () => settingsLayoutRoute,
  path: "/",
  component: SettingsHub,
});

const languageRoute = createRoute({
  getParentRoute: () => settingsLayoutRoute,
  path: "language",
  component: LanguagePage,
});

const providerRoute = createRoute({
  getParentRoute: () => settingsLayoutRoute,
  path: "provider",
  component: ProviderPage,
});

// The settings host contract, named for the generator's scan: contributed
// settings pages parent here, the way docks parent at the workspace route.
export const settingsRoute = settingsLayoutRoute;

// The capability route contract: every route this capability mounts under the
// shell root, as a const tuple. The generated table (web/lib/generated/
// routes.ts) imports this array; a capability without this file mounts
// nothing. The layout stands before its children, as a parent must in the
// composed table.
//
// The route consts stand on their own on purpose: a contextual type here
// (a `Route[]` annotation or satisfies) degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [
  settingsLayoutRoute,
  settingsIndexRoute,
  languageRoute,
  providerRoute,
] as const;
