/**
 * The prompt editor (W8 Task 12): the drafted right-hand column of the
 * `ai-prompts-overrides` authority — the scope chips (the novel chip only
 * where the key is scopable), the state info card per override state, the
 * variable legend (click = insert at the cursor), the draft textarea beside
 * the read-only bundled reference, the Ablehnungsgründe expander, and the
 * toolbar: the diff (the saved tiers, asked from the endpoint), the reset
 * with its one-time confirmation, the provider-free preview riding Task
 * 11's POST, the live test whose warning precedes the call, and the save
 * through the gate.
 *
 * Porting dispositions from the Stitch round — the honest-state rules:
 * - No „Prüfung erfolgreich“ bar while idle: no client-side Jinja check
 *   exists, and a success line without a check is a lie. The expander's
 *   refusal grounds stand instead; the preview's and the save's outcomes
 *   are the checks the faces answer on.
 * - No token estimate in the diagnostics: no read answers it (the
 *   diagnostics carry chars and lines) — the draft's „~214 Tokens“ is an
 *   invented number.
 * - No per-variable „Herkunft“ labels: the provenance the API answers is
 *   `{name, value, used}` — the used mark is the honest fact.
 * - The live test's context names the provider KIND, never a model
 *   marketing name: the fake wears its honest mark, a named driver its
 *   kind.
 */
