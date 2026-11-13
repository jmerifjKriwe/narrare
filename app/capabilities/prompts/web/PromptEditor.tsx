import { Fragment, useEffect, useId, useRef, useState } from "react";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";
import { Field, Textarea } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";

import { sideBySide } from "./diff";
import { reasonLabelOf } from "./promptLabels";

type PromptDetail = components["schemas"]["PromptDetail"];
type PromptDiff = components["schemas"]["PromptDiff"];

/** The two override tiers, as the API's `scope` field names them. */
type PromptScope = "global" | "novel";

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
export function PromptEditor(props: {
  promptKey: string;
  keyLabel: string;
  scope: PromptScope;
  novelId: string;
  novelTitle: string | null;
  focusNonce?: number;
  onClose: () => void;
  onSaved: () => void;
  onDirtyChange: (dirty: boolean) => void;
}) {
  const t = useTranslation();
  const {
    promptKey,
    keyLabel,
    scope,
    novelId,
    novelTitle,
    focusNonce,
    onClose,
    onSaved,
    onDirtyChange,
  } = props;
  const headingId = useId();
  const [detail, setDetail] = useState<PromptDetail | null>(null);
  const [detailFailed, setDetailFailed] = useState(false);
  const [content, setContent] = useState("");
  // The words the server last handed this editor: anything else is dirty and
  // asks before it is thrown away.
  const [snapshot, setSnapshot] = useState("");
  const [refusal, setRefusal] = useState<{ reason: string; detail: string } | null>(null);
  const [actionFailed, setActionFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [diff, setDiff] = useState<PromptDiff | "failed" | null>(null);
  // Bumped by the retry button: the one way a failed detail load asks again
  // without leaving the editor.
  const [attempt, setAttempt] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (focusNonce || attempt) textareaRef.current?.focus();
  }, [focusNonce, attempt]);

  // The detail load fills the editor's words: the text starts as the source
  // this scope would render with — the fork from an inherited tier happens on
  // visible words, never on a blank. A navigation away during the fetch must
  // not write into an unmounted editor; the flag is the smallest guard. The
  // novel id in the dependencies is the captured one, so a filter change on
  // the page cannot re-run this load under the editor.
  // biome-ignore lint/correctness/useExhaustiveDependencies: retry counter — `attempt` is the deliberate re-run key the retry button bumps (comment above); the load must not read it.
  useEffect(() => {
    let cancelled = false;
    setDetail(null);
    setDetailFailed(false);
    setRefusal(null);
    setActionFailed(false);
    setDiff(null);
    setContent("");
    setSnapshot("");
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
          setSnapshot(data.effective_content);
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

  // The page owns the guard; this editor only reports whether it holds words
  // the server does not.
  useEffect(() => {
    onDirtyChange(detail !== null && content !== snapshot);
  }, [detail, content, snapshot, onDirtyChange]);

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
              {...({ ref: textareaRef } as any)}
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
                          row.left === null ? "border-l-2 border-success pl-1" : "text-muted"
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
