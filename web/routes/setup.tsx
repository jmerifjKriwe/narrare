import { createRoute, useNavigate } from "@tanstack/react-router";
import { useState } from "react";

import { client } from "../lib/api/client";
import { useTranslation } from "../lib/i18n";
import { rootRoute } from "./__root";

function SetupPage() {
  const t = useTranslation();
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [failed, setFailed] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") return;
    const { data, response } = await client.POST("/api/setup", {
      body: { novel_title: title },
    });
    if (!response.ok || !data) {
      setFailed(true);
      return;
    }
    void navigate({ to: "/novels/$id", params: { id: data.novel_id } });
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-4 py-10">
      <div className="rounded-lg border border-border bg-card p-8">
        <h1 className="text-2xl font-semibold tracking-tight">{t("setup.welcome")}</h1>
        <p className="mt-2 text-sm leading-relaxed text-muted">{t("setup.intro")}</p>
        <form onSubmit={submit} className="mt-6 flex flex-col gap-2">
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("setup.titleLabel")}
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              className="rounded-md border border-border bg-background px-3 py-2 text-base font-normal focus:border-primary focus:outline-none"
            />
          </label>
          {failed ? (
            <p role="alert" className="text-sm text-danger">
              {t("setup.failed")}
            </p>
          ) : null}
          <button
            type="submit"
            className="mt-2 self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          >
            {t("setup.submit")}
          </button>
        </form>
      </div>
    </main>
  );
}

export const setupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/setup",
  component: SetupPage,
});
