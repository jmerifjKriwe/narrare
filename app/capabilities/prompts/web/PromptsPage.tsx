import { Fragment, useEffect, useId, useState } from "react";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { Button } from "@shell/ui/Button";
import { Field, Select, Textarea } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

type PromptSummary = components["schemas"]["PromptSummary"];
type PromptDetail = components["schemas"]["PromptDetail"];
type PromptDiff = components["schemas"]["PromptDiff"];
type Novel = components["schemas"]["NovelRead"];

/** The two override tiers, as the API's `scope` field names them. */
type PromptScope = "global" | "novel";

/**
 * The key labels the catalog carries, keyed by prompt key. The list of keys
 * comes from the server (the kernel registry); this map only supplies words.
 * A key the frontend has never heard of still renders, labelled by
 * `prompts.key.unknown`, which is the point of the endpoint: the registry is
 * the only list. The labels are the task names the settings page already
 * carries — one set of words for one registry key.
 */
const KEY_LABELS: Record<string, MessageKey> = {
  "writing.continuation": "settings.task.writing.continuation",
  "chat.ask": "settings.task.chat.ask",
  "knowledge.extract-entities": "settings.task.knowledge.extract-entities",
  "knowledge.check-consistency": "settings.task.knowledge.check-consistency",
};

/**
 * The refusal vocabulary's labels: the render's own reasons beside the save
 * gate's scope rules. A reason outside the map still renders — as the raw
 * word the server named — so a new refusal is never a blank.
 */
const REASON_LABELS: Record<string, MessageKey> = {
  syntax: "prompts.reason.syntax",
  "undefined-variable": "prompts.reason.undefined-variable",
  "include-depth": "prompts.reason.include-depth",
  "include-cycle": "prompts.reason.include-cycle",
  "include-missing": "prompts.reason.include-missing",
  forbidden: "prompts.reason.forbidden",
  runtime: "prompts.reason.runtime",
  budget: "prompts.reason.budget",
  "novel-scope": "prompts.reason.novel-scope",
  "unknown-novel": "prompts.reason.unknown-novel",
  contract: "prompts.reason.contract",
};

/** The `t` the hooks hand out, named so helpers can take it as a parameter. */
type Translate = ReturnType<typeof useTranslation>;

function keyLabelOf(key: string, t: Translate): string {
  const label = KEY_LABELS[key];
  return label === undefined ? t("prompts.key.unknown") : t(label);
}

function reasonLabelOf(reason: string, t: Translate): string {
  const label = REASON_LABELS[reason];
  return label === undefined ? reason : t(label);
}

/**
 * The save gate's refusal body. A refused write answers 422 with
 * `{ reason, detail }`; a request that failed validation answers with the
 * framework's body — the typed client carries both as a union, and this
 * guard narrows which one arrived before the page renders a reason.
 */
function refusalOf(error: unknown): { reason: string; detail: string } | null {
  const body = (error as { detail?: unknown } | null | undefined)?.detail;
  if (body === null || typeof body !== "object") return null;
  const { reason, detail } = body as { reason?: unknown; detail?: unknown };
  if (typeof reason !== "string") return null;
  return { reason, detail: typeof detail === "string" ? detail : "" };
}

/** One aligned pair of the side-by-side diff: a side without a line has none. */
type DiffRow = { left: string | null; right: string | null };

/**
 * The two texts as aligned line pairs, by the longest common subsequence —
 * the whole of the diff view, dependency-free by the plan's constraint.
 * Templates are short, so the quadratic table stays cheap.
 */
function sideBySide(bundled: string, override: string): DiffRow[] {
  const left = bundled.split("\n");
  const right = override.split("\n");
  const common: number[][] = Array.from({ length: left.length + 1 }, () =>
    new Array<number>(right.length + 1).fill(0),
  );
  for (let i = left.length - 1; i >= 0; i--) {
    for (let j = right.length - 1; j >= 0; j--) {
      common[i][j] =
        left[i] === right[j]
          ? common[i + 1][j + 1] + 1
          : Math.max(common[i + 1][j], common[i][j + 1]);
    }
  }
  const rows: DiffRow[] = [];
  let i = 0;
  let j = 0;
  while (i < left.length && j < right.length) {
    if (left[i] === right[j]) {
      rows.push({ left: left[i], right: right[j] });
      i++;
      j++;
    } else if (common[i + 1][j] >= common[i][j + 1]) {
      rows.push({ left: left[i], right: null });
      i++;
    } else {
      rows.push({ left: null, right: right[j] });
      j++;
    }
  }
  while (i < left.length) {
    rows.push({ left: left[i], right: null });
    i++;
  }
  while (j < right.length) {
    rows.push({ left: null, right: right[j] });
    j++;
  }
  return rows;
}