import { useEffect, useMemo, useRef, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { FOCUS } from "@shell/ui/card";
import { Icon, type IconName } from "@shell/ui/icons";

import {
  startLiveTest,
  usePreviewPrompt,
  usePromptDiff,
  useResetPrompt,
  useSavePrompt,
  type LiveTestContext,
  type WireError,
} from "./promptsQuery";
import { RefusalFace } from "./refusal";

const SERIF = "[font-family:var(--font-serif)]";
const MONO = "[font-family:var(--font-mono)]";

const CHIP =
  `rounded px-2.5 py-1 text-meta font-medium transition-colors ${FOCUS}`;
const TOOLBAR_BUTTON =
  `inline-flex items-center gap-1.5 rounded border border-border bg-panel px-3 py-1.5 text-meta font-semibold text-foreground shadow-sm transition-colors hover:bg-soft ${FOCUS}`;
const PRIMARY_BUTTON =
  `inline-flex items-center gap-1.5 rounded bg-primary px-3.5 py-1.5 text-meta font-semibold text-primary-foreground shadow-sm transition-colors hover:bg-primary/90 ${FOCUS}`;
const TEXTAREA =
  `min-h-56 w-full resize-y rounded border border-border bg-surface p-3 text-meta leading-relaxed text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus ${FOCUS}`;

/** The bundled keys' glyphs, in the draft's icon order. The registry's key
 *  set is closed; an unknown key answers no glyph (it never mounts). */
const KEY_ICONS: Readonly<Record<string, IconName>> = {
  "writing.continuation": "editNote",
  "chat.ask": "chat",
  "knowledge.extract-entities": "knowledge",
  "knowledge.check-consistency": "balance",
};

/** The context frame's fact keys the catalogs localize; anything else the
 *  frame names prints raw — the backend's own word, never a wrong label. */
const FACT_KEYS: ReadonlySet<string> = new Set(["novel", "chapter", "scene", "question", "passages"]);

export interface EditorScope {
  /** The tier the editor edits: the novel's own or the global one. */
  tier: "novel" | "global";
  /** The novel the novel tier names; null on the global tier. */
  novelId: string | null;
  /** The novel's display name; null on the global tier. */
  novelTitle: string | null;
  /** Whether the novel chip stands at all: a scopable key AND a novel
   *  filtered in the Geltungsbereich — the chip switches the tier, so it
   *  stays visible on the global tier too. */
  novelChip: boolean;
  /** The filtered novel's display name, for the chip's label. */
  filteredNovelTitle: string | null;
}

export function PromptEditor(props: {
  promptKey: string;
  detail: {
    bundled_content: string;
    variables: { name: string; example: string }[];
    override: { scope: string; content: string } | null;
    effective_content: string;
  };
  scope: EditorScope;
  onScopeChange: (tier: "novel" | "global") => void;
}) {
  const t = useTranslation();
  const { promptKey, detail, scope } = props;

  // The draft: the override in force when one stands, the effective source
  // otherwise — the baseline the dirty check compares against. The reset to
  // this baseline rides the component's own identity: the page keys the
  // editor on the key+scope, so a tier or key switch REMOUNTS and the draft
  // starts at the new tier's baseline. A refetch that lands mid-typing (the
  // save's invalidation, the bytes changing under the cursor) never
  // clobbers the draft — keystrokes belong to their author.
  const baseline = detail.override !== null ? detail.override.content : detail.effective_content;
  const [draft, setDraft] = useState(baseline);
  const [savedFace, setSavedFace] = useState(false);
  const [saveFailure, setSaveFailure] = useState<WireError | null>(null);
  const [confirmReset, setConfirmReset] = useState(false);
  const [diffOpen, setDiffOpen] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const novelId = scope.tier === "novel" ? scope.novelId : null;
  const diff = usePromptDiff(promptKey, novelId, diffOpen);
  const save = useSavePrompt();
  const reset = useResetPrompt();
  const preview = usePreviewPrompt();

  const dirty = draft !== baseline;

  function insertVariable(name: string): void {
    const textarea = textareaRef.current;
    if (textarea === null) {
      setDraft((current) => `${current}{{${name}}}`);
      return;
    }
    const at = textarea.selectionStart ?? draft.length;
    const next = `${draft.slice(0, at)}{{${name}}}${draft.slice(textarea.selectionEnd ?? at)}`;
    setDraft(next);
    // The inserted marker lands under the cursor, where the click promised.
    requestAnimationFrame(() => {
      textarea.focus();
      const position = at + name.length + 4;
      textarea.setSelectionRange(position, position);
    });
  }

  function runSave(): void {
    setSavedFace(false);
    setSaveFailure(null);
    save.mutate(
      { key: promptKey, content: draft, novelId },
      {
        onSuccess: () => setSavedFace(true),
        onError: (cause) => setSaveFailure(cause),
      },
    );
  }

  function runReset(): void {
    reset.mutate(
      { key: promptKey, novelId },
      {
        onSuccess: (fresh) => {
          setConfirmReset(false);
          setSavedFace(false);
          setSaveFailure(null);
          // The reset deleted the override; the draft follows the tier's
          // inherited baseline the fresh detail answers. The editor's
          // identity does not change on a reset, so nothing else would move
          // it — and Save would recreate the row the user just removed.
          setDraft(fresh.override !== null ? fresh.override.content : fresh.effective_content);
        },
        onError: (cause) => setSaveFailure(cause),
      },
    );
  }

  function runPreview(): void {
    preview.mutate({ key: promptKey, novelId, draft: dirty ? draft : null });
  }

  const lineCount = draft === "" ? 0 : draft.split("\n").length;

  return (
    <section
      data-testid="prompts-editor"
      aria-label={t("prompts.editor.scope.label")}
      className="space-y-4"
    >
      <div className="rounded-lg border border-border bg-panel p-5 shadow-sm">
        {/* Title, identifier and the scope chips. */}
        <div className="flex flex-col gap-3 border-b border-border/60 pb-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <h2 className={`${SERIF} text-2xl font-bold text-foreground`}>
                <span className="me-2 inline-flex align-middle text-primary">
                  <Icon name={KEY_ICONS[promptKey] ?? "document"} size={18} />
                </span>
                {t(`prompts.key.${promptKey}` as Parameters<typeof t>[0])}
              </h2>
              <span className={`${MONO} rounded border border-border bg-surface px-2 py-0.5 text-xs text-muted`} data-testid="editor-key">
                {promptKey}
              </span>
            </div>
            <p className="mt-1 text-meta text-muted">
              {t(`prompts.key.${promptKey}.desc` as Parameters<typeof t>[0])}
            </p>
          </div>

          <div
            role="group"
            aria-label={t("prompts.editor.scope.label")}
            className="flex items-center gap-1.5 self-start rounded border border-border bg-surface p-1 sm:self-auto"
          >
            <button
              type="button"
              data-testid="scope-chip-global"
              aria-pressed={scope.tier === "global"}
              onClick={() => props.onScopeChange("global")}
              className={`${CHIP} ${scope.tier === "global" ? "bg-primary font-semibold text-primary-foreground shadow-sm" : "text-muted hover:text-foreground"}`}
            >
              {t("prompts.editor.scope.global")}
            </button>
            {scope.novelChip && scope.filteredNovelTitle !== null && (
              <button
                type="button"
                data-testid="scope-chip-novel"
                aria-pressed={scope.tier === "novel"}
                onClick={() => props.onScopeChange("novel")}
                className={`${CHIP} ${scope.tier === "novel" ? "bg-primary font-semibold text-primary-foreground shadow-sm" : "text-muted hover:text-foreground"}`}
              >
                {t("prompts.editor.scope.novel", { novel: scope.filteredNovelTitle })}
              </button>
            )}
          </div>
        </div>

        {/* The state info card: the override facts of the tier under edit. */}
        <div className="mt-3 rounded border border-border bg-surface p-3 text-meta text-foreground" data-testid="editor-state">
          {detail.override !== null && detail.override.scope === "novel" ? (
            <p>{t("prompts.editor.overrideActive.novel", { novel: scope.novelTitle ?? "" })}</p>
          ) : detail.override !== null ? (
            <p>{t("prompts.editor.overrideActive.global")}</p>
          ) : scope.tier === "novel" ? (
            <p>{t("prompts.editor.inherit.body")}</p>
          ) : (
            <p className="text-muted">{t("prompts.sovereign.body")}</p>
          )}
        </div>

        {/* The variable legend: click inserts the marker at the cursor. */}
        <div className="mt-3 space-y-1.5" data-testid="variables-legend">
          <div className="text-meta font-semibold text-muted">{t("prompts.editor.variables.label")}</div>
          <div className="flex flex-wrap items-center gap-2">
            {detail.variables.map((variable) => (
              <button
                key={variable.name}
                type="button"
                title={t("prompts.editor.variables.insert")}
                onClick={() => insertVariable(variable.name)}
                className={`${MONO} inline-flex items-center gap-1 rounded border border-border bg-surface px-2 py-1 text-xs text-primary transition-colors hover:bg-soft ${FOCUS}`}
              >
                <span className="font-bold">{`{{${variable.name}}}`}</span>
                <span className="text-muted">„{variable.example}“</span>
              </button>
            ))}
          </div>
        </div>

        {/* The two panes: the read-only bundled reference, the draft. */}
        <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-12">
          <div className="flex flex-col overflow-hidden rounded border border-border bg-surface md:col-span-5">
            <div className="flex items-center justify-between border-b border-border bg-soft px-3 py-2">
              <span className="text-meta font-semibold text-foreground">{t("prompts.editor.bundled.title")}</span>
              <span className="rounded border border-border bg-panel px-1.5 py-0.5 text-[10px] font-medium text-muted">
                {t("prompts.editor.bundled.readonly")}
              </span>
            </div>
            <pre className={`${MONO} flex-1 overflow-x-auto whitespace-pre-wrap p-3 text-xs leading-relaxed text-muted`}>
              {detail.bundled_content}
            </pre>
          </div>

          <div className="flex flex-col overflow-hidden rounded border border-primary bg-panel shadow-sm md:col-span-7">
            <div className="flex items-center justify-between border-b border-border bg-surface px-3 py-2">
              <span className="text-meta font-semibold text-primary">
                {scope.tier === "novel" && scope.novelTitle !== null
                  ? t("prompts.editor.draft.title.novel", { novel: scope.novelTitle })
                  : t("prompts.editor.draft.title.global")}
              </span>
              <span className={`${MONO} text-[11px] text-muted`} data-testid="draft-meta">
                {t("prompts.editor.draft.meta", { count: lineCount })}
              </span>
            </div>
            <div className="p-3">
              <textarea
                ref={textareaRef}
                data-testid="draft-textarea"
                aria-label={
                  scope.tier === "novel" && scope.novelTitle !== null
                    ? t("prompts.editor.draft.title.novel", { novel: scope.novelTitle })
                    : t("prompts.editor.draft.title.global")
                }
                spellCheck={false}
                value={draft}
                onChange={(event) => {
                  setDraft(event.target.value);
                  setSavedFace(false);
                }}
                className={TEXTAREA}
              />
            </div>
          </div>
        </div>

        {/* The save face and the refusal family; the Ablehnungsgründe. */}
        <div className="mt-3 space-y-2" data-testid="refusal-reasons">
          {savedFace && (
            <p className="rounded border border-success/40 bg-panel p-2.5 text-meta font-semibold text-success" role="status" data-testid="saved-face">
              {t("prompts.saved")}
            </p>
          )}
          {saveFailure !== null && <RefusalFace failure={saveFailure} />}
          {save.isPending && <p className="text-meta text-muted">{t("prompts.editor.save.busy")}</p>}
          <details className="rounded border border-border bg-surface p-3 text-meta">
            <summary className="cursor-pointer text-muted transition-colors hover:text-foreground">
              {t("prompts.reasons.title")}
            </summary>
            <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
              <ReasonTile title={t("prompts.reasons.syntax.title")} body={t("prompts.reasons.syntax.body")} />
              <ReasonTile title={t("prompts.reasons.variable.title")} body={t("prompts.reasons.variable.body")} />
              <ReasonTile title={t("prompts.reasons.cycle.title")} body={t("prompts.reasons.cycle.body")} />
              <ReasonTile title={t("prompts.reasons.marker.title")} body={t("prompts.reasons.marker.body")} />
            </div>
          </details>
        </div>

        {/* The toolbar: diff, reset, preview, live test, save. */}
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3 border-t border-border/60 pt-3">
          <div className="flex flex-wrap items-center gap-2">
            <button type="button" data-testid="diff-button" onClick={() => setDiffOpen((open) => !open)} className={TOOLBAR_BUTTON}>
              <Icon name="viewList" size={15} />
              <span>{t("prompts.editor.diff.button")}</span>
            </button>
            <button
              type="button"
              data-testid="reset-button"
              title={scope.tier === "novel" ? t("prompts.editor.resetTitle") : t("prompts.editor.deleteTitle")}
              onClick={() => setConfirmReset(true)}
              className={TOOLBAR_BUTTON}
            >
              <Icon name="refresh" size={15} />
              <span>{scope.tier === "novel" ? t("prompts.editor.reset") : t("prompts.editor.deleteOverride")}</span>
            </button>
            {confirmReset && (
              <span className="inline-flex items-center gap-2 rounded border border-warning/50 bg-panel px-2.5 py-1 text-meta text-foreground" data-testid="reset-confirm">
                <span>{t("prompts.editor.resetConfirm")}</span>
                <button type="button" data-testid="reset-go" onClick={runReset} className={`rounded bg-primary px-2 py-1 text-meta font-semibold text-primary-foreground ${FOCUS}`}>
                  {t("prompts.editor.resetGo")}
                </button>
                <button
                  type="button"
                  data-testid="reset-cancel"
                  onClick={() => setConfirmReset(false)}
                  className={`rounded px-2 py-1 text-meta text-muted transition-colors hover:text-foreground ${FOCUS}`}
                >
                  {t("prompts.live.cancel")}
                </button>
              </span>
            )}
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <button type="button" data-testid="preview-button" onClick={runPreview} className={TOOLBAR_BUTTON}>
              <Icon name="insights" size={15} />
              <span>{t("prompts.preview.button")}</span>
            </button>
            <button type="button" data-testid="save-button" onClick={runSave} disabled={save.isPending} className={PRIMARY_BUTTON}>
              <Icon name="check" size={15} />
              <span>{save.isPending ? t("prompts.editor.save.busy") : t("prompts.editor.save")}</span>
            </button>
          </div>
        </div>
      </div>

      {/* The live-test card: the warning precedes the call — it stands above
          the trigger in every phase, exactly where the states reference
          draws Werkzeug 02. The overrides draft's extra toolbar button folds
          into this card's trigger: one door per action. */}
      <LiveTest promptKey={promptKey} novelId={novelId} dirty={dirty} draft={dirty ? draft : null} />

      {/* The preview card: the provider-free render and its diagnostics. */}
      {(preview.isPending || preview.data !== undefined || preview.isError) && (
        <div className="rounded-lg border border-border bg-panel p-5 shadow-sm" data-testid="preview-card">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 pb-2">
            <h3 className="text-label font-semibold text-foreground">{t("prompts.preview.title")}</h3>
            {preview.data !== undefined && (
              <div className={`${MONO} flex items-center gap-3 text-xs text-muted`}>
                <span>{t("prompts.preview.chars", { count: preview.data.diagnostics.chars })}</span>
                <span>{t("prompts.preview.lines", { count: preview.data.diagnostics.lines })}</span>
              </div>
            )}
          </div>
          {preview.isPending && <p className="mt-3 text-meta text-muted">{t("prompts.preview.busy")}</p>}
          {preview.isError && (
            <div className="mt-3">
              <RefusalFace failure={preview.error} />
            </div>
          )}
          {preview.data !== undefined && (
            <div className="mt-3 space-y-3">
              <p className="flex items-center gap-2 text-meta text-muted">
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-success" />
                {t("prompts.preview.diagnostics")}
              </p>
              <div className="flex flex-wrap items-center gap-2" data-testid="preview-provenance">
                <span className="text-meta font-semibold text-muted">{t("prompts.preview.provenance")}:</span>
                {preview.data.variables.map((variable) => (
                  <span key={variable.name} className={`${MONO} rounded border border-border bg-panel px-2 py-0.5 text-xs text-foreground`}>
                    {variable.name}
                    <span className={`ms-1.5 rounded px-1 py-0.5 text-[10px] font-medium ${variable.used ? "bg-panel text-primary" : "bg-panel text-muted"}`}>
                      {variable.used ? t("prompts.preview.used") : t("prompts.preview.unused")}
                    </span>
                  </span>
                ))}
              </div>
              {preview.data.diagnostics.contract_ok === false && (
                <p className="rounded border border-warning/50 bg-panel p-2.5 text-meta text-foreground" data-testid="preview-contract-fail" role="alert">
                  {t("prompts.preview.contractFail")}
                </p>
              )}
              {preview.data.diagnostics.contract_ok === true && (
                <p className="text-meta text-success">{t("prompts.preview.contractOk")}</p>
              )}
              {preview.data.diagnostics.contract_ok === null && (
                <p className="text-meta text-muted">{t("prompts.preview.contractNone")}</p>
              )}
              <div>
                <div className="mb-1 text-meta font-semibold text-muted">{t("prompts.preview.rendered")}</div>
                <pre data-testid="preview-rendered" className={`${MONO} whitespace-pre-wrap rounded border border-border bg-surface p-3 text-xs leading-relaxed text-foreground`}>
                  {preview.data.rendered}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}

      {/* The diff panel: the saved tiers, asked from the endpoint. */}
      {diffOpen && (
        <div className="rounded-lg border border-border bg-panel p-5 shadow-sm" data-testid="diff-panel">
          <h3 className="border-b border-border/60 pb-2 text-label font-semibold text-foreground">{t("prompts.editor.diff.title")}</h3>
          {diff.isPending && <p className="mt-3 text-meta text-muted">{t("prompts.loading")}</p>}
          {diff.data !== undefined && (
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <div className="rounded border border-border bg-surface">
                <div className="border-b border-border bg-soft px-3 py-2 text-meta font-semibold text-foreground">
                  {t("prompts.editor.diff.bundled")}
                </div>
                <pre data-testid="diff-bundled" className={`${MONO} whitespace-pre-wrap p-3 text-xs leading-relaxed text-muted`}>
                  {diff.data.bundled_content}
                </pre>
              </div>
              <div className="rounded border border-border bg-surface">
                <div className="border-b border-border bg-soft px-3 py-2 text-meta font-semibold text-foreground">
                  {t("prompts.editor.diff.override")}
                </div>
                {diff.data.override_content === null ? (
                  <p className="p-3 text-meta text-muted">{t("prompts.editor.diff.none")}</p>
                ) : (
                  <pre data-testid="diff-override" className={`${MONO} whitespace-pre-wrap p-3 text-xs leading-relaxed text-foreground`}>
                    {diff.data.override_content}
                  </pre>
                )}
              </div>
            </div>
          )}
          <div className="mt-3 text-end">
            <button type="button" data-testid="diff-close" onClick={() => setDiffOpen(false)} className={TOOLBAR_BUTTON}>
              {t("prompts.editor.diff.close")}
            </button>
          </div>
        </div>
      )}
    </section>
  );
}

function ReasonTile({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded border border-border bg-panel p-2 text-xs">
      <span className="block font-semibold text-foreground">{title}</span>
      <span className="text-muted">{body}</span>
    </div>
  );
}

/** The live test's phases: idle, running (context + the arriving answer),
 *  done, and the failure faces — the coded pre-stream answers localized by
 *  code, the mid-stream error frame, the refused draft. */
type LivePhase =
  | { phase: "idle" }
  | { phase: "running"; context: LiveTestContext | null; answer: string }
  | { phase: "done"; context: LiveTestContext | null; answer: string }
  | { phase: "failed"; kind: "rateLimited" | "noContext" | "embeddingMismatch" | "keyUnavailable" | "provider" | "interrupted" | "network" | "generic"; code?: string; retryAfter?: number }
  | { phase: "refused"; failure: WireError };

function LiveTest({ promptKey, novelId, dirty, draft }: { promptKey: string; novelId: string | null; dirty: boolean; draft: string | null }) {
  const t = useTranslation();
  const [phase, setPhase] = useState<LivePhase>({ phase: "idle" });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  function run(): void {
    const controller = new AbortController();
    controllerRef.current = controller;
    setPhase({ phase: "running", context: null, answer: "" });
    void startLiveTest(
      promptKey,
      { content: dirty ? draft : null, novel_id: novelId },
      controller.signal,
      {
        context: (context) =>
          setPhase((current) =>
            current.phase === "running" || current.phase === "done" ? { ...current, context } : current,
          ),
        delta: (text) =>
          setPhase((current) => {
            if (current.phase !== "running" && current.phase !== "done") return current;
            return { ...current, phase: "running", answer: current.answer + text };
          }),
        done: () =>
          setPhase((current) =>
            current.phase === "running" || current.phase === "done"
              ? { ...current, phase: "done" }
              : current,
          ),
        error: (code, retryAfter) =>
          setPhase({
            phase: "failed",
            kind:
              code === "rate-limited"
                ? "rateLimited"
                : code === "no-context"
                  ? "noContext"
                  : code === "embedding-mismatch"
                    ? "embeddingMismatch"
                    : code === "key-unavailable"
                      ? "keyUnavailable"
                      : code === "interrupted"
                        ? "interrupted"
                        : code === "network"
                          ? "network"
                          : "generic",
            code,
            retryAfter,
          }),
        refused: (body) =>
          setPhase({ phase: "refused", failure: Object.assign(new Error("live test refused"), { status: 422, body }) }),
        failed: (status) => setPhase({ phase: "failed", kind: status === 502 ? "provider" : "generic", code: `http-${status}` }),
        network: () => setPhase({ phase: "failed", kind: "network" }),
      },
    );
  }

  function cancel(): void {
    controllerRef.current?.abort();
    controllerRef.current = null;
    setPhase({ phase: "idle" });
  }

  const running = phase.phase === "running";
  const answerText = phase.phase === "running" || phase.phase === "done" ? phase.answer : "";
  const context = phase.phase === "running" || phase.phase === "done" ? phase.context : null;

  return (
    <div className="rounded-lg border border-border bg-panel p-5 shadow-sm" data-testid="live-card">
      <div className="flex items-start gap-2.5 border-b border-border/60 pb-2">
        <span className="mt-0.5 text-primary">
          <Icon name="shield" size={18} />
        </span>
        <div>
          <h3 className="text-label font-semibold text-foreground">{t("prompts.live.title")}</h3>
          {/* The warning precedes the call: it stands in every phase, above
              the trigger, exactly where the states reference draws it. */}
          <p data-testid="live-warning" className="mt-0.5 max-w-2xl text-xs leading-relaxed text-muted">
            {t("prompts.live.warning")}
          </p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="button" data-testid="live-button" onClick={run} disabled={running} className={PRIMARY_BUTTON}>
          <Icon name="play" size={15} />
          <span>{t("prompts.live.test")}</span>
        </button>
        {running && (
          <button type="button" data-testid="live-cancel" onClick={cancel} className={TOOLBAR_BUTTON}>
            {t("prompts.live.cancel")}
          </button>
        )}
        {phase.phase === "done" && (
          <span className="inline-flex items-center gap-1.5 text-meta font-medium text-success" data-testid="live-done">
            <Icon name="checkCircle" size={15} />
            {t("prompts.live.done")}
          </span>
        )}
        {phase.phase === "refused" && <RefusalFace failure={phase.failure} prefix={t("prompts.live.error.draftRefused")} />}
        {phase.phase === "failed" && <LiveErrorFace phase={phase} />}
      </div>
      {(running || phase.phase === "done") && (
        <div className="mt-3 rounded border border-border bg-surface p-3" data-testid="live-answer-region">
          {context !== null && <LiveContextLine context={context} />}
          <div className="mt-1 flex items-center justify-between text-xs">
            <span className="font-semibold text-primary">{t("prompts.live.context.title")}</span>
            {running && <span className="text-muted">{t("prompts.live.running")}</span>}
          </div>
          <div aria-live="polite" data-testid="live-answer" className={`${SERIF} mt-1 text-sm italic leading-relaxed text-foreground`}>
            {answerText}
          </div>
        </div>
      )}
    </div>
  );
}

function LiveContextLine({ context }: { context: LiveTestContext }) {
  const t = useTranslation();
  const facts = useMemo(() => {
    const entries = Object.entries(context.facts);
    return entries
      .map(([key, value]) => `${FACT_KEYS.has(key) ? t(`prompts.live.facts.${key}` as Parameters<typeof t>[0]) : key}: ${value}`)
      .join(" · ");
  }, [context.facts, t]);
  return (
    <div className="mb-1 flex flex-wrap items-center gap-x-2 gap-y-1 border-b border-border/60 pb-1 text-xs text-muted" data-testid="live-context">
      <span className="font-semibold text-muted">
        {context.provider === "fake" ? t("prompts.live.provider.fake") : t("prompts.live.provider.kind", { kind: context.provider })}
      </span>
      {context.provider === "fake" && <span>{t("prompts.live.provider.fakeNote")}</span>}
      <span>
        {t("prompts.live.context.source.draft")} / {t("prompts.live.context.source.effective")}:{" "}
        {context.source === "draft" ? t("prompts.live.context.source.draft") : t("prompts.live.context.source.effective")}
      </span>
      <span>{t("prompts.live.context.label")} {facts}</span>
    </div>
  );
}

function LiveErrorFace({ phase }: { phase: Extract<LivePhase, { phase: "failed" }> }) {
  const t = useTranslation();
  const copy = (() => {
    switch (phase.kind) {
      case "rateLimited":
        return t("prompts.live.error.rateLimited");
      case "noContext":
        return t("prompts.live.error.noContext");
      case "embeddingMismatch":
        return t("prompts.live.error.embeddingMismatch");
      case "keyUnavailable":
        return t("prompts.live.error.keyUnavailable");
      case "provider":
        return t("prompts.live.error.provider");
      case "interrupted":
        return t("prompts.live.error.interrupted");
      case "network":
        return t("prompts.live.error.network");
      default:
        return t("prompts.live.error.generic", { code: phase.code ?? "unknown" });
    }
  })();
  return (
    <span role="alert" data-testid="live-error" className="inline-flex flex-col rounded border border-danger/40 bg-panel p-2.5 text-meta text-danger">
      <span>{copy}</span>
      {phase.kind === "rateLimited" && phase.retryAfter !== undefined && (
        <span className="text-foreground">{t("prompts.live.cooldown", { count: phase.retryAfter })}</span>
      )}
    </span>
  );
}
