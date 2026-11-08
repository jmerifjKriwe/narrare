import { describe, expect, it } from "vitest";

import { router } from "../../../../web/router";
import { workspaceRouteId } from "../../../../web/lib/generated/workspace";

describe("the workspace route id", () => {
  it("names a route the shell router mounts", () => {
    expect(workspaceRouteId).not.toBeNull();
    expect(Object.keys(router.routesById)).toContain(workspaceRouteId);
  });
});