/** A scope chip: the name of the tier the lines under it speak about. */
function Chip({ children }: { children: string }) {
  return <span className="rounded-full bg-panel px-2 py-0.5 text-label">{children}</span>;
}

/**
 * The editor for one scope of one key: the variable legend, the text prefilled
 * with the scope's effective source, the save-time refusals by name, the
 * reset of the scope it was opened from, and the side-by-side diff. The body
 * of a save names its scope — `novel_id` present for the novel tier, absent
 * for the global one — which is what keeps a novel edit off the global row.
 *
 * The novel the editor writes is captured at open time and named in the
 * heading: the page's novel filter can move on while the editor stands, and
 * neither the typed words nor the write's target may follow it.
 */
function PromptEditor(props: {
  promptKey: string;
  keyLabel: string;
  scope: PromptScope;
  novelId: string;
  novelTitle: string | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useTranslation();
  const { promptKey, keyLabel, scope, novelId, novelTitle, onClose, onSaved } = props;
  const headingId = useId();
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [detailFailed, setDetailFailed] = useState(false);
  const [content, setContent] = useState("");
  const [refusal, setRefusal] = useState<{ reason: string; detail: string } | null>(null);
  const [actionFailed, setActionFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [diff, setDiff] = useState<PromptDiff | "failed" | null>(null);
  // Bumped by the retry button: the one way a failed detail load asks again
  // without leaving the editor.
  const [attempt, setAttempt] = useState(0);

  // The detail load fills the editor's words: the text starts as the source
  // this scope would render with — the fork from an inherited tier happens on
  // visible words, never on a blank. A navigation away during the fetch must
  // not write into an unmounted editor; the flag is the smallest guard. The
  // novel id in the dependencies is the captured one, so a filter change on
  // the page cannot re-run this load under the editor.
  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setDetailFailed(false);
    setRefusal(null);
    setActionFailed(false);
    setDiff(null);
    setContent("");
    client
      .GET("/api/prompts/{key}", {
        params: {
          path: { key: promptKey },
          ...(scope === "novel" ? { query: { novel_id: novelId } } : {}),
        },
      })
      .then(({ data, response }) => {
        if (cancelled) return;
        if (response.ok && data !== undefined) {
          setDetail(data);
          setContent(data.effective_content);
        } else {
          setDetailFailed(true);
        }
      })
      .catch(() => {
        if (!cancelled) setDetailFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [promptKey, scope, novelId, attempt]);

  async function save(): Promise<void> {
    setBusy(true);
    setRefusal(null);
    setActionFailed(false);
    try {
      const { data, error, response } = await client.PUT("/api/prompts/{key}", {
        params: { path: { key: promptKey } },
        body: { content, ...(scope === "novel" ? { novel_id: novelId } : {}) },
      });
      if (response.ok && data !== undefined) {
        onSaved();
        return;
      }
      const refused = response.status === 422 ? refusalOf(error) : null;
      if (refused !== null) {
        setRefusal(refused);
        return;
      }
      setActionFailed(true);
    } catch {
      // A rejected fetch has no response to inspect: the editor still says
      // so, in the same place a server-reachable failure appears.
      setActionFailed(true);
    } finally {
      setBusy(false);
    }
  }

  async function reset(): Promise<void> {
    setBusy(true);
    setRefusal(null);
    setActionFailed(false);
    try {
      const { error, response } = await client.DELETE("/api/prompts/{key}", {
        params: {
          path: { key: promptKey },
          ...(scope === "novel" ? { query: { novel_id: novelId } } : {}),
        },
      });
      if (response.ok) {
        onSaved();
        return;
      }
      const refused = response.status === 422 ? refusalOf(error) : null;
      if (refused !== null) {
        setRefusal(refused);
        return;
      }
      setActionFailed(true);
    } catch {
      setActionFailed(true);
    } finally {
      setBusy(false);
    }
  }

  async function toggleDiff(): Promise<void> {
    if (diff !== null) {
      setDiff(null);
      return;
    }
    try {
      const { data, response } = await client.GET("/api/prompts/{key}/diff", {
        params: {
          path: { key: promptKey },
          ...(scope === "novel" ? { query: { novel_id: novelId } } : {}),
        },
      });
      setDiff(response.ok && data !== undefined ? data : "failed");
    } catch {
      setDiff("failed");
    }
  }

  // The reset is offered only where this scope's own tier carries the
  // override: resetting a scope that inherits would be a no-op dressed as
  // an action. The other tier is never touched, server-side or here.
  const resettable =
    detail !== null && detail.override !== null && detail.override.scope === scope;
  // The novel editor names the novel it writes, not just the tier: the
  // filter on the page may since have moved, and the target must not.
  const scopeName =
    scope === "global" || novelTitle === null
      ? t(scope === "global" ? "prompts.scope.global" : "prompts.scope.novel")
      : novelTitle;

  return (
    // The editor sits on a rule of its own inside the key's block — the
    // separation is a rule, never a second box inside the card (L3, L5).
    <section aria-labelledby={headingId} className="mt-3 border-t border-rule pt-3">
      <h3 id={headingId} className="text-body font-semibold">
        {keyLabel} · {scopeName}
      </h3>
      {detail === null ? (
        detailFailed ? (
          <>
            <Notice tone="danger" live="alert" className="mt-2">
              {t("prompts.editor.detailFailed")}
            </Notice>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button variant="secondary" onClick={() => setAttempt((current) => current + 1)}>
                {t("prompts.editor.retry")}
              </Button>
              <Button variant="secondary" onClick={onClose}>
                {t("prompts.editor.cancel")}
              </Button>
            </div>
          </>
        ) : (
          <Notice tone="quiet" live="status" className="mt-2">
            {t("prompts.loading")}
          </Notice>
        )
      ) : (
        <>
          <div className="mt-2">
            <h4 className="text-label font-semibold uppercase tracking-[0.1em] text-muted">
              {t("prompts.legend")}
            </h4>
            <ul className="mt-1 list-disc pl-5 text-label text-muted">
              {detail.variables.map((variable) => (
                <li key={variable.name}>
                  {t("prompts.variable", { name: variable.name, example: variable.example })}
                </li>
              ))}
            </ul>
          </div>
          <Field label={t("prompts.editor.contentLabel")} className="mt-3">
            {/* The template keeps the mono face: it is code the render
                executes, not prose the reader reads. */}
            <Textarea
              value={content}
              onChange={(event) => setContent(event.target.value)}
              rows={10}
              className="font-mono"
            />
          </Field>
          {refusal !== null ? (
            <Notice tone="danger" live="alert" className="mt-2">
              {t("prompts.saveRefused", {
                reason: reasonLabelOf(refusal.reason, t),
                detail: refusal.detail,
              })}
            </Notice>
          ) : null}
          {actionFailed ? (
            <Notice tone="danger" live="alert" className="mt-2">
              {t("prompts.errorAction")}
            </Notice>
          ) : null}
          {diff === null ? null : diff === "failed" ? (
            <Notice tone="danger" live="alert" className="mt-2">
              {t("prompts.editor.diffFailed")}
            </Notice>
          ) : (
            <div className="mt-3">
              <div className="grid grid-cols-2 gap-2 text-label font-semibold text-muted">
                <h4>{t("prompts.diff.bundled")}</h4>
                <h4>{t("prompts.diff.override")}</h4>
              </div>
              {diff.override_content === null ? (
                <p className="mt-2 text-label text-muted">{t("prompts.diff.none")}</p>
              ) : (
                <div className="mt-1 grid grid-cols-2 gap-2 font-mono text-label">
                  {sideBySide(diff.bundled_content, diff.override_content).map((row, index) => (
                    <Fragment key={index}>
                      <pre
                        className={`min-w-0 break-words whitespace-pre-wrap ${
                          row.right === null ? "border-l-2 border-danger pl-1" : "text-muted"
                        }`}
                      >
                        {row.left}
                      </pre>
                      <pre
                        className={`min-w-0 break-words whitespace-pre-wrap ${
                          row.left === null ? "border-l-2 border-primary pl-1" : "text-muted"
                        }`}
                      >
                        {row.right}
                      </pre>
                    </Fragment>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="mt-3 flex flex-wrap gap-2">
            {/* The save is this screen's one filled primary (L1); every
                companion action — diff, reset, cancel — is a bordered
                equal. */}
            <Button variant="primary" disabled={busy} onClick={() => void save()}>
              {t("prompts.editor.save")}
            </Button>
            <Button variant="secondary" onClick={() => void toggleDiff()}>
              {diff === null ? t("prompts.editor.diff") : t("prompts.editor.hideDiff")}
            </Button>
            {resettable ? (
              <Button variant="secondary" disabled={busy} onClick={() => void reset()}>
                {t("prompts.editor.reset")}
              </Button>
            ) : null}
            <Button variant="secondary" onClick={onClose}>
              {t("prompts.editor.cancel")}
            </Button>
          </div>
        </>
      )}
    </section>
  );
}

/**
 * One key's block: the two scope chips with their honest state lines, the
 * explicit actions, and the editor when one of this key's scopes is open.
 * Every fact comes from the summary row — the page mints none of its own.
 * The blocks are rows of one list panel, separated by rules — never cards
 * inside the card (L5).
 */
function PromptCard(props: {
  summary: PromptSummary;
  novelSelected: boolean;
  editor: { scope: PromptScope; novelId: string; novelTitle: string | null } | null;
  onEdit: (scope: PromptScope) => void;
  onClose: () => void;
  onSaved: () => void;
}) {
  const t = useTranslation();
  const { summary, novelSelected, editor, onEdit, onClose, onSaved } = props;
  const label = keyLabelOf(summary.key, t);
  return (
    <li className="border-b border-rule py-3 first:pt-0 last:border-b-0 last:pb-0">
      <h2 className="flex flex-wrap items-baseline gap-2 text-body font-medium">
        {label}
        <code className="text-label font-normal text-muted">{summary.key}</code>
      </h2>
      <p className="mt-1 text-body text-muted">{summary.bundled_summary}</p>

      <div className="mt-3 flex flex-col gap-3">
        <div>
          <Chip>{t("prompts.scope.global")}</Chip>
          <p className="mt-1 text-label text-muted">
            {summary.override_global
              ? t("prompts.globalOverridden")
              : t("prompts.globalBundled")}
          </p>
          <div className="mt-2">
            <Button variant="secondary" onClick={() => onEdit("global")}>
              {t("prompts.edit")}
            </Button>
          </div>
        </div>
        {summary.novel_scopable ? (
          <div>
            <Chip>{t("prompts.scope.novel")}</Chip>
            {novelSelected ? (
              <>
                <p className="mt-1 text-label text-muted">
                  {summary.override_novel
                    ? t("prompts.novelOverridden")
                    : t("prompts.inherits", {
                        state: summary.override_global
                          ? t("prompts.inheritsFrom.global")
                          : t("prompts.inheritsFrom.bundled"),
                      })}
                </p>
                <div className="mt-2">
                  <Button variant="secondary" onClick={() => onEdit("novel")}>
                    {summary.override_novel ? t("prompts.editNovel") : t("prompts.create")}
                  </Button>
                </div>
              </>
            ) : (
              <p className="mt-1 text-label text-muted">{t("prompts.pickNovel")}</p>
            )}
          </div>
        ) : null}
      </div>

      {editor === null ? null : (
        <PromptEditor
          promptKey={summary.key}
          keyLabel={label}
          scope={editor.scope}
          novelId={editor.novelId}
          novelTitle={editor.novelTitle}
          onClose={onClose}
          onSaved={onSaved}
        />
      )}
    </li>
  );
}

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
  usePageTitle(t("prompts.settingsTitle"));
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
      <h2 id="settings-prompts-heading" className="text-lg font-semibold">
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
                onEdit={(scope) => setEditor({ key: summary.key, scope, novelId })}
                onClose={() => setEditor(null)}
                onSaved={() => {
                  setEditor(null);
                  setRefresh((current) => current + 1);
                }}
              />
            ))}
          </ul>
        </Panel>
      )}
    </section>
  );
}
