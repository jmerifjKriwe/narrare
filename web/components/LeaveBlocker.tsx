import { useBlocker } from "@tanstack/react-router";

/**
 * A route's leave guard, as a component rather than a hook call in the page.
 *
 * `useBlocker` reads the router from context and throws without one; the
 * component tests render a page alone, with no route to leave. Mounting this
 * only where a router exists keeps the page testable and the guard real — a
 * conditional hook call could not.
 */
export function LeaveBlocker({
  dirty,
  ask,
}: {
  dirty: boolean;
  ask: () => Promise<boolean>;
}) {
  useBlocker({
    shouldBlockFn: async () => (dirty ? !(await ask()) : false),
    enableBeforeUnload: () => dirty,
  });
  return null;
}
