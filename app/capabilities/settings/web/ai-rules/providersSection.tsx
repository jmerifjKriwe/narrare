/**
 * The Provider section (W8 Task 9) — the approved draft's first section on
 * the shell's tokens: the guarantee banner, the provider cards with their
 * masks, and the create form with the key-once moment.
 *
 * Honest states throughout — the draft's sample data is draft data, the
 * real rows answer everywhere:
 *
 * - No handshake, no heartbeat, no „zuletzt geprüft“: the backend answers
 *   no provider health, so the cards claim none. The mask (`sk-…xxxx`) is
 *   the only key face any read shows — the full key rode exactly one
 *   response, the create's, and the create form's success face is where the
 *   surface shows it once (the key-once moment); the grid re-asks the mask.
 * - The delete guard's 409 names the models still pointed at the provider;
 *   the family face renders the copy family's sentence in the reader's
 *   language — the wire's English detail stays out. The 503 key-store face
 *   and the create/update refusals wear their families the same way.
 * - The draft's per-card „Verbindung testen“ button is not ported: the
 *   backend tests MODELS (`POST /models/{id}/test`), never providers — a
 *   provider-level button would be a dead promise. The test lives on the
 *   model cards, where the wire exists.
 */
import { useState, type FormEvent } from "react";

import type { Provider, Preset } from "@shell/lib/api/client";
import { catalogs } from "@shell/lib/generated/catalogs";
import { useTranslation } from "@shell/lib/i18n";
import type { MessageKey } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import { useCreateProvider, useDeleteProvider, useUpdateProvider, type WireError } from "../aiRulesQuery";

const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

const INPUT =
  "h-9 w-full rounded border border-border bg-surface-container-lowest px-3 text-body text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus";

const BUTTON =
  `inline-flex items-center gap-1.5 rounded bg-soft px-3 py-1 text-label text-foreground transition-colors hover:bg-surface-container-high ${FOCUS}`;

const GHOST_BUTTON =
  `rounded px-2.5 py-1 text-label text-danger transition-colors hover:bg-danger/10 ${FOCUS}`;

/** The refusal family a wire error's status names: the copy the surface
 *  owes each code — 409 the guard, 502 the unreachable endpoint, 503 the
 *  key store, 422 the atelier's own refusal, anything else the loss-free
 *  line. */
export function familyKey(status: number | undefined): MessageKey {
  switch (status) {
    case 409:
      return "settings.ai.errors.guarded";
    case 502:
      return "settings.ai.errors.unreachable";
    case 503:
      return "settings.ai.errors.keystore";
    case 422:
      return "settings.refused";
    default:
      return "settings.ai.errors.generic";
  }
}

/** The backend's own sentence, when one rode the refusal, is not the face's
 *  copy: the family sentence speaks the reader's language, and the code — not
 *  the wire's English — is what names the refusal. */
export function FamilyFace({ error, family }: { error: WireError | null; family?: MessageKey }) {
  const t = useTranslation();
  if (error === null) return null;
  return (
    <div role="alert" className="space-y-1 rounded border border-danger/40 bg-panel px-3 py-2">
      <p className="text-meta text-danger">{t(family ?? familyKey(error.status))}</p>
    </div>
  );
}

/** The create form's selection: a preset row (the endpoint facts it fills)
 *  or the free endpoint. The kind is never a free-typed word — the kernel's
 *  closed vocabulary answers through the preset, and the custom entry is an
 *  OpenAI-compatible endpoint. */
type Selection = { kind: "preset"; preset: Preset } | { kind: "custom" };

/** The presets' note key rides the wire as a string; the catalog's own key
 *  union is the gate — a note the catalogs do not carry renders as nothing
 *  rather than as a broken lookup. */
function isCatalogKey(key: string): key is MessageKey {
  return key in catalogs.en;
}

