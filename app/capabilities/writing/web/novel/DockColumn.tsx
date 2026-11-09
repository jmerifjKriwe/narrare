import { Outlet } from "@tanstack/react-router";

import { docks } from "@shell/lib/generated/docks";
import { useTranslation } from "@shell/lib/i18n";

type DockRow = (typeof docks)[number];

export function DockColumn({
  openDock,
  railOverlay,
}: {
  openDock: DockRow;
  railOverlay: boolean;
}) {
  const t = useTranslation();
  return (
    <aside
      /* Same contract as the rail, mirrored: a drawer from the
         right below 1024, the desktop's dock column at ≥1024. The
         352 the dock takes are the arithmetic's own; the column's
         16 px padding is the gap the card's ring needs. The column is
         a flex
         stack so the title holds its place while the body under it
         takes the remaining height and scrolls alone. The rail's
         drawer sits a z-step above this one: a rail opened over a
         live dock covers it without unmounting it, so the dock's
         in-progress ask survives behind the drawer — and while it is
         covered the dock goes `inert`, so the keyboard cannot land on
         controls the drawer hides. */
      className="flex w-88 shrink-0 flex-col rounded-[var(--radius-lg)] border border-rule bg-panel p-4 max-lg:absolute max-lg:top-0 max-lg:bottom-0 max-lg:right-0 max-lg:z-20 max-lg:max-w-full max-lg:shadow-overlay lg:max-h-[calc(100dvh-16rem)] lg:pl-6"
      aria-label={t(openDock.titleKey)}
      inert={railOverlay || undefined}
    >
      <h2 className="text-emph font-semibold tracking-tight">{t(openDock.titleKey)}</h2>
      {/* The dock owns its scroll: it takes the height it needs up to
          the viewport's own cap (the rail's arithmetic), and the body
          under the title scrolls inside it. A fixed 50 vh window used
          to cut a row in half while 200 px of the page stood unused. */}
      <div className="mt-3 min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </aside>
  );
}
