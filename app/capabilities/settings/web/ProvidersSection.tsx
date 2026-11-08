import { useEffect, useId, useState } from "react";

import { dirtyFields } from "@shell/lib/dirty";
import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { Button } from "@shell/ui/Button";
import { Field, Input, Select } from "@shell/ui/field";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

import { client } from "@shell/lib/api/client";
import type { components } from "@shell/lib/api/schema";

export type Provider = components["schemas"]["ProviderRead"];
export type Preset = components["schemas"]["PresetRead"];

/**
 * The model a preset-created provider suggests to the model form: the
 * seed's token makes it one-shot — a second save of the model form, or an
 * edit, never re-seeds from the same emission — and its provider id points
 * the model form's provider select at the row just stored.
 */
export type ModelSeed = { providerId: string; model: string; token: number };

/** The kinds the form offers; the server's provider vocabulary is exactly these three. */
export const KINDS: readonly string[] = ["fake", "openai-chat", "anthropic"];

export const KIND_LABELS: Record<string, MessageKey> = {
  fake: "settings.providers.kind.fake",
  "openai-chat": "settings.providers.kind.openai-chat",
  anthropic: "settings.providers.kind.anthropic",
};

/**
 * The one label grid this panel's forms speak: the label sits in the grid's
 * own 128 px track, the control beside it at the field's 28 px. The column
 * comes from the track, never from a sized label — and `grid` appended after
 * `Field`'s own `flex` is what turns the field into the row (the E2E pins the
 * computed `gridTemplateColumns`, so a Tailwind reorder that let the stack
 * win again goes red loudly instead of drifting quietly).
 */
export const LABEL_ROW = "grid grid-cols-[128px_minmax(0,1fr)] items-center gap-x-2";

/** The guard a form section shares with the panel: who asks, and whether. */
export type Guard = {
  /** True while any form on the page holds typed values. */
  dirty: boolean;
  /** Ask before typed values are discarded; false means "stay". */
  ask: () => Promise<boolean>;
};

/** One text field of the provider form, as the input holds it. */
type FormState = {
  name: string;
  kind: string;
  baseUrl: string;
  modelsUrl: string;
  vendor: string;
  apiKey: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  kind: "fake",
  baseUrl: "",
  modelsUrl: "",
  vendor: "",
  apiKey: "",
};

/** A provider's columns as the form holds them: every value a string. */
function formOf(provider: Provider): FormState {
  return {
    name: provider.name,
    kind: provider.kind,
    baseUrl: provider.base_url ?? "",
    modelsUrl: provider.models_url ?? "",
    vendor: provider.vendor ?? "",
    // The key is never prefilled: no read carries it, and the field means
    // "replace", with emptiness meaning "keep" (the hint below says so).
    apiKey: "",
  };
}

/**
 * The providers section: the saved endpoints their models hang off, with the
 * create and edit form and the per-provider actions. The row is the endpoint
 * facts — kind, base URL, models URL, vendor — and the one secret of the
 * page: its key shows exactly once (the create's), every later read the mask.
 *
 * Creating starts at the preset select: one choice fills the endpoint fields
 * and clears the key, so a known vendor is one click from "no providers
 * yet". Every filled field stays editable, and "Custom provider" — the
 * blank form — is the default. The select speaks only while creating: an
 * edit is what the provider already is.
 *
 * The section's one filled primary is the form's save (L1); every other
 * control is a bordered equal. The states speak through `Notice`: the empty
 * list, the save and delete refusals, and the row's own model discovery.
 */
