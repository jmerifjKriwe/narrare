/**
 * The Modelle section (W8 Task 9) — the approved draft's second section on
 * the shell's tokens: the registered models' grid with the default badge
 * and its handover, the connection test's running/ok/fail faces, the delete
 * for the non-default models, and the register form with the discovery
 * door.
 *
 * Honest states throughout:
 * - The stat tiles answer the model's own stored columns — an unset column
 *   is the honest „—“ („Keine Angabe“), never a drafted sample number. A
 *   model whose provider is the fake answers local: its inference tile says
 *   so, the provider row's kind being the fact's source.
 * - `in_catalog` and `last_error_code` are read-only marks: the catalog's
 *   check beside the name, the newest failed audit under the card — no
 *   invented „verifiziert“ beyond the fact's own name.
 * - The default model carries no Entfernen: the backend refuses it (409),
 *   and a button that can only ever fail is not drawn. Its assignments'
 *   count is the honest „Gebunden an: N“; a freed model says so.
 * - The draft's header discovery button is not ported: discovery asks ONE
 *   provider's endpoint, and the header named none — the door lives in the
 *   register form, beside the provider select it asks about (the 409 fake
 *   face, the 502 unreachable face, the empty answer's own line).
 * - The register form's provider select resolves its selection against
 *   the CURRENT list: a selection that names nothing (the first visit's
 *   empty answer before any provider existed, a provider since deleted)
 *   falls to the first available one — the shown first row is the value
 *   the submit and the discovery door send, never a ghost the guards
 *   silently swallow. The discovery's answers ride the provider they
 *   were asked about: a selection change hides them by derivation.
 */
import { useState, type FormEvent } from "react";

import type { Assignment, Model, Preset, Provider } from "@shell/lib/api/client";
import { formatNumber } from "@shell/lib/format";
import { useTranslation } from "@shell/lib/i18n";
import type { MessageKey } from "@shell/lib/i18n";
import { Icon } from "@shell/ui/icons";

import {
  useCreateModel,
  useDeleteModel,
  useProviderModels,
  useSetDefaultModel,
  useTestModel,
  type WireError,
} from "../aiRulesQuery";
import { FamilyFace, familyKey } from "./providersSection";

/** The discovery's own family map: a 409 here is the fake's no-endpoint
 *  face, never the delete guard's — the same code means a different refusal
 *  under a different door. */
function discoverFamily(status: number | undefined): MessageKey {
  if (status === 409) return "settings.ai.errors.noEndpoint";
  return familyKey(status);
}

const FOCUS =
  "focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus";

const INPUT =
  "h-9 w-full rounded border border-border bg-surface-container-lowest px-3 text-body text-foreground outline-none transition-shadow focus:border-focus focus:ring-1 focus:ring-focus";

const BUTTON =
  `inline-flex items-center gap-1.5 rounded bg-soft px-3 py-1 text-label text-foreground transition-colors hover:bg-surface-container-high ${FOCUS}`;

const PRIMARY_BUTTON =
  `inline-flex items-center gap-1.5 rounded bg-primary px-4 py-1.5 text-label font-semibold text-primary-foreground shadow-sm transition-colors hover:opacity-95 ${FOCUS}`;

/** One tile of the draft's four-cell grid: the eyebrow label over the
 *  stored value, the honest unset where the row answers none. */
function Stat({ label, value, tone }: { label: string; value: string; tone?: "ok" }) {
  return (
    <div className="rounded bg-surface p-2">
      <span className="block text-eyebrow uppercase tracking-wider text-muted">{label}</span>
      <span className={`font-semibold ${tone === "ok" ? "text-success" : "text-foreground"}`}>{value}</span>
    </div>
  );
}

