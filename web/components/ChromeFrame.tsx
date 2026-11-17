/**
 * The chrome frame (W4 Task 10, D15): the app-wide rail + topbar around
 * the post-setup surfaces — the shelf today, the workspace from Task 11.
 * The welcome and the wizard stay standalone (their drafts are chrome-less
 * guided flows); the shell root passes the mode per route.
 *
 * The geometry is the light stage's: the topbar spans the page above the
 * rail (its left group indented by `--rail-width` so the breadcrumb sits
 * on the content axis), the rail stands the body's full height at the
 * collapsed width and glides open as an elevated overlay — the content
 * column never moves (DESIGN.md's rail engine). The page scrolls inside
 * the one main landmark; the chrome stays.
 *
 * The main landmark sits at a CONSTANT tree depth in both modes, the
 * chrome parts conditional siblings around it: the router's pathname
 * flips before its matches swap mid-navigation, and a branch that moved
 * the outlet would remount the page being left — re-firing its effects
 * (the provisioning step's one POST among them). Standalone, the wrappers
 * are `display: contents` — layout-transparent, the guided flows full-bleed
 * exactly as before.
 */
import { Suspense, type ReactNode } from "react";

import { IconRail } from "./IconRail";
import { TopBar } from "./TopBar";

export function ChromeFrame({
  standalone = false,
  children,
}: {
  /** The guided flows (`/setup/*`) wear no chrome. */
  standalone?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={standalone ? "contents" : "flex h-dvh flex-col"}>
      {!standalone && <TopBar />}
      <div className={standalone ? "contents" : "flex flex-1 overflow-hidden"}>
        {/* The rail's offset: the collapsed width on a fine pointer, the
            open rail's own where there is no hover (the token's media). */}
        {!standalone && (
          <div className="relative w-[var(--rail-width)] shrink-0">
            <IconRail />
          </div>
        )}
        {/* The shell owns the page's one main landmark; routes render
            content inside it. tabIndex makes the landing hold focus —
            fragment navigation focuses a target only if it can. Capability
            pages load lazily, each as its own bundle chunk; the one
            boundary lives in the shell so no capability needs one, and the
            fallback is null on purpose — the gap while a chunk arrives
            stays quiet. */}
        <main id="main" tabIndex={0} className={standalone ? undefined : "flex-1 overflow-y-auto"}>
          <Suspense fallback={null}>{children}</Suspense>
        </main>
      </div>
    </div>
  );
}
