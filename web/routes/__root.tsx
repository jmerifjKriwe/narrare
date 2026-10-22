import { createRootRoute, Outlet } from "@tanstack/react-router";
import { useEffect } from "react";

import { t } from "../lib/i18n";
import "../globals.css";

/** The one shell: every route renders inside it. */
function Shell() {
  useEffect(() => {
    document.title = t("app.title");
  }, []);

  return <Outlet />;
}

export const rootRoute = createRootRoute({ component: Shell });