export function ModelsSection({
  models,
  providers,
  presets,
  assignments,
}: {
  models: Model[];
  providers: Provider[];
  presets: Preset[];
  assignments: Assignment[];
}) {
  const t = useTranslation();
  const createModel = useCreateModel();
  const setDefault = useSetDefaultModel();
  const deleteModel = useDeleteModel();
  const testModel = useTestModel();
  const discover = useProviderModels();

  // The register form's answers and its faces. `open` is the draft's
  // „Modell registrieren“ door; the discovery state lives beside the
  // provider select it asks about.
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [providerId, setProviderId] = useState(providers[0]?.id ?? "");
  const [modelId, setModelId] = useState("");
  // The discovery's answers, keyed to the provider they were asked about:
  // a face never outlives the selection it belongs to — a provider change
  // (the select, or the list moving beneath the form) hides the stale
  // ids and the stale refusal by derivation, nothing cleared by hand.
  const [discovered, setDiscovered] = useState<{ providerId: string; ids: string[] } | null>(null);
  const [discoverError, setDiscoverError] = useState<{ providerId: string; error: WireError } | null>(null);
  const [formError, setFormError] = useState<WireError | null>(null);

  // The test faces and the delete's refusals, per model id — one card's
  // face never bleeds into its neighbours'.
  const [runningId, setRunningId] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, { ok: boolean; text: string }>>({});
  const [deleteErrors, setDeleteErrors] = useState<Record<string, WireError>>({});
  const [defaultError, setDefaultError] = useState<WireError | null>(null);

  // The honest bound count: the stored assignments pointing at each model,
  // read once for the grid.
  const boundByModel = new Map<string, number>();
  for (const assignment of assignments) {
    if (assignment.profile_id !== null) {
      boundByModel.set(assignment.profile_id, (boundByModel.get(assignment.profile_id) ?? 0) + 1);
    }
  }

  // The selection, resolved against the current list: a stored selection
  // that names nothing — the empty answer the form was opened under (the
  // first visit, before any provider existed), a provider since deleted —
  // falls to the first available one. The select's visible first row IS
  // the value the submit and the discovery door send: a shown selection
  // that silently returns is the dishonest face this surface does not
  // wear.
  const selectedId = providers.some((entry) => entry.id === providerId)
    ? providerId
    : (providers[0]?.id ?? "");
  const provider = providers.find((entry) => entry.id === selectedId);
  // The chosen provider's vendor row in the kernel's preset table: its
  // catalog vocabulary feeds the model-id datalist, the snapshot date is
  // the mark that says how old that knowledge is.
  const vendorPreset = presets.find((entry) => entry.vendor === provider?.vendor) ?? null;
  // The discovery faces, read only for the provider they belong to.
  const discoveredIds = discovered !== null && discovered.providerId === selectedId ? discovered.ids : null;
  const discoverErrorForForm =
    discoverError !== null && discoverError.providerId === selectedId ? discoverError.error : null;

  function askEndpoint() {
    if (provider === undefined) return;
    setDiscoverError(null);
    discover.mutate(
      { id: provider.id },
      {
        onSuccess: (ids) => {
          setDiscovered({ providerId: provider.id, ids });
        },
        onError: (cause) => {
          setDiscovered(null);
          setDiscoverError({ providerId: provider.id, error: cause });
        },
      },
    );
  }

  function submitRegister(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (provider === undefined) return;
    createModel.mutate(
      { name: name.trim(), provider_id: provider.id, model: modelId.trim() },
      {
        onSuccess: () => {
          setOpen(false);
          setName("");
          setModelId("");
          setDiscovered(null);
        },
        onError: (cause) => setFormError(cause),
      },
    );
  }

  function runTest(id: string) {
    setRunningId(id);
    testModel.mutate(
      { id },
      {
        onSuccess: (result) => {
          setRunningId(null);
          setResults((current) => ({
            ...current,
            [id]: {
              ok: result.ok,
              text: result.ok
                ? t("settings.ai.models.testOk", { ms: formatNumber(result.latency_ms) })
                : t("settings.ai.models.testFail", { error: result.error ?? "" }),
            },
          }));
        },
        onError: () => setRunningId(null),
      },
    );
  }

  const registerBusy = createModel.isPending;

  return (
    <section id="sektion-modelle" aria-labelledby="ai-rules-models-heading" className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-0.5">
          <h2 id="ai-rules-models-heading" className="text-title font-semibold text-foreground">
            {t("settings.ai.section.models")}
          </h2>
          <p className="text-meta text-muted">{t("settings.ai.models.sub")}</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setOpen((current) => !current)}
            aria-expanded={open}
            className={PRIMARY_BUTTON}
          >
            <Icon name="plus" size={15} />
            {t("settings.ai.models.register")}
          </button>
        </div>
      </div>

      {models.length === 0 ? (
        <p className="rounded-lg border border-border bg-card p-4 text-meta text-muted">
          {t("settings.ai.models.empty")}
        </p>
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {models.map((model) => {
            const isDefault = model.is_default;
            const bound = boundByModel.get(model.id) ?? 0;
            const result = results[model.id];
            // The inference tile's truth: a fake-kind provider answers on
            // this machine — the provider row's kind is the fact's source,
            // every other model wears its stored temperature.
            const local = providers.find((entry) => entry.id === model.provider_id)?.kind === "fake";
            return (
              <article
                key={model.id}
                data-testid="model-card"
                className="flex flex-col justify-between space-y-4 rounded-lg border border-border bg-card p-5 shadow-sm"
              >
                <div className="space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-1.5">
                        <h3 className="text-emph font-semibold text-foreground">{model.name}</h3>
                        {model.in_catalog && (
                          <span title={t("settings.ai.models.inCatalog")} className="text-success">
                            <Icon name="checkCircle" size={15} />
                          </span>
                        )}
                      </div>
                      <p className="text-meta text-muted">
                        {t("settings.ai.models.via", { provider: model.provider_name })}
                      </p>
                    </div>
                    {isDefault ? (
                      <span className="rounded bg-primary px-2 py-0.5 text-eyebrow uppercase tracking-wider text-primary-foreground">
                        {t("settings.ai.models.default")}
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          setDefaultError(null);
                          setDefault.mutate({ id: model.id }, { onError: (cause) => setDefaultError(cause) });
                        }}
                        className={`rounded bg-soft px-2 py-0.5 text-label text-muted transition-colors hover:bg-surface-container-high hover:text-foreground ${FOCUS}`}
                      >
                        {t("settings.ai.models.makeDefault")}
                      </button>
                    )}
                  </div>

                  <div
                    className="truncate rounded bg-background px-2 py-1 font-mono text-meta text-muted"
                    title={model.model}
                  >
                    {model.model}
                  </div>

                  <div className="grid grid-cols-2 gap-2 pt-1 text-meta text-muted">
                    <Stat
                      label={t("settings.ai.stat.context")}
                      value={
                        model.context_window === null
                          ? "—"
                          : `${formatNumber(model.context_window)} ${t("settings.ai.stat.tokens")}`
                      }
                    />
                    <Stat
                      label={t("settings.ai.stat.maxOut")}
                      value={
                        model.max_output_tokens === null
                          ? "—"
                          : `${formatNumber(model.max_output_tokens)} ${t("settings.ai.stat.tokens")}`
                      }
                    />
                    <Stat
                      label={t("settings.ai.stat.timeout")}
                      value={
                        model.request_timeout === null
                          ? "—"
                          : t("settings.ai.stat.seconds", { n: formatNumber(model.request_timeout) })
                      }
                    />
                    {local ? (
                      <Stat
                        label={t("settings.ai.stat.local")}
                        value={t("settings.ai.stat.localValue")}
                        tone="ok"
                      />
                    ) : (
                      <Stat
                        label={t("settings.ai.stat.temperature")}
                        value={model.temperature === null ? "—" : String(model.temperature)}
                      />
                    )}
                  </div>
                </div>

                <div className="space-y-2 border-t border-rule pt-3">
                  {model.last_error_code !== null && (
                    <p className="inline-flex items-center gap-1 text-meta font-medium text-danger">
                      <Icon name="warning" size={14} />
                      {t("settings.ai.models.lastError", { code: model.last_error_code })}
                    </p>
                  )}
                  {result !== undefined && (
                    <p className={`text-meta font-medium ${result.ok ? "text-success" : "text-danger"}`}>
                      {result.text}
                    </p>
                  )}
                  <div className="flex items-center justify-between text-meta">
                    <span className={bound > 0 ? "font-medium text-primary" : "text-muted"}>
                      {bound > 0
                        ? t("settings.ai.models.bound", { count: bound })
                        : t("settings.ai.models.unbound")}
                    </span>
                    <span className="flex items-center gap-2">
                      <button
                        type="button"
                        disabled={runningId === model.id}
                        onClick={() => runTest(model.id)}
                        className={`${BUTTON} ${runningId === model.id ? "cursor-wait text-muted" : ""}`}
                      >
                        <Icon name={runningId === model.id ? "refresh" : "radar"} size={14} />
                        {runningId === model.id ? t("settings.ai.models.testing") : t("settings.ai.models.test")}
                      </button>
                      {!isDefault && (
                        <button
                          type="button"
                          title={t("settings.ai.models.removeNote")}
                          onClick={() => {
                            setDeleteErrors((current) => {
                              const next = { ...current };
                              delete next[model.id];
                              return next;
                            });
                            deleteModel.mutate(
                              { id: model.id },
                              {
                                onError: (cause) =>
                                  setDeleteErrors((current) => ({ ...current, [model.id]: cause })),
                              },
                            );
                          }}
                          className={`rounded px-2.5 py-1 text-label text-danger transition-colors hover:bg-danger/10 ${FOCUS}`}
                        >
                          {t("settings.ai.models.remove")}
                        </button>
                      )}
                    </span>
                  </div>
                  {deleteErrors[model.id] !== undefined && <FamilyFace error={deleteErrors[model.id]} />}
                </div>
              </article>
            );
          })}
        </div>
      )}
      {defaultError !== null && <FamilyFace error={defaultError} />}

      {/* The register form: name, provider, model id — with the discovery
          door and the catalog datalist beside the provider select. */}
      {open && (
        <form
          className="space-y-4 rounded-lg border border-border bg-panel p-5 shadow-sm"
          onSubmit={submitRegister}
        >
          <div className="space-y-0.5">
            <span className="text-emph font-semibold text-foreground">{t("settings.ai.models.registerTitle")}</span>
            <p className="text-meta text-muted">{t("settings.ai.models.registerSub")}</p>
          </div>
          {providers.length === 0 ? (
            <p className="text-meta text-muted">{t("settings.ai.models.registerNoProvider")}</p>
          ) : (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <label className="space-y-1">
                <span className="block text-label font-medium text-foreground">{t("settings.ai.models.registerProvider")}</span>
                <div className="relative">
                  <select
                    value={selectedId}
                    onChange={(event) => setProviderId(event.target.value)}
                    className={`${INPUT} appearance-none pr-8`}
                  >
                    {providers.map((entry) => (
                      <option key={entry.id} value={entry.id}>
                        {entry.name}
                      </option>
                    ))}
                  </select>
                  <span className="pointer-events-none absolute right-2.5 top-2.5 text-muted">
                    <Icon name="selectChevron" size={14} />
                  </span>
                </div>
              </label>
              <label className="space-y-1">
                <span className="block text-label font-medium text-foreground">{t("settings.ai.models.registerName")}</span>
                <input
                  type="text"
                  value={name}
                  maxLength={120}
                  required
                  onChange={(event) => setName(event.target.value)}
                  className={INPUT}
                />
              </label>
              <div className="space-y-1 md:col-span-2">
                <label className="space-y-1">
                  <span className="block text-label font-medium text-foreground">{t("settings.ai.models.registerModel")}</span>
                  <input
                    type="text"
                    value={modelId}
                    maxLength={200}
                    required
                    list="ai-rules-model-ids"
                    placeholder={t("settings.ai.models.registerModelPlaceholder")}
                    onChange={(event) => setModelId(event.target.value)}
                    className={`${INPUT} font-mono text-meta`}
                  />
                </label>
                <datalist id="ai-rules-model-ids">
                  {(discoveredIds ?? vendorPreset?.models ?? []).map((id) => (
                    <option key={id} value={id} />
                  ))}
                </datalist>
                <div className="flex items-center gap-2 pt-1">
                  <button type="button" onClick={askEndpoint} disabled={discover.isPending} className={BUTTON}>
                    <Icon name={discover.isPending ? "refresh" : "radar"} size={14} />
                    {discover.isPending ? t("settings.ai.models.discovering") : t("settings.ai.models.discover")}
                  </button>
                </div>
                {vendorPreset !== null && vendorPreset.snapshot_date !== null && (
                  <span className="block text-[11px] text-muted">
                    {t("settings.ai.models.snapshot", { date: vendorPreset.snapshot_date })}
                  </span>
                )}
                {discoverErrorForForm !== null && (
                  <FamilyFace error={discoverErrorForForm} family={discoverFamily(discoverErrorForForm.status)} />
                )}
                {discoveredIds !== null && discoveredIds.length === 0 && discoverErrorForForm === null && (
                  <span className="block text-[11px] text-muted">{t("settings.ai.models.discoverEmpty")}</span>
                )}
                {discoveredIds !== null && discoveredIds.length > 0 && (
                  <span className="block text-[11px] text-muted">{t("settings.ai.models.discoverNote")}</span>
                )}
              </div>
            </div>
          )}
          {formError !== null && <FamilyFace error={formError} />}
          <div className="flex items-center justify-end gap-2 pt-2">
            <button type="button" onClick={() => setOpen(false)} className={BUTTON}>
              {t("settings.ai.cancel")}
            </button>
            <button
              type="submit"
              disabled={registerBusy || providers.length === 0}
              className={`${PRIMARY_BUTTON} ${registerBusy ? "cursor-not-allowed opacity-60" : ""}`}
            >
              <Icon name="plus" size={15} />
              {registerBusy ? t("settings.saving") : t("settings.ai.models.registerSubmit")}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
