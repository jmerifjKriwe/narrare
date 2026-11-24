/**
 * The Prompts surface (W8 Task 12) — the settings area's third page at
 * `/settings/prompts`, ported from the owner-approved `ai-prompts-overrides`
 * draft onto the shell's tokens, under the hub chrome. The draft's geometry,
 * in its order: the header row with the Geltungsbereich selector and the
 * novel-scope override badge, then the two-column core — the four-key
 * catalog left (its override marks read the list's real fields), the editor
 * right — and the Souveränitäts-Garantie card below the catalog.
 *
 * Porting dispositions from the Stitch round's owner checkpoint — none of
 * these are omissions, they are the honest-state rules at work:
 * - The Garantie card's `.narrare/prompts/` claim is not ported: overrides
 *   live in the local database, and the copy says so (the Stitch round
 *   audit's finding 6, decided correct-at-port).
 * - The header's „Lokaler Prompt-Speicher“ chip is not ported: invented
 *   chrome, no read answers it (the same finding's rule as the hub chip).
 * - The footer with its three dead links is not ported: dead promises (the
 *   AI-Regeln surface's own disposition).
 * - The draft's editorial flourish inside the editor header (the per-novel
 *   „Passe an, wie …“ line) is not ported: the key's real description — the
 *   catalog's own words — answers instead.
 *
 * The Geltungsbereich selector drives two reads at once: the catalog's
 * marks (the list with the novel id) and the editor's default tier (the
 * novel's own override, where the key is scopable). Honest page states:
 * the loading skeleton while the reads stand, the outage face with its
 * retry when any fails — never dressed-up nulls.
 */
import { useState, type ReactNode } from "react";

import { SettingsHub } from "@shell/components/SettingsHub";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { queryClient, useNovelsQuery } from "@shell/lib/query";
import { FOCUS } from "@shell/ui/card";
import { Icon, type IconName } from "@shell/ui/icons";

import { PromptEditor, type EditorScope } from "./PromptEditor";
import { usePromptDetail, usePromptsList, useResetPending, useResetPrompt, useResetRevision } from "./promptsQuery";

const SERIF = "[font-family:var(--font-serif)]";
const MONO = "[font-family:var(--font-mono)]";

/** The bundled keys' glyphs, in the draft's icon order. The registry's key
 *  set is closed; an unknown key answers no glyph (it never mounts). */
const KEY_ICONS: Readonly<Record<string, IconName>> = {
  "writing.continuation": "editNote",
  "chat.ask": "chat",
  "knowledge.extract-entities": "knowledge",
  "knowledge.check-consistency": "balance",
};

/** The editor's first face: the draft draws Text fortsetzen as the selected
 *  card, and the registry's registration order (the shell's import order)
 *  is an implementation fact, not a surface contract. The fallback keeps an
 *  honest face should the closed set ever change under it. */
const DEFAULT_KEY = "writing.continuation";

