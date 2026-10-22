import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";

import { client } from "@shell/lib/api/client";
import { nav } from "@shell/lib/generated/capabilities";
import { useTranslation } from "@shell/lib/i18n";
import { useCreateNovel, useNovelsQuery } from "@shell/lib/query";

/** The novels page: the library, and the one field that starts a new novel. */
export function NovelsPage() {
  const t = useTranslation();
  const navigate = useNavigate();
  const novels = useNovelsQuery();
  const createNovel = useCreateNovel();
  const [title, setTitle] = useState("");
  const [failed, setFailed] = useState(false);
  const [ready, setReady] = useState(false);

  // The setup gate decides whether there is a library to list at all. Only
  // the novels themselves go through the query cache; this check cannot,
  // because its answer is "go somewhere else", not data.
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const status = await client.GET("/api/setup/status");
        if (cancelled) return;
        if (!status.response.ok) {
          // An answer that is not "ok" means no usable state. Showing an empty
          // list here would claim the instance holds nothing; say what failed.
          setFailed(true);
        } else if (status.data && !status.data.complete) {
          // Nothing to list yet: an uninstalled instance starts at setup.
          void navigate({ to: "/setup", replace: true });
          return;
        }
      } catch {
        // The local service is not answering at all and the proxy refuses.
        if (!cancelled) setFailed(true);
      }
      if (!cancelled) setReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, [navigate]);

  async function create(event: React.FormEvent) {
    event.preventDefault();
    if (title.trim() === "") return;
    try {
      // The list refreshes through the ["novels"] invalidation, not through
      // a reload here: the mutation owns that side of the contract.
      await createNovel.mutateAsync({ title });
    } catch {
      setFailed(true);
      return;
    }
    setTitle("");
  }

  // Nothing renders until the gate has answered and the list query has
  // settled: the page appears complete or reports the failure, never an
  // empty library that has not asked yet.
  if (!ready || novels.isPending) return null;

  const failedNow = failed || novels.isError;

  return (
    <div className="mx-auto max-w-2xl px-4 py-10">
      <h1 className="text-2xl font-semibold tracking-tight">{t("novels.heading")}</h1>
      <p className="mt-2 text-sm text-muted">
        {nav.map((entry, index) => (
          <span key={entry.id}>
            {index > 0 && <span aria-hidden="true"> · </span>}
            <Link to={entry.path} className="underline-offset-4 hover:underline">
              {t(entry.titleKey)}
            </Link>
          </span>
        ))}
      </p>
      {failedNow ? (
        <p role="alert" className="mt-6 text-sm text-danger">
          {t("novels.errorLoad")}
        </p>
      ) : (
        <>
          <form onSubmit={create} className="mt-6 flex flex-col gap-2">
            <label className="flex flex-col gap-1 text-sm font-medium">
              {t("novels.titleLabel")}
              <input
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                className="rounded-md border border-border bg-card px-3 py-2 text-base font-normal focus:border-primary focus:outline-none"
              />
            </label>
            <button
              type="submit"
              className="self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
            >
              {t("novels.create")}
            </button>
          </form>
          <ul className="mt-8 flex flex-col gap-2">
            {(novels.data ?? []).map((novel) => (
              <li key={novel.id} className="rounded-lg border border-border bg-card">
                <Link
                  to="/novels/$id"
                  params={{ id: novel.id }}
                  className="block px-4 py-3 underline-offset-4 hover:underline"
                >
                  {novel.title}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
