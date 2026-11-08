import { useEffect, useState } from "react";

import type { components } from "@shell/lib/api/schema";
import { client } from "@shell/lib/api/client";
import { dirtyFields } from "@shell/lib/dirty";
import { useTranslation } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";
import { Field, Input, Select } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

import { LABEL_ROW, type Guard, type Provider } from "./ProvidersSection";

type Model = components["schemas"]["ModelRead"];
type ModelTestResult = components["schemas"]["ModelTestResult"];

/** One text field of the model form, as the input holds it. */
type FormState = {
  name: string;
  providerId: string;
  model: string;
  contextWindow: string;
  maxOutput: string;
  temperature: string;
  timeout: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  providerId: "",
  model: "",
  contextWindow: "",
  maxOutput: "",
  temperature: "",
  timeout: "",
};

/** A model's columns as the form holds them: every value a string. */
function formOf(model: Model): FormState {
  return {
    name: model.name,
    providerId: model.provider_id,
    model: model.model,
    contextWindow: model.context_window === null ? "" : String(model.context_window),
    maxOutput: model.max_output_tokens === null ? "" : String(model.max_output_tokens),
    temperature: model.temperature === null ? "" : String(model.temperature),
    timeout: model.request_timeout === null ? "" : String(model.request_timeout),
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
 * The models section: the rows that name a provider and a model string,
 * with the provider select, the tunables, the default and the connection
 * test. Everything endpoint-shaped lives on the provider this row names —
 * the form offers no endpoint and no key, because the model carries none.
 *
 * The section's one filled primary is the form's save (L1); every other
 * control is a bordered equal. The states speak through `Notice`: the empty
 * list, the save and delete refusals, and the row's own probe outcome.
 */
export function ModelsSection({
  providers,
  models,
  reload,
  guard,
  onDirty,
}: {
  providers: Provider[] | null;
  models: Model[] | null;
  reload: () => Promise<void>;
  guard: Guard;
  onDirty: (dirty: boolean) => void;
}) {
  const t = useTranslation();
  const [editing, setEditing] = useState<Model | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // The values the form was opened with: anything else is dirty and asks
  // before it is thrown away.
  const [snapshot, setSnapshot] = useState<FormState>(EMPTY_FORM);
  const [saveFailed, setSaveFailed] = useState(false);
  const [deleteRefused, setDeleteRefused] = useState<"default" | "other" | null>(null);
  const [testResults, setTestResults] = useState<Record<string, ModelTestResult>>({});
  // The actions' failure (default flip, probe) speaks its own words beside
  // the form's save refusal: a refused save is not an unreachable service.
  const [failure, setFailure] = useState(false);

  const dirty = dirtyFields(form, snapshot).length > 0;
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);

  /** One form field's change, by its key in the form state. */
  function set<K extends keyof FormState>(key: K, value: string): void {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function startEditing(model: Model): void {
    void (async () => {
      if (dirty && !(await guard.ask())) return;
      setEditing(model);
      setForm(formOf(model));
      setSnapshot(formOf(model));
      setSaveFailed(false);
    })();
  }

  /** Close the form without a question — after a save it holds nothing new. */
  function resetForm(): void {
    setEditing(null);
    setForm(EMPTY_FORM);
    setSnapshot(EMPTY_FORM);
    setSaveFailed(false);
  }

  function stopEditing(): void {
    void (async () => {
      if (dirty && !(await guard.ask())) return;
      resetForm();
    })();
  }

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (form.name.trim() === "" || form.providerId === "" || form.model.trim() === "") return;
    if (editing === null) {
      const { response } = await client.POST("/api/settings/models", {
        body: {
          name: form.name.trim(),
          provider_id: form.providerId,
          model: form.model.trim(),
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
      if (!response.ok) {
        setSaveFailed(true);
        return;
      }
      resetForm();
      await reload();
      return;
    }
    // An edit sends every column explicitly: an emptied field clears it
    // (present nulls clear), which is what a form full of values means —
    // the tuning columns included, or a cleared value would silently keep
    // governing every request.
    const { response } = await client.PATCH("/api/settings/models/{model_id}", {
      params: { path: { model_id: editing.id } },
      body: {
        name: form.name.trim(),
        provider_id: form.providerId,
        model: form.model.trim(),
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
    resetForm();
    await reload();
  }

  async function makeDefault(model: Model): Promise<void> {
    setFailure(false);
    try {
      const { response } = await client.PATCH("/api/settings/models/{model_id}", {
        params: { path: { model_id: model.id } },
        body: { is_default: true },
      });
      if (!response.ok) {
        setFailure(true);
        return;
      }
      await reload();
    } catch {
      // A rejected fetch has no response to inspect: the page still says so,
      // in the same place a server-reachable failure appears.
      setFailure(true);
    }
  }

  async function remove(model: Model): Promise<void> {
    try {
      const { response } = await client.DELETE("/api/settings/models/{model_id}", {
        params: { path: { model_id: model.id } },
      });
      if (response.ok) {
        setDeleteRefused(null);
        await reload();
        return;
      }
      // The 409 is the default guard: its message names the way out, so the
      // page names it too — in the reader's language, not the server's.
      setDeleteRefused(response.status === 409 ? "default" : "other");
    } catch {
      // A rejected fetch has no response to inspect: the page still says so,
      // in the same place a server-reachable failure appears.
      setDeleteRefused("other");
    }
  }

  async function testConnection(model: Model): Promise<void> {
    setFailure(false);
    try {
      const { data, response } = await client.POST("/api/settings/models/{model_id}/test", {
        params: { path: { model_id: model.id } },
      });
      if (response.ok && data) {
        setTestResults((current) => ({ ...current, [model.id]: data }));
        return;
      }
    } catch {
      // A rejected fetch has no response to inspect: the page still says so.
    }
    setFailure(true);
  }

  return (
    <section aria-labelledby="settings-models-heading" className="mt-5">
      <h2 id="settings-models-heading" className="text-emph font-semibold">
        {t("settings.models")}
      </h2>

      {saveFailed ? (
        <Notice tone="danger" live="alert" className="mt-3">
          {t("settings.profiles.errorSave")}
        </Notice>
      ) : null}
      {failure ? (
        <Notice tone="danger" live="alert" className="mt-3">
          {t("settings.profiles.errorAction")}
        </Notice>
      ) : null}
      {deleteRefused !== null ? (
        <Notice tone="danger" live="alert" className="mt-3">
          {deleteRefused === "default"
            ? t("settings.profiles.errorDefaultDelete")
            : t("settings.profiles.errorDelete")}
        </Notice>
      ) : null}

      {models === null ? null : models.length === 0 ? (
        <Notice tone="quiet" className="mt-3">
          {t("settings.profiles.empty")}
        </Notice>
      ) : (
        <Panel dense className="mt-3">
          <ul className="flex flex-col">
            {models.map((model) => {
              const result = testResults[model.id];
              return (
                <li
                  key={model.id}
                  className="border-b border-rule py-3 first:pt-0 last:border-b-0 last:pb-0"
                >
                  <p className="flex flex-wrap items-baseline gap-2 text-body font-medium">
                    {model.name}
                    {model.is_default ? (
                      <span className="rounded-full bg-panel px-2 py-0.5 text-label">
                        {t("settings.profiles.defaultBadge")}
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-1 min-w-0 break-words text-body text-muted">
                    {model.provider_name}
                    {" · "}
                    {model.model}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {!model.is_default ? (
                      <Button variant="secondary" onClick={() => void makeDefault(model)}>
                        {t("settings.profiles.makeDefault")}
                      </Button>
                    ) : null}
                    <Button variant="secondary" onClick={() => startEditing(model)}>
                      {t("settings.profiles.edit")}
                    </Button>
                    <Button variant="secondary" onClick={() => void testConnection(model)}>
                      {t("settings.profiles.test")}
                    </Button>
                    <Button variant="secondary" onClick={() => void remove(model)}>
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
        <Field label={t("settings.profiles.providerLabel")} className={LABEL_ROW}>
          <Select
            value={form.providerId}
            onChange={(event) => set("providerId", event.target.value)}
          >
            {form.providerId === "" ? (
              // The create starts with no provider named: the blank select
              // says so out loud, instead of sitting silently on a disabled
              // save. An edit always opens with the stored provider named.
              <option value="" disabled>
                {t("settings.profiles.chooseProvider")}
              </option>
            ) : null}
            {(providers ?? []).map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("settings.profiles.modelLabel")} className={LABEL_ROW}>
          <Input
            value={form.model}
            onChange={(event) => set("model", event.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
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
          {/* The save is this section's one filled primary (L1); the
              cancel beside it is a bordered equal. */}
          <Button
            type="submit"
            variant="primary"
            disabled={
              form.name.trim() === "" || form.providerId === "" || form.model.trim() === ""
            }
          >
            {editing === null ? t("settings.profiles.create") : t("settings.profiles.save")}
          </Button>
          {editing === null ? null : (
            <Button variant="secondary" onClick={stopEditing}>
              {t("settings.profiles.cancel")}
            </Button>
          )}
        </div>
      </form>
    </section>
  );
}