export function PromptsPage() {
  const t = useTranslation();
  usePageTitle(t("prompts.pageTitle"));

  const [novelId, setNovelId] = useState<string | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [tier, setTier] = useState<EditorScope["tier"]>("global");

  const novels = useNovelsQuery();
  const list = usePromptsList(novelId);
  const resetPending = useResetPending();

  // The Geltungsbereich's chosen novel by name, for the chips' labels.
  const novelTitle =
    novelId !== null ? (novels.data ?? []).find((novel) => novel.id === novelId)?.title ?? null : null;

  // The draft's drawn selection is the editor's first face; a selection the
  // list answers keeps standing (the keys never leave the registry).
  const listData = list.data;
  const currentKey =
    selectedKey ??
    (listData?.some((row) => row.key === DEFAULT_KEY) === true
      ? DEFAULT_KEY
      : listData?.[0]?.key ?? null);
  const current = listData?.find((row) => row.key === currentKey) ?? null;

  // The novel chip exists only where the key is scopable AND a novel is
  // filtered; the editor's tier falls back to global when it cannot stand.
  const novelChipStands = current !== null && current.novel_scopable && novelId !== null;
  const effectiveTier = novelChipStands ? tier : "global";
  const scope: EditorScope = {
    tier: effectiveTier,
    novelId: effectiveTier === "novel" ? novelId : null,
    novelTitle: effectiveTier === "novel" ? novelTitle : null,
    novelChip: novelChipStands,
    filteredNovelTitle: novelTitle,
  };

  const reset = useResetPrompt(currentKey, scope.novelId);
  const resetRevision = useResetRevision(currentKey, scope.novelId);
  const detailRead = usePromptDetail(currentKey, scope.novelId);

  function runReset(key: string, novelId: string | null): void {
    reset.mutate({ key, novelId });
  }

  const resetFailure =
    reset.isError && reset.variables?.key === currentKey && reset.variables.novelId === scope.novelId
      ? reset.error
      : null;

  const data = novels.data !== undefined && list.data !== undefined ? { novels: novels.data, list: list.data } : null;
  // The editor's detail read is the page's third read: a failed detail is
  // the outage face, never a right column whose loading card stands forever.
  const reads = [novels, list, detailRead];

  function retry(): void {
    for (const read of reads) {
      if (read.isError) void read.refetch();
    }
    // A read that never mounted its ask (an earlier throw left it idle)
    // re-asks through the cache invalidation — the family's own prefix.
    void queryClient.invalidateQueries({ queryKey: ["prompts"] });
  }

  function changeScope(next: string | null): void {
    if (resetPending) return;
    setNovelId(next);
    // A scope switch leaves the novel tier when no novel backs it; a novel
    // choice defaults the editor to that novel's own tier — the draft's
    // chip face with a book in the filter.
    setTier(next === null ? "global" : "novel");
  }

  const novelOverrides = novelId !== null ? (list.data ?? []).filter((row) => row.override_novel).length : 0;

  return (
    <main id="main-content" data-testid="prompts-page" aria-busy={data === null || resetPending} className="h-full overflow-y-auto">
      <div className="mx-auto max-w-6xl space-y-6 px-8 py-10 pb-24">
        <SettingsHub />

        {/* The header row: eyebrow, title, Geltungsbereich, the badge. */}
        <section className="flex flex-col gap-4 border-b border-border/60 pb-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="space-y-1">
            <div className="text-eyebrow uppercase tracking-wider text-muted">{t("prompts.catalog.title")}</div>
            <h1 className={`${SERIF} text-hero font-normal tracking-tight text-foreground`}>{t("prompts.title")}</h1>
            <p className="text-body text-muted">{t("prompts.catalog.sub")}</p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <label data-testid="scope-select" className="flex items-center gap-2 text-meta text-muted">
              <span>{t("prompts.scope.label")}</span>
              <select
                value={novelId ?? ""}
                onChange={(event) => changeScope(event.target.value === "" ? null : event.target.value)}
                disabled={resetPending}
                className={`rounded border border-border bg-panel px-2 py-1.5 text-meta font-semibold text-foreground shadow-sm disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS}`}
              >
                <option value="">{t("prompts.scope.global")}</option>
                {(novels.data ?? []).map((novel) => (
                  <option key={novel.id} value={novel.id}>
                    {novel.title}
                  </option>
                ))}
              </select>
            </label>

            {novelId !== null && novelOverrides > 0 && (
              <div
                data-testid="override-badge"
                className="flex items-center gap-1.5 rounded border border-warning/50 bg-panel px-2.5 py-1 text-meta font-medium text-foreground"
              >
                <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-warning" />
                <span>{t("prompts.scope.badge", { count: novelOverrides })}</span>
              </div>
            )}
          </div>
        </section>

        {reads.some((read) => read.isError) ? (
          <div className="flex justify-center p-6">
            <div role="alert" className="space-y-2 rounded-lg border border-danger/40 bg-panel p-5 text-center" data-testid="prompts-outage">
              <p className="text-body text-danger">{t("prompts.loadFailed")}</p>
              <button
                type="button"
                data-testid="prompts-retry"
                onClick={retry}
                className={`rounded border border-border bg-soft px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-soft/70 ${FOCUS}`}
              >
                {t("prompts.retry")}
              </button>
            </div>
          </div>
        ) : data === null || current === null ? (
          <div className="space-y-6" role="status">
            <p className="text-body text-muted">{t("prompts.loading")}</p>
            <div aria-hidden="true" className="space-y-3">
              <div className="h-10 w-72 animate-pulse rounded bg-soft" />
              <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
                <div className="h-64 animate-pulse rounded bg-soft lg:col-span-4" />
                <div className="h-96 animate-pulse rounded bg-soft lg:col-span-8" />
              </div>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 items-start gap-6 lg:grid-cols-12">
            {/* Left column: the catalog with its override marks. */}
            <div className="space-y-4 lg:col-span-4">
              <div className="rounded-lg border border-border bg-panel p-4 shadow-sm">
                <h2 className="text-label font-semibold text-foreground">{t("prompts.catalog.title")}</h2>
                <p className="mb-3 text-meta text-muted">{t("prompts.catalog.sub")}</p>
                <div className="space-y-2" data-testid="prompt-catalog">
                  {data.list.map((row) => {
                    const selected = row.key === currentKey;
                    return (
                      <button
                        key={row.key}
                        type="button"
                        data-testid="prompt-card"
                        data-key={row.key}
                        aria-pressed={selected}
                        onClick={() => {
                          if (resetPending) return;
                          setSelectedKey(row.key);
                          setTier(novelId !== null ? "novel" : "global");
                        }}
                        disabled={resetPending}
                        className={`w-full rounded border-2 p-3 text-start transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${FOCUS} ${
                          selected
                            ? "border-primary bg-surface"
                            : "border-border bg-panel hover:bg-surface"
                        }`}
                      >
                        <span className="flex items-start justify-between gap-2">
                          <span className="flex items-center gap-2 text-label font-semibold text-foreground">
                            <span className={selected ? "text-primary" : "text-muted"}>
                              <Icon name={KEY_ICONS[row.key] ?? "document"} size={16} />
                            </span>
                            <span>{t(`prompts.key.${row.key}` as Parameters<typeof t>[0])}</span>
                          </span>
                          <span className={selected ? "text-primary" : "text-muted"}>
                            <Icon name="arrowRight" size={14} />
                          </span>
                        </span>
                        <span className={`${MONO} mt-0.5 block text-[11px] text-muted`}>{row.key}</span>
                        <span className="mt-1 block text-xs leading-snug text-muted">{row.bundled_summary}</span>
                        <span className="mt-2.5 flex flex-wrap items-center gap-1.5" data-testid={`prompt-mark-${row.key}`}>
                          <Mark row={row} novelTitle={novelId !== null ? novelTitle : null} />
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* The Souveränitäts-Garantie, the DB-truthful copy (the
                  Stitch round's finding 6, decided correct-at-port). */}
              <div className="rounded-lg border border-border bg-panel p-4 shadow-sm">
                <div className="flex items-start gap-2.5">
                  <span className="mt-0.5 text-primary">
                    <Icon name="lock" size={18} />
                  </span>
                  <div>
                    <h3 className="text-xs font-semibold text-foreground">{t("prompts.sovereign.title")}</h3>
                    <p className="mt-1 text-xs leading-relaxed text-muted">{t("prompts.sovereign.body")}</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Right column: the editor for the selected key. */}
            <div className="lg:col-span-8">
              {detailRead.data !== undefined && currentKey !== null ? (
                <PromptEditor
                  key={`${currentKey}:${scope.tier}:${scope.novelId ?? "global"}:${resetRevision}`}
                  promptKey={currentKey}
                  detail={detailRead.data}
                  scope={scope}
                  onScopeChange={setTier}
                  resetPending={resetPending}
                  resetFailure={resetFailure}
                  onReset={runReset}
                />
              ) : (
                <div className="rounded-lg border border-border bg-panel p-5 shadow-sm" role="status">
                  <p className="text-meta text-muted">{t("prompts.loading")}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

/** The catalog mark: the override facts the list answers, spoken in the
 *  states reference's families. */
function Mark({ row, novelTitle }: { row: { novel_scopable: boolean; override_global: boolean; override_novel: boolean; key: string }; novelTitle: string | null }) {
  const t = useTranslation();
  if (!row.novel_scopable) {
    // The global-only key carries its scope fact beside the global mark —
    // the overrides draft's chat.ask card draws both.
    return (
      <>
        <MarkChip accent={row.override_global}>
          <span>{row.override_global ? t("prompts.catalog.globalOverride") : t("prompts.catalog.globalStandard")}</span>
        </MarkChip>
        <MarkChip muted>
          <span>{t("prompts.catalog.globalOnly")}</span>
        </MarkChip>
      </>
    );
  }
  if (novelTitle !== null) {
    return (
      <MarkChip accent={row.override_novel}>
        <span>
          {row.override_novel
            ? t("prompts.catalog.novelOverride", { novel: novelTitle })
            : t("prompts.catalog.inherits", { novel: novelTitle })}
        </span>
      </MarkChip>
    );
  }
  return (
    <MarkChip accent={row.override_global}>
      <span>{row.override_global ? t("prompts.catalog.globalOverride") : t("prompts.catalog.globalStandard")}</span>
    </MarkChip>
  );
}

function MarkChip({ accent, muted = false, children }: { accent?: boolean; muted?: boolean; children: ReactNode }) {
  // The muted chip's ground is the panel, never the soft wash: the muted
  // ink clears 4.5:1 on the panel, not on the soft step (the a11y floor).
  const face = accent
    ? "bg-primary font-semibold text-primary-foreground"
    : muted
      ? "bg-panel text-muted"
      : "border border-border bg-panel text-muted";
  return (
    <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${face}`}>
      {children}
    </span>
  );
}
