import { useEffect, useId, useRef, useState } from "react";

import { useRouter } from "@tanstack/react-router";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { dirtyFields } from "@shell/lib/dirty";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { LeaveBlocker } from "@shell/components/LeaveBlocker";
import { Button } from "@shell/ui/Button";
import { Dialog } from "@shell/ui/Dialog";
import { Field, Input, Select } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

type Profile = components["schemas"]["ProfileRead"];
type ProfileTestResult = components["schemas"]["ProfileTestResult"];
type Assignment = components["schemas"]["AssignmentRead"];
type TaskEffective = components["schemas"]["TaskEffectiveRead"];

/** The kinds the form offers; the server's vocabulary is exactly these two. */
const KINDS: readonly string[] = ["fake", "openai-chat"];

const KIND_LABELS: Record<string, MessageKey> = {
  fake: "settings.profiles.kind.fake",
  "openai-chat": "settings.profiles.kind.openai-chat",
};

/**
 * The task labels the catalog carries, keyed by task. The list of tasks comes
 * from the server (`KNOWN_TASK_KEYS`); this map only supplies words. The
 * server's `assignable` decides whether a row gets a select, so a new key is
 * routable without a frontend edit and only needs its label (a missing label
 * falls back to the generic one, never to the raw key).
 */
const TASK_LABELS: Record<string, MessageKey> = {
  "writing.continuation": "settings.task.writing.continuation",
  "chat.ask": "settings.task.chat.ask",
  "knowledge.extract-entities": "settings.task.knowledge.extract-entities",
  "knowledge.check-consistency": "settings.task.knowledge.check-consistency",
  "settings.test": "settings.tasks.settings.test",
};

/**
 * The one label grid this panel's forms speak: the label sits in the grid's
 * own 128 px track, the control beside it at the field's 28 px. The column
 * comes from the track, never from a sized label — and `grid` appended after
 * `Field`'s own `flex` is what turns the field into the row (the E2E pins the
 * computed `gridTemplateColumns`, so a Tailwind reorder that let the stack
 * win again goes red loudly instead of drifting quietly).
 */
const LABEL_ROW = "grid grid-cols-[128px_minmax(0,1fr)] items-center gap-x-2";

/** One text field of the profile form, as the input holds it. */
type FormState = {
  name: string;
  kind: string;
  baseUrl: string;
  model: string;
  apiKey: string;
  contextWindow: string;
  maxOutput: string;
  temperature: string;
  timeout: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  kind: "fake",
  baseUrl: "",
  model: "",
  apiKey: "",
  contextWindow: "",
  maxOutput: "",
  temperature: "",
  timeout: "",
};

/** A profile's columns as the form holds them: every value a string. */
function formOf(profile: Profile): FormState {
  return {
    name: profile.name,
    kind: profile.kind,
    baseUrl: profile.base_url ?? "",
    model: profile.model ?? "",
    // The key is never prefilled: no read carries it, and the field means
    // "replace", with emptiness meaning "keep" (the hint below says so).
    apiKey: "",
    contextWindow: profile.context_window === null ? "" : String(profile.context_window),
    maxOutput: profile.max_output_tokens === null ? "" : String(profile.max_output_tokens),
    temperature: profile.temperature === null ? "" : String(profile.temperature),
    timeout: profile.request_timeout === null ? "" : String(profile.request_timeout),
  };
}