export function ProvidersSection({
  providers,
  presets,
  reload,
  guard,
  onDirty,
  onPresetCreated,
}: {
  providers: Provider[] | null;
  presets: Preset[] | null;
  reload: () => Promise<void>;
  guard: Guard;
  onDirty: (dirty: boolean) => void;
  /** The panel's ear: a preset-created provider names itself and its model. */
  onPresetCreated: (providerId: string, model: string) => void;
}) {
  const t = useTranslation();
  const [editing, setEditing] = useState<Provider | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // The values the form was opened with: anything else is dirty and asks
  // before it is thrown away.
  const [snapshot, setSnapshot] = useState<FormState>(EMPTY_FORM);
  // The preset the form currently reflects, "" for the blank custom form.
  // Not a form column: it names how the fields were filled, not what saves.
  const [presetId, setPresetId] = useState("");
  const [created, setCreated] = useState<{ name: string; apiKey: string } | null>(null);
  const [saveFailed, setSaveFailed] = useState(false);
  const [deleteRefused, setDeleteRefused] = useState<"in-use" | "other" | null>(null);
  const [models, setModels] = useState<Record<string, string[] | "failed">>({});
  // The stored-key hint's and the preset note's ids: wired to their controls
  // by hand, because both belong to the control's column of the grid row
  // (Field's own hint would land under the label).
  const apiKeyHintId = useId();
  const presetNoteId = useId();

  const dirty = dirtyFields(form, snapshot).length > 0;
  useEffect(() => {
    onDirty(dirty);
  }, [dirty, onDirty]);

  /** One form field's change, by its key in the form state. */
  function set<K extends keyof FormState>(key: K, value: string): void {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function startEditing(provider: Provider): void {
    void (async () => {
      if (dirty && !(await guard.ask())) return;
      setEditing(provider);
      setPresetId("");
      setForm(formOf(provider));
      setSnapshot(formOf(provider));
      setSaveFailed(false);
    })();
  }

  /** Close the form without a question — after a save it holds nothing new. */
  function resetForm(): void {
    setEditing(null);
    setPresetId("");
    setForm({ ...EMPTY_FORM, kind: "fake" });
    setSnapshot({ ...EMPTY_FORM, kind: "fake" });
    setSaveFailed(false);
  }

  function stopEditing(): void {
    void (async () => {
      if (dirty && !(await guard.ask())) return;
      resetForm();
    })();
  }

  /**
   * The preset choice: fill the endpoint fields from it, clear the key, and
   * take the fill as the form's new baseline — only edits after the choice
   * are dirty and ask. "Custom provider" is the blank form again. The
   * choice replaces typed values without asking: choosing it *is* the
   * deliberate act, and every field stays editable afterwards.
   */
  function choosePreset(id: string): void {
    setPresetId(id);
    const chosen = presets?.find((preset) => preset.id === id) ?? null;
    if (chosen === null) {
      setForm({ ...EMPTY_FORM, kind: "fake" });
      setSnapshot({ ...EMPTY_FORM, kind: "fake" });
      // The blank form is a fresh start too: a failed save before the
      // choice was the old attempt's failure, not this one's.
      setSaveFailed(false);
      return;
    }
    const filled: FormState = {
      name: chosen.label,
      kind: chosen.kind,
      baseUrl: chosen.base_url,
      modelsUrl: chosen.models_url ?? "",
      vendor: chosen.vendor,
      // A preset never carries a key over: the field the choice clears.
      apiKey: "",
    };
    setForm(filled);
    setSnapshot(filled);
    setSaveFailed(false);
  }

  const chosenPreset = presets?.find((preset) => preset.id === presetId) ?? null;

  async function submit(event: React.FormEvent): Promise<void> {
    event.preventDefault();
    if (form.name.trim() === "") return;
    // An empty key field never reaches the body: only replacing a key is an
    // operation, and "keep the stored one" is the absence of one.
    const apiKey = form.apiKey.trim() === "" ? {} : { api_key: form.apiKey.trim() };
    // The preset the create rode in on: its model becomes the model form's
    // seed, once, when the provider is stored. Captured before resetForm
    // clears the choice.
    const presetModel = editing === null ? (chosenPreset?.model ?? null) : null;
    if (editing === null) {
      const { data, response } = await client.POST("/api/settings/providers", {
        body: {
          name: form.name.trim(),
          kind: form.kind,
          ...(form.baseUrl.trim() === "" ? {} : { base_url: form.baseUrl.trim() }),
          ...(form.modelsUrl.trim() === "" ? {} : { models_url: form.modelsUrl.trim() }),
          ...(form.vendor.trim() === "" ? {} : { vendor: form.vendor.trim() }),
          ...apiKey,
        },
      });
      if (!response.ok || data === undefined) {
        setSaveFailed(true);
        return;
      }
      // The one response that carries the full key becomes the one box that
      // shows it; dismissed, it never exists again anywhere.
      if (data.api_key) setCreated({ name: data.name, apiKey: data.api_key });
      // The created provider is the model form's next subject: it names
      // itself so the form can point at it, with the preset's model as the
      // suggestion. A failed save emits nothing — nothing was stored.
      if (presetModel !== null) onPresetCreated(data.id, presetModel);
      resetForm();
      await reload();
      return;
    }
    // An edit sends every column explicitly: an emptied field clears it
    // (present nulls clear), which is what a form full of values means —
    // or a cleared endpoint would silently keep governing every call.
    const { response } = await client.PATCH("/api/settings/providers/{provider_id}", {
      params: { path: { provider_id: editing.id } },
      body: {
        name: form.name.trim(),
        base_url: form.baseUrl.trim() === "" ? null : form.baseUrl.trim(),
        models_url: form.modelsUrl.trim() === "" ? null : form.modelsUrl.trim(),
        vendor: form.vendor.trim() === "" ? null : form.vendor.trim(),
        ...apiKey,
      },
    });
    if (!response.ok) {
      setSaveFailed(true);
      return;
    }
    resetForm();
    await reload();
  }

  async function remove(provider: Provider): Promise<void> {
    try {
      const { response } = await client.DELETE("/api/settings/providers/{provider_id}", {
        params: { path: { provider_id: provider.id } },
      });
      if (response.ok) {
        setDeleteRefused(null);
        await reload();
        return;
      }
      // The 409 is the delete guard: its message names the models still
      // pointed here, so the page names the way out too — in the reader's
      // language, not the server's.
      setDeleteRefused(response.status === 409 ? "in-use" : "other");
    } catch {
      // A rejected fetch has no response to inspect: the page still says so,
      // in the same place a server-reachable failure appears.
      setDeleteRefused("other");
    }
  }

  async function discoverModels(provider: Provider): Promise<void> {
    const { data, response } = await client.GET("/api/settings/providers/{provider_id}/models", {
      params: { path: { provider_id: provider.id } },
    });
    // The outcome is data on the row either way: the ids, or the failure
    // the page can name while the endpoint cannot be asked.
    setModels((current) => ({
      ...current,
      [provider.id]: response.ok ? (data ?? []) : "failed",
    }));
  }

  return (
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
              {t("settings.providers.keyOnceDone")}
            </Button>
          }
        >
          {t("settings.providers.keyOnce", { name: created.name, key: created.apiKey })}
        </Notice>
      ) : null}

      {saveFailed ? (
        <Notice tone="danger" live="alert" className="mt-3">
          {t("settings.providers.errorSave")}
        </Notice>
      ) : null}
      {deleteRefused !== null ? (
        <Notice tone="danger" live="alert" className="mt-3">
          {deleteRefused === "in-use"
            ? t("settings.providers.errorInUse")
            : t("settings.providers.errorDelete")}
        </Notice>
      ) : null}

      {providers === null ? null : providers.length === 0 ? (
        <Notice tone="quiet" className="mt-3">
          {t("settings.providers.empty")}
        </Notice>
      ) : (
        <Panel dense className="mt-3">
          <ul className="flex flex-col">
            {providers.map((provider) => {
              const discovered = models[provider.id];
              return (
                <li
                  key={provider.id}
                  className="border-b border-rule py-3 first:pt-0 last:border-b-0 last:pb-0"
                >
                  <p className="flex flex-wrap items-baseline gap-2 text-body font-medium">
                    {provider.name}
                  </p>
                  <p className="mt-1 min-w-0 break-words text-body text-muted">
                    {KIND_LABELS[provider.kind] === undefined
                      ? provider.kind
                      : t(KIND_LABELS[provider.kind])}
                    {provider.base_url ? ` · ${provider.base_url}` : ""}
                    {provider.vendor ? ` · ${provider.vendor}` : ""}
                    {provider.api_key_mask ? ` · ${provider.api_key_mask}` : ""}
                  </p>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button variant="secondary" onClick={() => startEditing(provider)}>
                      {t("settings.providers.edit")}
                    </Button>
                    {provider.kind === "openai-chat" ? (
                      <Button variant="secondary" onClick={() => void discoverModels(provider)}>
                        {t("settings.providers.discover")}
                      </Button>
                    ) : null}
                    <Button variant="secondary" onClick={() => void remove(provider)}>
                      {t("settings.providers.delete")}
                    </Button>
                  </div>
                  {discovered === undefined ? null : (
                    <Notice
                      tone={discovered === "failed" ? "warning" : "quiet"}
                      live="status"
                      className="mt-2"
                    >
                      {discovered === "failed"
                        ? t("settings.providers.errorModels")
                        : t("settings.providers.models", { models: discovered.join(", ") })}
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
        {editing === null && presets !== null && presets.length > 0 ? (
          <Field label={t("settings.providers.presetLabel")} className={LABEL_ROW}>
            <Select
              value={presetId}
              onChange={(event) => choosePreset(event.target.value)}
              aria-describedby={chosenPreset?.note_key ? presetNoteId : undefined}
            >
              {/* The blank choice is the default: the form the page always
                  had, before the presets were one click away. */}
              <option value="">{t("settings.providers.presetCustom")}</option>
              {presets.map((preset) => (
                <option key={preset.id} value={preset.id}>
                  {preset.label}
                </option>
              ))}
            </Select>
            {chosenPreset?.note_key ? (
              <p id={presetNoteId} className="col-start-2 text-label text-muted">
                {t(chosenPreset.note_key as MessageKey)}
              </p>
            ) : null}
          </Field>
        ) : null}
        <Field label={t("settings.providers.nameLabel")} className={LABEL_ROW}>
          <Input
            value={form.name}
            onChange={(event) => set("name", event.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
        </Field>
        <Field label={t("settings.providers.kindLabel")} className={LABEL_ROW}>
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
        <Field label={t("settings.providers.baseUrlLabel")} className={LABEL_ROW}>
          <Input
            value={form.baseUrl}
            onChange={(event) => set("baseUrl", event.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
        </Field>
        <Field label={t("settings.providers.modelsUrlLabel")} className={LABEL_ROW}>
          <Input
            value={form.modelsUrl}
            onChange={(event) => set("modelsUrl", event.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
        </Field>
        <Field label={t("settings.providers.vendorLabel")} className={LABEL_ROW}>
          <Input
            value={form.vendor}
            onChange={(event) => set("vendor", event.target.value)}
            spellCheck={false}
            autoComplete="off"
          />
        </Field>
        <Field label={t("settings.providers.apiKeyLabel")} className={LABEL_ROW}>
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
              {t("settings.providers.apiKeyHint")}
            </p>
          ) : null}
        </Field>
        <div className="mt-2 flex items-center gap-2">
          {/* The save is this section's one filled primary (L1); the
              cancel beside it is a bordered equal. */}
          <Button type="submit" variant="primary" disabled={form.name.trim() === ""}>
            {editing === null ? t("settings.providers.create") : t("settings.providers.save")}
          </Button>
          {editing === null ? null : (
            <Button variant="secondary" onClick={stopEditing}>
              {t("settings.providers.cancel")}
            </Button>
          )}
        </div>
      </form>
    </section>
  );
}