export function ProvidersSection({ providers, presets }: { providers: Provider[]; presets: Preset[] }) {
  const t = useTranslation();
  const createProvider = useCreateProvider();
  const updateProvider = useUpdateProvider();
  const deleteProvider = useDeleteProvider();

  // The create form's answers; `presetId === ""` is the custom endpoint.
  const [presetId, setPresetId] = useState(presets[0]?.id ?? "");
  const [name, setName] = useState("");
  const [baseUrl, setBaseUrl] = useState(presets[0]?.base_url ?? "");
  const [apiKey, setApiKey] = useState("");
  // The key-once face: the create's one answer, held until Fertig.
  const [created, setCreated] = useState<ProviderCreatedFace | null>(null);
  const [createError, setCreateError] = useState<WireError | null>(null);

  // The inline edit and the delete's family faces, per provider: one edit
  // stands at a time, a delete's refusal stays on the card that asked.
  const [editId, setEditId] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editBaseUrl, setEditBaseUrl] = useState("");
  const [editApiKey, setEditApiKey] = useState("");
  const [editError, setEditError] = useState<WireError | null>(null);
  const [deleteErrors, setDeleteErrors] = useState<Record<string, WireError>>({});

  const selected: Selection =
    presetId === ""
      ? { kind: "custom" }
      : { kind: "preset", preset: presets.find((entry) => entry.id === presetId) ?? presets[0] };

  function choosePreset(next: string) {
    setPresetId(next);
    if (next === "") {
      setBaseUrl("");
      return;
    }
    const preset = presets.find((entry) => entry.id === next);
    if (preset !== undefined) setBaseUrl(preset.base_url);
  }

  function submitCreate(event: FormEvent) {
    event.preventDefault();
    setCreateError(null);
    const body = {
      name: name.trim(),
      kind: selected.kind === "preset" ? selected.preset.kind : "openai-chat",
      base_url: baseUrl.trim() === "" ? null : baseUrl.trim(),
      models_url: selected.kind === "preset" ? selected.preset.models_url : null,
      vendor: selected.kind === "preset" ? selected.preset.vendor : null,
      api_key: apiKey === "" ? null : apiKey,
    };
    createProvider.mutate(body, {
      onSuccess: (row) => {
        // The key-once moment: the create's answer is the only carrier.
        // The face holds the row until Fertig; the grid below already
        // answers with the mask.
        setCreated({ name: row.name, apiKey: row.api_key ?? null });
        setName("");
        setApiKey("");
        setBaseUrl(selected.kind === "preset" ? selected.preset.base_url : "");
      },
      onError: (cause) => setCreateError(cause),
    });
  }

  function submitEdit(id: string) {
    setEditError(null);
    // Only what the edit carries rides: an empty key field keeps the stored
    // key (clearing is not an operation, only replacing is), and the body
    // carries no api_key key at all in that case.
    const changes: { name: string; base_url: string | null; api_key?: string } = {
      name: editName.trim(),
      base_url: editBaseUrl.trim() === "" ? null : editBaseUrl.trim(),
    };
    if (editApiKey !== "") changes.api_key = editApiKey;
    updateProvider.mutate(
      { id, changes },
      {
        onSuccess: () => {
          setEditId(null);
          setEditApiKey("");
        },
        onError: (cause) => setEditError(cause),
      },
    );
  }

  const createBusy = createProvider.isPending;
  const editBusy = updateProvider.isPending;

  return (
    <section id="sektion-provider" aria-labelledby="ai-rules-providers-heading" className="space-y-4">
      <div className="flex items-center gap-3">
        <h2 id="ai-rules-providers-heading" className="text-title font-semibold text-foreground">
          {t("settings.ai.section.providers")}
        </h2>
        <span className="rounded bg-surface-container-high px-2 py-0.5 text-meta font-semibold text-primary">
          {t("settings.ai.providers.badge", { count: providers.length })}
        </span>
      </div>

      {/* The guarantee banner — the draft's card, its conditional copy. */}
      <div className="flex items-start gap-3.5 rounded-lg border border-border bg-surface p-4 shadow-sm">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded bg-success/10 text-success">
          <Icon name="shield" size={17} />
        </span>
        <div className="space-y-1">
          <p className="text-label font-semibold text-foreground">{t("settings.ai.guarantee.title")}</p>
          <p className="text-body leading-relaxed text-muted">{t("settings.ai.guarantee.body")}</p>
        </div>
      </div>

      {/* The provider cards. */}
      {providers.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-meta text-muted">
          {t("settings.ai.providers.empty")}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          {providers.map((provider) => {
            const local = provider.base_url === null || provider.kind === "fake";
            return (
              <article
                key={provider.id}
                data-testid="provider-card"
                className="flex flex-col justify-between space-y-4 rounded-lg border border-border bg-card p-5 shadow-sm"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-center gap-2.5">
                      <span className="flex h-9 w-9 items-center justify-center rounded bg-background text-foreground">
                        <Icon name={local ? "house" : "globe"} size={18} />
                      </span>
                      <div>
                        <h3 className="text-emph font-semibold text-foreground">{provider.name}</h3>
                        <p className="text-meta text-muted">
                          {provider.vendor ?? provider.kind}
                        </p>
                      </div>
                    </div>
                    <span
                      title={provider.kind}
                      className="rounded bg-surface-container px-2 py-0.5 text-eyebrow uppercase tracking-wider text-muted"
                    >
                      {provider.vendor ?? provider.kind}
                    </span>
                  </div>

                  <div className="space-y-2 pt-1">
                    <span className="block text-eyebrow uppercase tracking-wider text-muted">
                      {t("settings.ai.provider.endpoint")}
                    </span>
                    {provider.base_url === null ? (
                      <div className="rounded bg-background px-2.5 py-1.5 text-meta text-muted">
                        {t("settings.ai.provider.noEndpoint")}
                      </div>
                    ) : (
                      <div className="select-all rounded bg-background px-2.5 py-1.5 font-mono text-meta text-foreground">
                        {provider.base_url}
                      </div>
                    )}

                    <div className="flex items-center justify-between pt-1 text-meta text-muted">
                      <span className="inline-flex items-center gap-1.5">
                        <Icon name={provider.api_key_mask === null ? "info" : "lock"} size={14} />
                        {provider.api_key_mask === null
                          ? t("settings.ai.provider.key.none")
                          : t("settings.ai.provider.key.vault")}
                      </span>
                    </div>
                    {provider.api_key_mask !== null && (
                      <div className="space-y-1">
                        <span className="block text-eyebrow uppercase tracking-wider text-muted">
                          {t("settings.ai.provider.key.masked")}
                        </span>
                        <div className="select-all rounded bg-background px-2.5 py-1.5 font-mono text-meta text-muted">
                          {provider.api_key_mask}
                        </div>
                        <p className="pt-0.5 text-meta text-muted">{t("settings.ai.provider.key.note")}</p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-end gap-2 border-t border-rule pt-2">
                  {deleteErrors[provider.id] !== undefined && (
                    <div className="mr-auto">
                      <FamilyFace error={deleteErrors[provider.id]} />
                    </div>
                  )}
                  {editId === provider.id ? (
                    /* The inline edit: name, endpoint, key replacement. The
                       kind is what the provider is — not editable. */
                    <form
                      className="w-full space-y-3"
                      onSubmit={(event) => {
                        event.preventDefault();
                        submitEdit(provider.id);
                      }}
                    >
                      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <label className="space-y-1">
                          <span className="block text-eyebrow uppercase tracking-wider text-muted">
                            {t("settings.ai.create.name")}
                          </span>
                          <input
                            type="text"
                            value={editName}
                            maxLength={120}
                            onChange={(event) => setEditName(event.target.value)}
                            className={INPUT}
                          />
                        </label>
                        <label className="space-y-1">
                          <span className="block text-eyebrow uppercase tracking-wider text-muted">
                            {t("settings.ai.create.baseUrl")}
                          </span>
                          <input
                            type="text"
                            value={editBaseUrl}
                            onChange={(event) => setEditBaseUrl(event.target.value)}
                            className={`${INPUT} font-mono text-meta`}
                          />
                        </label>
                      </div>
                      <label className="space-y-1">
                        <span className="block text-eyebrow uppercase tracking-wider text-muted">
                          {t("settings.ai.provider.editKey")}
                        </span>
                        <input
                          type="password"
                          value={editApiKey}
                          autoComplete="off"
                          onChange={(event) => setEditApiKey(event.target.value)}
                          className={INPUT}
                        />
                      </label>
                      <span className="block text-[11px] text-muted">{t("settings.ai.provider.editKeyHint")}</span>
                      {editError !== null && <FamilyFace error={editError} />}
                      <div className="flex items-center justify-end gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            setEditId(null);
                            setEditError(null);
                            setEditApiKey("");
                          }}
                          className={BUTTON}
                        >
                          {t("settings.ai.cancel")}
                        </button>
                        <button
                          type="submit"
                          disabled={editBusy}
                          className={`rounded bg-primary px-4 py-1 text-label font-semibold text-primary-foreground shadow-sm transition-colors hover:opacity-95 ${FOCUS} ${editBusy ? "cursor-not-allowed opacity-60" : ""}`}
                        >
                          {t("settings.ai.save")}
                        </button>
                      </div>
                    </form>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          setEditId(provider.id);
                          setEditName(provider.name);
                          setEditBaseUrl(provider.base_url ?? "");
                          setEditError(null);
                          setDeleteErrors((current) => {
                            const next = { ...current };
                            delete next[provider.id];
                            return next;
                          });
                        }}
                        className={BUTTON}
                      >
                        {t("settings.ai.provider.edit")}
                      </button>
                      <button
                        type="button"
                        title={t("settings.ai.provider.removeTitle")}
                        onClick={() => {
                          setDeleteErrors((current) => {
                            const next = { ...current };
                            delete next[provider.id];
                            return next;
                          });
                          deleteProvider.mutate(
                            { id: provider.id },
                            { onError: (cause) => setDeleteErrors((current) => ({ ...current, [provider.id]: cause })) },
                          );
                        }}
                        className={GHOST_BUTTON}
                      >
                        {t("settings.ai.provider.remove")}
                      </button>
                    </>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {/* The create form card — or, after a landed create, the key-once
          face until Fertig retires it. */}
      <div className="space-y-4 rounded-lg border border-border bg-panel p-5 shadow-sm">
        {created !== null ? (
          <div data-testid="key-once-face" className="space-y-3">
            <div className="flex items-center gap-2">
              <span className="text-success">
                <Icon name="checkCircle" size={18} />
              </span>
              <p className="text-emph font-semibold text-foreground">{t("settings.ai.created.title")}</p>
            </div>
            <p className="text-meta text-muted">
              {created.name} ·{" "}
              {created.apiKey === null
                ? t("settings.ai.created.noKey")
                : t("settings.ai.created.keyOnce")}
            </p>
            {created.apiKey !== null && (
              <div
                data-testid="created-key"
                className="select-all break-all rounded bg-background px-2.5 py-1.5 font-mono text-meta text-foreground"
              >
                {created.apiKey}
              </div>
            )}
            <button type="button" onClick={() => setCreated(null)} className={BUTTON}>
              {t("settings.ai.created.done")}
            </button>
          </div>
        ) : (
          <form className="space-y-4" onSubmit={submitCreate}>
            <div className="space-y-0.5">
              <div className="flex items-center gap-2">
                <span className="text-emph font-semibold text-foreground">{t("settings.ai.create.title")}</span>
                <span className="rounded bg-surface px-1.5 py-0.5 text-eyebrow uppercase tracking-wider text-muted">
                  {t("settings.ai.create.badge")}
                </span>
              </div>
              <p className="text-meta text-muted">{t("settings.ai.create.sub")}</p>
            </div>
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <label className="space-y-1">
                <span className="block text-label font-medium text-foreground">{t("settings.ai.create.preset")}</span>
                <div className="relative">
                  <select
                    value={presetId}
                    onChange={(event) => choosePreset(event.target.value)}
                    className={`${INPUT} appearance-none pr-8`}
                  >
                    {presets.map((preset) => (
                      <option key={preset.id} value={preset.id}>
                        {preset.label}
                      </option>
                    ))}
                    <option value="">{t("settings.ai.create.presetCustom")}</option>
                  </select>
                  <span className="pointer-events-none absolute right-2.5 top-2.5 text-muted">
                    <Icon name="selectChevron" size={14} />
                  </span>
                </div>
                {selected.kind === "preset" && selected.preset.note_key !== null && isCatalogKey(selected.preset.note_key) && (
                  <span className="block text-[11px] leading-relaxed text-muted">{t(selected.preset.note_key)}</span>
                )}
              </label>
              <label className="space-y-1">
                <span className="block text-label font-medium text-foreground">{t("settings.ai.create.name")}</span>
                <input
                  type="text"
                  value={name}
                  maxLength={120}
                  required
                  placeholder={t("settings.ai.create.namePlaceholder")}
                  onChange={(event) => setName(event.target.value)}
                  className={INPUT}
                />
              </label>
              <label className="space-y-1">
                <span className="block text-label font-medium text-foreground">{t("settings.ai.create.baseUrl")}</span>
                <input
                  type="text"
                  value={baseUrl}
                  required
                  onChange={(event) => setBaseUrl(event.target.value)}
                  className={`${INPUT} font-mono text-meta`}
                />
              </label>
              <label className="space-y-1">
                <span className="block text-label font-medium text-foreground">{t("settings.ai.create.apiKey")}</span>
                <input
                  type="password"
                  value={apiKey}
                  autoComplete="off"
                  placeholder={t("settings.ai.create.apiKeyPlaceholder")}
                  onChange={(event) => setApiKey(event.target.value)}
                  className={INPUT}
                />
              </label>
              <span className="block text-[11px] leading-relaxed text-muted">{t("settings.ai.create.apiKeyHint")}</span>
            </div>
            {createError !== null && <FamilyFace error={createError} />}
            <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
              <button
                type="submit"
                disabled={createBusy}
                className={`inline-flex items-center gap-1.5 rounded bg-primary px-4 py-1.5 text-label font-semibold text-primary-foreground shadow-sm transition-colors hover:opacity-95 ${FOCUS} ${createBusy ? "cursor-not-allowed opacity-60" : ""}`}
              >
                <Icon name="plus" size={15} />
                {createBusy ? t("settings.saving") : t("settings.ai.create.submit")}
              </button>
            </div>
          </form>
        )}
      </div>
    </section>
  );
}

/** The key-once face's held answer: the row's name and the one plaintext. */
type ProviderCreatedFace = { name: string; apiKey: string | null };
