import { useEffect, useState } from "react";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";

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
 * from the server (`KNOWN_TASK_KEYS`); this map only supplies words, and a key
 * without one renders as itself — a new kernel key needs no frontend change.
 */
const TASK_LABELS: Record<string, MessageKey> = {
  "writing.continuation": "settings.task.writing.continuation",
  "chat.ask": "settings.task.chat.ask",
  "knowledge.extract-entities": "settings.task.knowledge.extract-entities",
  "knowledge.check-consistency": "settings.task.knowledge.check-consistency",
  "settings.test": "settings.task.settings.test",
};

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
 */
export function ProvidersPanel() {
  const t = useTranslation();
  const [profiles, setProfiles] = useState<Profile[] | null>(null);
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [tasks, setTasks] = useState<TaskEffective[]>([]);
  const [editing, setEditing] = useState<Profile | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [created, setCreated] = useState<{ name: string; apiKey: string } | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [deleteRefused, setDeleteRefused] = useState<"default" | "other" | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ProfileTestResult>>({});
  const [models, setModels] = useState<Record<string, string[] | "failed">>({});

  useEffect(() => {
    // Both views load on mount: the assignment selects display their values
    // out of this list, so a fresh visit must show the stored choices — not
    // "automatic" until some later mutation happens to refetch them.
    void reload();
  }, []);

  async function reload(): Promise<void> {
    const [profileList, assignmentList, taskList] = await Promise.all([
      client.GET("/api/settings/profiles"),
      client.GET("/api/settings/assignments"),
      client.GET("/api/settings/tasks"),
    ]);
    setProfiles(profileList.data ?? []);
    setAssignments(assignmentList.data ?? []);
    setTasks(taskList.data ?? []);
  }

  /** One form field's change, by its key in the form state. */
  function set<K extends keyof FormState>(key: K, value: string): void {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function startEditing(profile: Profile): void {
    setEditing(profile);
    setForm(formOf(profile));
    setSaveFailed(false);
  }

  function stopEditing(): void {
    setEditing(null);
    setForm({ ...EMPTY_FORM, kind: "fake" });
    setSaveFailed(false);
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (form.name.trim() === "") return;
    // An empty key field never reaches the body: only replacing a key is an
    // operation, and "keep the stored one" is the absence of one.
    const apiKey = form.apiKey.trim() === "" ? {} : { api_key: form.apiKey.trim() };
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
      stopEditing();
      await reload();
      return;
    }
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
        max_output_tokens: tuned(form.maxOutput),
        temperature: tuned(form.temperature),
        request_timeout: tuned(form.timeout),
      },
    });
    if (!response.ok) {
      setSaveFailed(true);
      return;
    }
    stopEditing();
    await reload();
  }

  async function makeDefault(profile: Profile): Promise<void> {
    await client.PATCH("/api/settings/profiles/{profile_id}", {
      params: { path: { profile_id: profile.id } },
      body: { is_default: true },
    });
    await reload();
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
    const { data, response } = await client.POST("/api/settings/profiles/{profile_id}/test", {
      params: { path: { profile_id: profile.id } },
    });
    if (response.ok && data) {
      setTestResults((current) => ({ ...current, [profile.id]: data }));
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
    const { response } = await client.PUT("/api/settings/assignments/{task_key}", {
      params: { path: { task_key: taskKey } },
      body: { profile_id: profileId === "" ? null : profileId },
    });
    if (response.ok) await reload();
  }

  const field =
    "rounded-md border border-border bg-card px-3 py-2 text-base font-normal focus:border-primary focus:outline-none";
  const action = "rounded-md border border-border px-2 py-1 text-sm font-medium";

  return (
    <>
      <section className="mt-10" aria-labelledby="settings-providers-heading">
        <h2 id="settings-providers-heading" className="text-lg font-semibold">
          {t("settings.providers")}
        </h2>

        {created ? (
          <p
            role="status"
            className="mt-3 rounded-lg border border-border bg-card px-4 py-3 text-sm"
          >
            {t("settings.profiles.keyOnce", { name: created.name, key: created.apiKey })}{" "}
            <button type="button" onClick={() => setCreated(null)} className={action}>
              {t("settings.profiles.keyOnceDone")}
            </button>
          </p>
        ) : null}

        {saveFailed ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {t("settings.profiles.errorSave")}
          </p>
        ) : null}
        {deleteRefused !== null ? (
          <p role="alert" className="mt-3 text-sm text-danger">
            {deleteRefused === "default"
              ? t("settings.profiles.errorDefaultDelete")
              : t("settings.profiles.errorDelete")}
          </p>
        ) : null}

        {profiles === null ? null : profiles.length === 0 ? (
          <p className="mt-3 text-sm text-muted">{t("settings.profiles.empty")}</p>
        ) : (
          <ul className="mt-3 flex flex-col gap-2">
            {profiles.map((profile) => {
              const result = testResults[profile.id];
              const discovered = models[profile.id];
              return (
              <li
                key={profile.id}
                className="rounded-lg border border-border bg-card px-4 py-3 text-sm"
              >
                <p className="flex flex-wrap items-center gap-2 font-medium">
                  {profile.name}
                  {profile.is_default ? (
                    <span className="rounded-full border border-border px-2 py-0.5 text-xs font-normal text-muted">
                      {t("settings.profiles.defaultBadge")}
                    </span>
                  ) : null}
                </p>
                <p className="mt-1 text-muted">
                  {KIND_LABELS[profile.kind] === undefined
                    ? profile.kind
                    : t(KIND_LABELS[profile.kind])}
                  {" · "}
                  {profile.model ?? "—"}
                  {profile.api_key_mask ? ` · ${profile.api_key_mask}` : ""}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {!profile.is_default ? (
                    <button
                      type="button"
                      onClick={() => void makeDefault(profile)}
                      className={action}
                    >
                      {t("settings.profiles.makeDefault")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => startEditing(profile)}
                    className={action}
                  >
                    {t("settings.profiles.edit")}
                  </button>
                  <button
                    type="button"
                    onClick={() => void testConnection(profile)}
                    className={action}
                  >
                    {t("settings.profiles.test")}
                  </button>
                  {profile.kind === "openai-chat" ? (
                    <button
                      type="button"
                      onClick={() => void discoverModels(profile)}
                      className={action}
                    >
                      {t("settings.profiles.discover")}
                    </button>
                  ) : null}
                  <button
                    type="button"
                    onClick={() => void remove(profile)}
                    className={action}
                  >
                    {t("settings.profiles.delete")}
                  </button>
                </div>
                {result === undefined ? null : (
                  <p role="status" className="mt-2 text-muted">
                    {result.ok
                      ? t("settings.profiles.testOk", { ms: result.latency_ms })
                      : t("settings.profiles.testFailed", { error: result.error ?? "" })}
                  </p>
                )}
                {discovered === undefined ? null : (
                  <p className="mt-2 text-muted">
                    {discovered === "failed"
                      ? t("settings.profiles.errorModels")
                      : t("settings.profiles.models", { models: discovered.join(", ") })}
                  </p>
                )}
              </li>
              );
            })}
          </ul>
        )}

        <form onSubmit={submit} className="mt-6 flex flex-col gap-3">
          {editing === null ? null : (
            <p className="text-sm text-muted">{editing.name}</p>
          )}
          <div className="flex flex-col gap-3 sm:flex-row">
            <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
              {t("settings.profiles.nameLabel")}
              <input
                value={form.name}
                onChange={(event) => set("name", event.target.value)}
                className={field}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm font-medium">
              {t("settings.profiles.kindLabel")}
              <select
                value={form.kind}
                onChange={(event) => set("kind", event.target.value)}
                disabled={editing !== null}
                className={field}
              >
                {KINDS.map((kind) => (
                  <option key={kind} value={kind}>
                    {KIND_LABELS[kind] === undefined ? kind : t(KIND_LABELS[kind])}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("settings.profiles.baseUrlLabel")}
            <input
              value={form.baseUrl}
              onChange={(event) => set("baseUrl", event.target.value)}
              className={field}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("settings.profiles.modelLabel")}
            <input
              value={form.model}
              onChange={(event) => set("model", event.target.value)}
              className={field}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            {t("settings.profiles.apiKeyLabel")}
            <input
              type="password"
              value={form.apiKey}
              onChange={(event) => set("apiKey", event.target.value)}
              aria-describedby="settings-api-key-hint"
              className={field}
            />
          </label>
          {editing !== null && editing.api_key_mask !== null ? (
            <p id="settings-api-key-hint" className="-mt-2 text-xs text-muted">
              {t("settings.profiles.apiKeyHint")}
            </p>
          ) : null}
          <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
            <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
              {t("settings.profiles.contextWindowLabel")}
              <input
                type="number"
                min={1}
                value={form.contextWindow}
                onChange={(event) => set("contextWindow", event.target.value)}
                className={field}
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
              {t("settings.profiles.maxOutputLabel")}
              <input
                type="number"
                min={1}
                value={form.maxOutput}
                onChange={(event) => set("maxOutput", event.target.value)}
                className={field}
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
              {t("settings.profiles.temperatureLabel")}
              <input
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={form.temperature}
                onChange={(event) => set("temperature", event.target.value)}
                className={field}
              />
            </label>
            <label className="flex flex-1 flex-col gap-1 text-sm font-medium">
              {t("settings.profiles.timeoutLabel")}
              <input
                type="number"
                min={0.5}
                step={0.5}
                value={form.timeout}
                onChange={(event) => set("timeout", event.target.value)}
                className={field}
              />
            </label>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="submit"
              disabled={form.name.trim() === ""}
              className="self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {editing === null
                ? t("settings.profiles.create")
                : t("settings.profiles.save")}
            </button>
            {editing === null ? null : (
              <button
                type="button"
                onClick={stopEditing}
                className="self-start rounded-md border border-border px-3 py-2 text-sm font-medium"
              >
                {t("settings.profiles.cancel")}
              </button>
            )}
          </div>
        </form>
      </section>

      <section className="mt-10" aria-labelledby="settings-assignments-heading">
        <h2 id="settings-assignments-heading" className="text-lg font-semibold">
          {t("settings.assignments")}
        </h2>
        {tasks.map((task) => {
          const assigned = assignments.find((row) => row.task_key === task.task_key);
          const labelKey = TASK_LABELS[task.task_key];
          const kindKey = KIND_LABELS[task.kind];
          return (
            <div
              key={task.task_key}
              className="mt-3 flex flex-col gap-1 text-sm font-medium sm:flex-row sm:items-center sm:gap-4"
            >
              <label htmlFor={`settings-task-${task.task_key}`}>
                {labelKey === undefined ? task.task_key : t(labelKey)}
              </label>
              <select
                id={`settings-task-${task.task_key}`}
                value={assigned?.profile_id ?? ""}
                onChange={(event) => void assign(task.task_key, event.target.value)}
                aria-describedby={`settings-task-effective-${task.task_key}`}
                className={`${field} sm:max-w-64`}
              >
                <option value="">{t("settings.assignments.auto")}</option>
                {(profiles ?? []).map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name}
                  </option>
                ))}
              </select>
              {/* What actually answers, not the stored choice: the cascade can
                  serve a sibling's assignment or the default from here. */}
              <p
                id={`settings-task-effective-${task.task_key}`}
                className="text-xs font-normal text-muted"
              >
                {task.profile_name !== null
                  ? t("settings.assignments.via", { profile: task.profile_name })
                  : t("settings.assignments.environment", {
                      kind: kindKey === undefined ? task.kind : t(kindKey),
                    })}
              </p>
            </div>
          );
        })}
      </section>
    </>
  );
}
