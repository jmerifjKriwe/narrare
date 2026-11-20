import { queryOptions } from "@tanstack/react-query";
import { createRoute, redirect, Link, useParams } from "@tanstack/react-router";
import { lazy } from "react";

import { client } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";
import { rootRoute } from "@shell/routes/__root";

// React.lazy keeps the face out of the shell's bundle: it loads as its
// own chunk when the route opens, and the shell root's Suspense
// boundary covers the gap.
const TimelinePage = lazy(async () => {
  const page = await import("./TimelinePage");
  return { default: page.TimelinePage };
});

/**
 * The setup gate the planning surfaces share with the shelf, the workspace
 * and the knowledge pages: an unconfigured instance is handed to `/setup`
 * before the page mounts. The check is the public status endpoint asked
 * directly — a capability never imports another (rule 1), so the
 * coordination is the cache key (`["setup", "status"]`, the same entry
 * setup's write invalidates), not an import. `staleTime: Infinity` keeps
 * a remount on the cached answer; a fresh load asks anew. A non-ok
 * answer throws to the root's error screen.
 */
const setupStatusQueryOptions = queryOptions({
  queryKey: ["setup", "status"],
  staleTime: Infinity,
  queryFn: async () => {
    const { data, response } = await client.GET("/api/setup/status");
    if (!response.ok || !data) {
      throw new Error(`setup status unavailable: ${response.status}`);
    }
    return data.complete;
  },
});

/** The waiting face's route ids — the param read needs the literal. */
const PENDING_FROM = {
  storyboard: "/novels/$novelId/planning/storyboard",
  causality: "/novels/$novelId/planning/causality",
} as const;

/**
 * The honest waiting face of a registered route whose surface lands later
 * in this wave (the storyboard is W6 Task 4, the causality strip Task 5):
 * the URL is real and the sub-nav walks here, so the page says plainly
 * that the surface is still being built and holds the door back to the
 * chronology — the wave's gap discipline, never an invented face and
 * never a redirect that would hide the address.
 */
function PendingSurface({ area }: { area: "storyboard" | "causality" }) {
  const t = useTranslation();
  const { novelId } = useParams({ from: PENDING_FROM[area] });
  const titleKey = area === "storyboard" ? "planning.sub.storyboard" : "planning.sub.causality";
  usePageTitle(t(titleKey));
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-6">
      <div className="max-w-sm space-y-3 rounded-[var(--radius-surface)] border border-border bg-panel p-8 text-center">
        <span className="inline-block text-muted">
          <Icon name={area === "storyboard" ? "viewList" : "waves"} size={28} />
        </span>
        <h1 className="text-body font-semibold text-foreground">{t(titleKey)}</h1>
        <p className="text-meta text-muted">{t("planning.pending.note")}</p>
        <Link
          to="/novels/$novelId/planning/timeline"
          params={{ novelId }}
          className={`inline-flex items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container-high px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
        >
          {t("planning.pending.openTimeline")}
        </Link>
      </div>
    </div>
  );
}

function StoryboardPending() {
  return <PendingSurface area="storyboard" />;
}

function CausalityPending() {
  return <PendingSurface area="causality" />;
}

/**
 * The chronology (W6 Task 3) — the planning capability's first addressable
 * surface, a book-scoped page parented at the shell root (the knowledge
 * graph's precedent: a full path literal, not a child of the workspace
 * component, which renders its own columns and has no page-level Outlet).
 * The chrome resolves the active book from the route's own `novelId` param
 * on any book-scoped surface (chrome.ts), so the chronology wears the
 * book's breadcrumb exactly as the workspace does.
 */
const timelineRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/planning/timeline",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: TimelinePage,
});

/**
 * The storyboard's address (W6 Task 4): registered now so the sub-nav's
 * doors and the rail's active face are real from the first surface, with
 * the honest waiting face until its own task lands.
 */
const storyboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/planning/storyboard",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: StoryboardPending,
});

/**
 * The causality strip's address (W6 Task 5): the same mount shape and the
 * same waiting face.
 */
const causalityRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/novels/$novelId/planning/causality",
  beforeLoad: async () => {
    const complete = await queryClient.ensureQueryData(setupStatusQueryOptions);
    if (!complete) throw redirect({ to: "/setup" });
  },
  component: CausalityPending,
});

// The capability route contract: every route this capability mounts under
// the shell root, as a const tuple. The route consts stand on their own
// on purpose: a contextual type here degrades createRoute's inference to
// `any` paths, and with it the router's checked `to=` props.
export const routes = [timelineRoute, storyboardRoute, causalityRoute] as const;
