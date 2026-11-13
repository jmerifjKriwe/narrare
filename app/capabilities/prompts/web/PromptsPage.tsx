import { useEffect, useRef, useState } from "react";

import { useRouter } from "@tanstack/react-router";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { LeaveBlocker } from "@shell/components/LeaveBlocker";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Select } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

import { PromptCard } from "./PromptCard";

type PromptSummary = components["schemas"]["PromptSummary"];
type Novel = components["schemas"]["NovelRead"];

/** The two override tiers, as the API's `scope` field names them. */
type PromptScope = "global" | "novel";

/**
 * The prompts destination: every bundled key with its two override tiers, a
 * novel filter that scopes the views, and per scope an editor that speaks the
 * save gate's language. The novels list is fetched over HTTP like any other
 * page's data — the writing capability's code stays behind its router.
 * The settings area's frame owns the page's shape — the container and the
 * area's single <h1> — so this page is a section under an <h2>, like every
 * contributed settings page. The key blocks share one list panel: the
 * surface is the panel's, the rows' separators are rules.
 */
export function PromptsPage() {
  const t = useTranslation();
  // The tab's name: this page is "Prompts" for as long as it shows, and the
  // top bar's place indicator reads the same stack's top.
  usePageTitle(t("prompts.heading"));
  const [novels, setNovels] = useState<Novel[]>([]);
  const [novelId, setNovelId] = useState("");
  const [rows, setRows] = useState<PromptSummary[] | null>(null);
  const [listFailed, setListFailed] = useState(false);
  const [novelsFailed, setNovelsFailed] = useState(false);
  // The open editor carries the novel it was opened for — captured here, at
  // open time, so the filter's later moves cannot re-target its save or wipe
  // its words. A filter change leaves it exactly as it stands.
  const [editor, setEditor] = useState<{
    key: string;
    scope: PromptScope;
    novelId: string;
  } | null>(null);
  // Bumped when a save or reset lands, and by the page-level retry: the list
  // refetches through the effect instead of a handler patching rows by hand.
  const [refresh, setRefresh] = useState(0);
  // The open editor's words, reported up: re-targeting or leaving the page
  // must ask before they are thrown away. One ask stands at a time.
  const [editorDirty, setEditorDirty] = useState(false);
  const [guardOpen, setGuardOpen] = useState(false);
  const guardAnswer = useRef<((leave: boolean) => void) | null>(null);

  /** Resolve the standing ask; a dismissed dialog means "stay". */
  function settle(leave: boolean): void {
    const answer = guardAnswer.current;
    guardAnswer.current = null;
    setGuardOpen(false);
    answer?.(leave);
  }

  /** Ask before typed words are discarded; a second ask while one stands is a no. */
  function askToLeave(): Promise<boolean> {
    if (guardAnswer.current !== null) return Promise.resolve(false);
    setGuardOpen(true);
    return new Promise<boolean>((resolve) => {
      guardAnswer.current = resolve;
    });
  }

  async function closeEditor(): Promise<void> {
    if (editorDirty && !(await askToLeave())) return;
    setEditor(null);
    setEditorDirty(false);
  }

  async function openEditor(key: string, scope: PromptScope): Promise<void> {
    if (editor !== null && editorDirty && !(await askToLeave())) return;
    setEditor({ key, scope, novelId });
    setEditorDirty(false);
  }

  // The third door: a route change with a dirty editor asks too. The blocker
  // mounts only where a router exists, so the page stays renderable alone.
  const router = useRouter({ warn: false });

  // biome-ignore lint/correctness/useExhaustiveDependencies: re-run key — `refresh` is bumped by the page's retry and after a save or reset (comment above) to refetch; the load must not read it.
  useEffect(() => {
    // Both reads fail independently: a lost novels list must not also hide
    // the summaries that did arrive. A navigation away during the fetches
    // must not write into an unmounted page; the flag is the smallest guard.
    let cancelled = false;
    void (async () => {
      const [novelList, promptList] = await Promise.allSettled([
        client.GET("/api/writing/novels"),
        client.GET("/api/prompts", {
          params: { query: { novel_id: novelId === "" ? undefined : novelId } },
        }),
      ]);
      if (cancelled) return;
      if (novelList.status === "fulfilled" && novelList.value.response.ok) {
        setNovels(novelList.value.data ?? []);
        setNovelsFailed(false);
      } else {
        setNovelsFailed(true);
      }
      if (promptList.status === "fulfilled" && promptList.value.response.ok) {
        setRows(promptList.value.data ?? []);
        setListFailed(false);
      } else {
        setListFailed(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [novelId, refresh]);

  return (
    <section className="mt-8" aria-labelledby="settings-prompts-heading">
      <h2 id="settings-prompts-heading" className="text-emph font-semibold">
        {t("prompts.heading")}
      </h2>

      <Field label={t("prompts.filter")} className="mt-6 max-w-64">
        <Select
          value={novelId}
          onChange={(event) => setNovelId(event.target.value)}
        >
          <option value="">{t("prompts.filter.all")}</option>
          {novels.map((novel) => (
            <option key={novel.id} value={novel.id}>
              {novel.title}
            </option>
          ))}
        </Select>
      </Field>

      {listFailed ? (
        // The outage is named where the way back is: one alert, one press —
        // the effect asks both reads again, no reload demanded.
        <Notice
          tone="danger"
          live="alert"
          className="mt-4"
          action={
            <Button variant="secondary" onClick={() => setRefresh((current) => current + 1)}>
              {t("prompts.retry")}
            </Button>
          }
        >
          {t("prompts.errorLoad")}
        </Notice>
      ) : null}

      {novelsFailed ? (
        <Notice tone="danger" live="alert" className="mt-4">
          {t("prompts.errorLoadNovels")}
        </Notice>
      ) : null}

      {rows === null ? (
        listFailed ? null : (
          <Notice tone="quiet" live="status" className="mt-4">
            {t("prompts.loading")}
          </Notice>
        )
      ) : (
        <Panel className="mt-4">
          <ul className="flex flex-col">
            {rows.map((summary) => (
              <PromptCard
                key={summary.key}
                summary={summary}
                novelSelected={novelId !== ""}
                editor={
                  editor?.key === summary.key
                    ? {
                        scope: editor.scope,
                        novelId: editor.novelId,
                        novelTitle:
                          novels.find((novel) => novel.id === editor.novelId)?.title ?? null,
                      }
                    : null
                }
                onEdit={(scope) => void openEditor(summary.key, scope)}
                onClose={() => void closeEditor()}
                onDirtyChange={setEditorDirty}
                onSaved={() => {
                  setEditor(null);
                  setEditorDirty(false);
                  setRefresh((current) => current + 1);
                }}
              />
            ))}
          </ul>
        </Panel>
      )}

      {router ? <LeaveBlocker dirty={editorDirty} ask={askToLeave} /> : null}

      <Dialog
        title={t("save.leaveTitle")}
        isOpen={guardOpen}
        onOpenChange={(open) => {
          if (!open) settle(false);
        }}
      >
        {(close) => (
          <>
            <p className="mt-2 text-body text-muted">{t("dirty.confirmLeave")}</p>
            <div className="mt-4 flex justify-end gap-2">
              <Button
                variant="secondary"
                onClick={() => {
                  settle(false);
                  close();
                }}
              >
                {t("save.leaveStay")}
              </Button>
              <Button
                variant="primary"
                onClick={() => {
                  settle(true);
                  close();
                }}
              >
                {t("save.leaveGo")}
              </Button>
            </div>
          </>
        )}
      </Dialog>
    </section>
  );
}