/** A numeric field as a number, or undefined for "send nothing". */
function optionalNumber(value: string): number | undefined {
  const trimmed = value.trim();
  if (trimmed === "") return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

/**
 * A tuning column of an edit: the number, or the explicit null that clears
 * it. An edit's every column is sent, so an emptied field must arrive as a
 * present null — omitted, it would mean "keep", and the form says otherwise.
 */
function tuned(value: string): number | null {
  const parsed = optionalNumber(value);
  return parsed === undefined ? null : parsed;
}

/**
 * The provider section: the list with its per-profile actions, the create
 * and edit form, and the per-task assignments. Everything a user can do to
 * a profile happens here, against the same masked surface the API serves.
 *
 * The sub-page's one filled primary is the form's save (L1); every other
 * control — the list actions, the retries, the key box's done — is a
 * bordered equal. The states speak through `Notice`: the wait, the empty
 * list, the load failure with its retry, the save and action refusals, and
 * the row's own probe outcomes.
 */
export function ProvidersPanel() {
  const t = useTranslation();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [tasks, setTasks] = useState<TaskEffective[]>([]);
  const [editing, setEditing] = useState<Profile | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // The values the form was opened with: anything else is dirty and asks
  // before it is thrown away.
  const [snapshot, setSnapshot] = useState<FormState>(EMPTY_FORM);
  const [guardOpen, setGuardOpen] = useState(false);
  const guardAnswer = useRef<((leave: boolean) => void) | null>(null);

  const dirty = dirtyFields(form, snapshot).length > 0;

  /** Resolve the standing ask; a dismissed dialog means "stay". */
  function settle(leave: boolean): void {
    const answer = guardAnswer.current;
    guardAnswer.current = null;
    setGuardOpen(false);
    answer?.(leave);
  }

  /** Ask before typed values are discarded; a second ask while one stands is a no. */
  function askToLeave(): Promise<boolean> {
    if (guardAnswer.current !== null) return Promise.resolve(false);
    setGuardOpen(true);
    return new Promise<boolean>((resolve) => {
      guardAnswer.current = resolve;
    });
  }

  // The third door: a route change with a dirty form asks too. The blocker
  // mounts only where a router exists, so the panel stays renderable alone.
  const router = useRouter({ warn: false });
  const [created, setCreated] = useState<{ name: string; apiKey: string } | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [failure, setFailure] = useState<MessageKey | null>(null);
  const [deleteRefused, setDeleteRefused] = useState<"default" | "other" | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ProfileTestResult>>({});
  const [models, setModels] = useState<Record<string, string[] | "failed">>({});
  // The stored-key hint's id: wired to the key input by hand, because the
  // hint belongs to the control's column of the grid row (Field's own hint
  // would land under the label).
  const apiKeyHintId = useId();

  // biome-ignore lint/correctness/useExhaustiveDependencies: mount-once load — `reload` is a component-scope function re-created every render, so listing it would re-run this effect every render.
  useEffect(() => {
    // Both views load on mount: the assignment selects display their values
    // out of this list, so a fresh visit must show the stored choices — not
    // "automatic" until some later mutation happens to refetch them. A
    // navigation away during that first fetch must not write into an
    // unmounted panel; the flag is the smallest guard, and React's no-op
    // setState is not a contract to rely on.
    let cancelled = false;
    void reload(() => cancelled);
    return () => {
      cancelled = true;
    };
  }, []);

  async function reload(cancelled: () => boolean = () => false): Promise<void> {
    // The three reads fail independently: a lost key that fails /tasks must
    // not also hide the profiles and assignments that did arrive. Settled
    // results keep every success, and the panel's alert names the failure.
    const [profileList, assignmentList, taskList] = await Promise.allSettled([
      client.GET("/api/settings/profiles"),
      client.GET("/api/settings/assignments"),
      client.GET("/api/settings/tasks"),
    ]);
    if (cancelled()) return;
    let failed = false;
    if (profileList.status === "fulfilled" && profileList.value.response.ok) {
      setProfiles(profileList.value.data ?? []);
    } else {
      failed = true;
    }
    if (assignmentList.status === "fulfilled" && assignmentList.value.response.ok) {
      setAssignments(assignmentList.value.data ?? []);
    } else {
      failed = true;
    }
    if (taskList.status === "fulfilled" && taskList.value.response.ok) {
      setTasks(taskList.value.data ?? []);
    } else {
      failed = true;
    }
    setFailure(failed ? "settings.profiles.errorLoad" : null);
  }

  /** One form field's change, by its key in the form state. */
  function set<K extends keyof FormState>(key: K, value: string): void {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function startEditing(profile: Profile): void {
    void (async () => {
      if (dirty && !(await askToLeave())) return;
      setEditing(profile);
      setForm(formOf(profile));
      setSnapshot(formOf(profile));
      setSaveFailed(false);
    })();
  }

  /** Close the form without a question — after a save it holds nothing new. */
  function resetForm(): void {
    setEditing(null);
    setForm({ ...EMPTY_FORM, kind: "fake" });
    setSnapshot({ ...EMPTY_FORM, kind: "fake" });
    setSaveFailed(false);
  }

  function stopEditing(): void {
    void (async () => {
      if (dirty && !(await askToLeave())) return;
      resetForm();
    })();
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (form.name.trim() === "") return;
    // An empty key field never reaches the body: only replacing a key is an
    // operation, and "keep the stored one" is the absence of one.
    const apiKey = form.apiKey.trim() === "" ? {} : { api_key: form.apiKey.trim() };
    try {
      if (editing === null) {
        const { data, response } = await client.POST("/api/settings/profiles", {
          body: {
            name: form.name.trim(),
            kind: form.kind,
            ...(form.baseUrl.trim() === "" ? {} : { base_url: form.baseUrl.trim() }),
            ...(form.model.trim() === "" ? {} : { model: form.model.trim() }),
            ...apiKey,
            ...(optionalNumber(form.contextWindow) === undefined
              ? {}
              : { context_window: optionalNumber(form.contextWindow) }),
            ...(optionalNumber(form.maxOutput) === undefined
              ? {}
              : { max_output_tokens: optionalNumber(form.maxOutput) }),
            ...(optionalNumber(form.temperature) === undefined
              ? {}
              : { temperature: optionalNumber(form.temperature) }),
            ...(optionalNumber(form.timeout) === undefined
              ? {}
              : { request_timeout: optionalNumber(form.timeout) }),
          },
        });
        if (!response.ok || data === undefined) {
          setSaveFailed(true);
          return;
        }
        // The one response that carries the full key becomes the one box that
        // shows it; dismissed, it never exists again anywhere.
        if (data.api_key) setCreated({ name: data.name, apiKey: data.api_key });
        resetForm();
      } else {
        // An edit sends every column explicitly: an emptied field clears it
        // (present nulls clear), which is what a form full of values means —
        // the tuning columns included, or a cleared value would silently keep
        // governing every request.
        const { response } = await client.PATCH("/api/settings/profiles/{profile_id}", {
          params: { path: { profile_id: editing.id } },
          body: {
            name: form.name.trim(),
            base_url: form.baseUrl.trim() === "" ? null : form.baseUrl.trim(),
            model: form.model.trim() === "" ? null : form.model.trim(),
            ...apiKey,
            context_window: tuned(form.contextWindow),
// nosemgrep
            max_output_tokens: tuned(form.maxOutput),
            temperature: tuned(form.temperature),
            request_timeout: tuned(form.timeout),
          },
        });
        if (!response.ok) {
          setSaveFailed(true);
          return;
        }
        resetForm();
      }
    } catch {
      // A rejected fetch has no response to inspect: the save says so where
      // a refused response does, and the handler resolves instead of
      // leaving the rejection to the browser.
      setSaveFailed(true);
      return;
    }
    // After a save that landed: the reload's own reads settle, so a lost
    // service is the load alert, never a save refusal.
    try {
      await reload();
    } catch {
      setFailure("settings.profiles.errorLoad");
    }
  }

  async function makeDefault(profile: Profile): Promise<void> {
    setFailure(null);
    try {
      const { response } = await client.PATCH("/api/settings/profiles/{profile_id}", {
        params: { path: { profile_id: profile.id } },
        body: { is_default: true },
      });
      if (!response.ok) {
        setFailure("settings.profiles.errorAction");
        return;
      }
      await reload();
    } catch {
      // A rejected fetch has no response to inspect: the page still says so,
      // in the same place a server-reachable failure appears.
      setFailure("settings.profiles.errorAction");
    }
  }

  async function remove(profile: Profile): Promise<void> {
    const { response } = await client.DELETE("/api/settings/profiles/{profile_id}", {
      params: { path: { profile_id: profile.id } },
    });
    if (response.ok) {
      setDeleteRefused(null);
      await reload();
      return;
    }
    // The 409 is the default guard: its message names the way out, so the
    // page names it too — in the reader's language, not the server's.
    setDeleteRefused(response.status === 409 ? "default" : "other");
  }

  async function testConnection(profile: Profile): Promise<void> {
    setFailure(null);
    try {
      const { data, response } = await client.POST("/api/settings/profiles/{profile_id}/test", {
        params: { path: { profile_id: profile.id } },
      });
      if (response.ok && data) {
        setTestResults((current) => ({ ...current, [profile.id]: data }));
        return;
      }
      setFailure("settings.profiles.errorAction");
    } catch {
      setFailure("settings.profiles.errorAction");
    }
  }

  async function discoverModels(profile: Profile): Promise<void> {
    const { data, response } = await client.GET("/api/settings/profiles/{profile_id}/models", {
      params: { path: { profile_id: profile.id } },
    });
    // The outcome is data on the row either way: the ids, or the failure
    // the page can name while the endpoint cannot be asked.
    setModels((current) => ({
      ...current,
      [profile.id]: response.ok ? (data ?? []) : "failed",
    }));
  }

  async function assign(taskKey: string, profileId: string): Promise<void> {
    setFailure(null);
    try {
      const { response } = await client.PUT("/api/settings/assignments/{task_key}", {
        params: { path: { task_key: taskKey } },
        body: { profile_id: profileId === "" ? null : profileId },
      });
      if (!response.ok) {
        setFailure("settings.profiles.errorAction");
        return;
      }
      await reload();
    } catch {
      setFailure("settings.profiles.errorAction");
    }
  }

  return (
    <>
      <section aria-labelledby="settings-providers-heading">
        <h2 id="settings-providers-heading" className="text-emph font-semibold">
          {t("settings.providers")}
        </h2>

        {created ? (
          <Notice
            tone="info"
            live="status"
            className="mt-3"
            action={
              <Button variant="secondary" onClick={() => setCreated(null)}>
                {t("settings.profiles.keyOnceDone")}
              </Button>
            }
          >
            {t("settings.profiles.keyOnce", { name: created.name, key: created.apiKey })}
          </Notice>
        ) : null}

        {saveFailed ? (
          <Notice tone="danger" live="alert" className="mt-3">
            {t("settings.profiles.errorSave")}
          </Notice>
        ) : null}
        {deleteRefused !== null ? (
          <Notice tone="danger" live="alert" className="mt-3">
            {deleteRefused === "default"
              ? t("settings.profiles.errorDefaultDelete")
              : t("settings.profiles.errorDelete")}
          </Notice>
        ) : null}
        {failure !== null ? (
          // The reads failed: said where the way back is — one press asks
          // all three again, no reload demanded.
          <Notice
            tone="danger"
            live="alert"
            className="mt-3"
            action={
              <Button variant="secondary" onClick={() => void reload()}>
                {t("settings.retry")}
              </Button>
            }
          >
            {t(failure)}
          </Notice>
        ) : null}

        {profiles === null ? (
          // The answer has not arrived yet: the wait is named, not silence.
          // A failed load speaks through the alert above, not twice here.
          failure === null ? (
            <Notice tone="quiet" live="status" className="mt-3">
              {t("settings.profiles.loading")}
            </Notice>
          ) : null
        ) : profiles.length === 0 ? (
          <Notice tone="quiet" className="mt-3">
            {t("settings.profiles.empty")}
          </Notice>
        ) : (
          <Panel dense className="mt-3">
            <ul className="flex flex-col">
              {profiles.map((profile) => {
                const result = testResults[profile.id];
                const discovered = models[profile.id];
                return (
                  <li
                    key={profile.id}
                    className="border-b border-rule py-3 first:pt-0 last:border-b-0 last:pb-0"
                  >
                    <p className="flex flex-wrap items-baseline gap-2 text-body font-medium">
                      {profile.name}
                      {profile.is_default ? (
                        <span className="rounded-full bg-panel px-2 py-0.5 text-label">
                          {t("settings.profiles.defaultBadge")}
                        </span>
                      ) : null}
                    </p>
                    <p className="mt-1 text-body text-muted">
                      {KIND_LABELS[profile.kind] === undefined
                        ? profile.kind
                        : t(KIND_LABELS[profile.kind])}
                      {" · "}
                      {profile.model ?? "—"}
                      {profile.api_key_mask ? ` · ${profile.api_key_mask}` : ""}
                    </p>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {!profile.is_default ? (
                        <Button variant="secondary" onClick={() => void makeDefault(profile)}>
                          {t("settings.profiles.makeDefault")}
                        </Button>
                      ) : null}
                      <Button variant="secondary" onClick={() => startEditing(profile)}>
                        {t("settings.profiles.edit")}
                      </Button>
                      <Button variant="secondary" onClick={() => void testConnection(profile)}>
                        {t("settings.profiles.test")}
                      </Button>
                      {profile.kind === "openai-chat" ? (
                        <Button variant="secondary" onClick={() => void discoverModels(profile)}>
                          {t("settings.profiles.discover")}
                        </Button>
                      ) : null}
                      <Button variant="secondary" onClick={() => void remove(profile)}>
                        {t("settings.profiles.delete")}
                      </Button>
                    </div>
                    {result === undefined ? null : (
                      <Notice tone={result.ok ? "quiet" : "warning"} live="status" className="mt-2">
                        {result.ok
                          ? t("settings.profiles.testOk", { ms: result.latency_ms })
                          : t("settings.profiles.testFailed", { error: result.error ?? "" })}
                      </Notice>
                    )}
                    {discovered === undefined ? null : (
                      <Notice
                        tone={discovered === "failed" ? "warning" : "quiet"}
                        live="status"
                        className="mt-2"
                      >
                        {discovered === "failed"
                          ? t("settings.profiles.errorModels")
                          : t("settings.profiles.models", { models: discovered.join(", ") })}
                      </Notice>
                    )}
                  </li>
                );
              })}
            </ul>
          </Panel>
        )}

        <form onSubmit={submit} className="mt-5 flex flex-col gap-2">
          {editing === null ? null : <p className="text-body text-muted">{editing.name}</p>}
          <Field label={t("settings.profiles.nameLabel")} className={LABEL_ROW}>
            <Input
              value={form.name}
              onChange={(event) => set("name", event.target.value)}
              spellCheck={false}
              autoComplete="off"
            />
          </Field>
          <Field label={t("settings.profiles.kindLabel")} className={LABEL_ROW}>
            <Select
              value={form.kind}
              onChange={(event) => set("kind", event.target.value)}
              disabled={editing !== null}
            >
              {KINDS.map((kind) => (
                <option key={kind} value={kind}>
                  {KIND_LABELS[kind] === undefined ? kind : t(KIND_LABELS[kind])}
                </option>
              ))}
            </Select>
          </Field>
          <Field label={t("settings.profiles.baseUrlLabel")} className={LABEL_ROW}>
            <Input
              value={form.baseUrl}
              onChange={(event) => set("baseUrl", event.target.value)}
              spellCheck={false}
              autoComplete="off"
            />
          </Field>
          <Field label={t("settings.profiles.modelLabel")} className={LABEL_ROW}>
            <Input
              value={form.model}
              onChange={(event) => set("model", event.target.value)}
              spellCheck={false}
              autoComplete="off"
            />
          </Field>
          <Field label={t("settings.profiles.apiKeyLabel")} className={LABEL_ROW}>
            <Input
              type="password"
              value={form.apiKey}
              onChange={(event) => set("apiKey", event.target.value)}
              aria-describedby={apiKeyHintId}
              spellCheck={false}
              autoComplete="new-password"
            />
            {editing !== null && editing.api_key_mask !== null ? (
              <p id={apiKeyHintId} className="col-start-2 text-label text-muted">
                {t("settings.profiles.apiKeyHint")}
              </p>
            ) : null}
          </Field>
          <Field label={t("settings.profiles.contextWindowLabel")} className={LABEL_ROW}>
            <Input
              type="number"
              min={1}
              value={form.contextWindow}
              onChange={(event) => set("contextWindow", event.target.value)}
            />
          </Field>
          <Field label={t("settings.profiles.maxOutputLabel")} className={LABEL_ROW}>
            <Input
              type="number"
              min={1}
              value={form.maxOutput}
              onChange={(event) => set("maxOutput", event.target.value)}
            />
          </Field>
          <Field label={t("settings.profiles.temperatureLabel")} className={LABEL_ROW}>
            <Input
              type="number"
              min={0}
              max={2}
              step={0.1}
              value={form.temperature}
              onChange={(event) => set("temperature", event.target.value)}
            />
          </Field>
          <Field label={t("settings.profiles.timeoutLabel")} className={LABEL_ROW}>
            <Input
              type="number"
              min={0.5}
              step={0.5}
              value={form.timeout}
              onChange={(event) => set("timeout", event.target.value)}
            />
          </Field>
          <div className="mt-2 flex items-center gap-2">
            {/* The save is this sub-page's one filled primary (L1); the
                cancel beside it is a bordered equal. */}
            <Button
              type="submit"
              variant="primary"
              disabled={form.name.trim() === ""}
            >
              {editing === null
                ? t("settings.profiles.create")
                : t("settings.profiles.save")}
            </Button>
            {editing === null ? null : (
              <Button variant="secondary" onClick={stopEditing}>
                {t("settings.profiles.cancel")}
              </Button>
            )}
          </div>
        </form>
      </section>

      <section aria-labelledby="settings-assignments-heading" className="mt-5">
        <h2 id="settings-assignments-heading" className="text-emph font-semibold">
          {t("settings.assignments")}
        </h2>
        <div className="mt-3 flex flex-col gap-2">
          {tasks.map((task) => {
            const assigned = assignments.find((row) => row.task_key === task.task_key);
            const labelKey = TASK_LABELS[task.task_key];
            const label = labelKey === undefined ? t("settings.tasks.unknown") : t(labelKey);
            const kindKey = KIND_LABELS[task.kind];
            if (!task.assignable) {
              // An audit-only key (the settings probe's) has no serving tier and
              // no assignment to offer: one labelled line explains what it is.
              // A plain text pair, not a `Field`: there is no control for a
              // label to point at.
              return (
                <div
                  key={task.task_key}
                  className={`${LABEL_ROW} text-label font-medium`}
                >
                  <span>{label}</span>
                  <p className="font-normal text-muted">
                    {t("settings.profiles.taskAuditOnly")}
                  </p>
                </div>
              );
            }
            // What actually answers, not the stored choice: the cascade can
            // serve a sibling's assignment or the default from here.
            const effective =
              task.profile_name !== null
                ? t("settings.assignments.via", { profile: task.profile_name })
                : t("settings.assignments.environment", {
                    kind: kindKey === undefined ? task.kind : t(kindKey),
                  });
            return (
              <Field key={task.task_key} label={label} className={LABEL_ROW}>
                <Select
                  value={assigned?.profile_id ?? ""}
                  onChange={(event) => void assign(task.task_key, event.target.value)}
                  aria-describedby={`settings-task-effective-${task.task_key}`}
                  className="max-w-64"
                >
                  <option value="">{t("settings.assignments.auto")}</option>
                  {(profiles ?? []).map((profile) => (
                    <option key={profile.id} value={profile.id}>
                      {profile.name}
                    </option>
                  ))}
                </Select>
                <p
                  id={`settings-task-effective-${task.task_key}`}
                  className="col-start-2 text-label font-normal text-muted"
                >
                  {effective}
                </p>
              </Field>
            );
          })}
        </div>
      </section>

      {router ? <LeaveBlocker dirty={dirty} ask={askToLeave} /> : null}

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
    </>
  );
}
