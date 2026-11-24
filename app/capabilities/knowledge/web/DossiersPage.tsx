/**
 * The dossiers page (W5 Task 5) — the capability's browsing surface, ported
 * from the owner-approved harmonized `dossiers-2` draft onto the shell's
 * tokens. The novel's real cast as a searchable, type-filtered grid:
 *
 * - The list column carries one card per EntityRead row: the type glyph, the
 *   name, the type badge, the description excerpt and the honest relation
 *   count (both directions, a self-loop once). The draft's invented „Aktiv"
 *   status is NOT rendered — no model carries a status; the shared dossier's
 *   neutral gap row is its honest home.
 * - The subbar's tabs are the extraction contract's REAL eight types (the
 *   draft drew four) plus All, each with its real count — a type the canon
 *   does not carry stands at zero, honest, not hidden. The search reads name
 *   AND body, case-insensitive, and composes with the type filter (AND).
 * - A card opens the shared EntityDossier (Task 3's component, one component
 *   two homes) in the detail column; the selection rides the URL's `entity`
 *   search param, so deep links and the back button work. The page injects
 *   the draft's two profile gap areas (psychological, linguistic — the
 *   Want/Need/Lie geometry and the dialogue patterns) through the dossier's
 *   children slot: honest disabled areas with their gap note, never fake
 *   content.
 * - The overview rail names the selection's REAL model fields (name, type,
 *   relation count). The draft's disabled graph area is a LIVE door here:
 *   the lore graph went live this wave (Task 3), so „comes later" would be a
 *   false gap — the door opens the graph with this entity selected. The
 *   manuscript-evidence gap is not doubled: the shared dossier already
 *   carries it once (excerpts). AI sparring stays an honest disabled area.
 * - The new-dossier door (W9) opens the hand-made create; a saved row is
 *   selected at once, so its dossier opens without a second click.
 * - The subbar's sibling door connects the graph (and the graph's subbar
 *   answers back) — the honest minimal navigation between the two surfaces,
 *   carrying the selection across.
 *
 * The page reads the real API through the shell's query seam and imports no
 * other capability (rule 1). Loading, outage and the empty canon each answer
 * with their own honest face — and each answer stands BELOW the subbar,
 * which never leaves: one consistent mechanism with the graph and the
 * sources archive, the sibling doors stay reachable in every state.
 */
import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback, useMemo, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useEntitiesQuery, useNovelRelationsQuery } from "@shell/lib/query";
import { CARD_EYEBROW, FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { EntityDossier } from "./EntityDossier";
import { EntityCreateDialog } from "./crudDialogs";
import { TYPE_KEYS, entityTypeIcon, entityTypeLabel, typeTheme } from "./entityTypes";

const DOSSIERS_PATH = "/novels/$novelId/knowledge/dossiers";
const GRAPH_PATH = "/novels/$novelId/knowledge/graph";
const SOURCES_PATH = "/novels/$novelId/knowledge/sources";

/** The draft's tab geometry on the shell's tokens: the active tab lifts onto
 *  the card surface with the brand ink; the rest wait in the muted register. */
function tabClass(active: boolean): string {
  return `flex items-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-meta transition-colors ${FOCUS} ${
    active ? "bg-card font-semibold text-primary shadow-card" : "text-muted hover:bg-surface-container hover:text-foreground"
  }`;
}

export function DossiersPage() {
  const t = useTranslation();
  const { novelId } = useParams({ from: DOSSIERS_PATH });
  const { entity: selectedId } = useSearch({ from: DOSSIERS_PATH });
  const navigate = useNavigate();
  usePageTitle(t("knowledge.dossiers.title"));

  const entities = useEntitiesQuery(novelId);
  const relations = useNovelRelationsQuery(novelId);

  const [activeType, setActiveType] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [creating, setCreating] = useState(false);

  const entityList = useMemo(() => entities.data ?? [], [entities.data]);
  const relationList = useMemo(() => relations.data ?? [], [relations.data]);

  // The honest relation count per entity — both directions, a self-loop
  // once (the same edges the dossier's relation list shows).
  const relationCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const relation of relationList) {
      counts.set(relation.from_entity_id, (counts.get(relation.from_entity_id) ?? 0) + 1);
      if (relation.to_entity_id !== relation.from_entity_id) {
        counts.set(relation.to_entity_id, (counts.get(relation.to_entity_id) ?? 0) + 1);
      }
    }
    return counts;
  }, [relationList]);

  // --- The client-side filter: type AND (name OR body) --------------------
  const needle = query.trim().toLowerCase();
  const visible = useMemo(
    () =>
      entityList.filter(
        (entity) =>
          (activeType === null || entity.type === activeType) &&
          (needle === "" ||
            entity.name.toLowerCase().includes(needle) ||
            entity.content.toLowerCase().includes(needle)),
      ),
    [entityList, activeType, needle],
  );

  // The tabs' real counts — the contract's eight types, in contract order.
  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const entity of entityList) counts.set(entity.type, (counts.get(entity.type) ?? 0) + 1);
    return counts;
  }, [entityList]);

  // --- Selection rides the URL (the graph's convention) --------------------
  const select = useCallback(
    (id: string | null) => {
      void navigate({
        to: DOSSIERS_PATH,
        params: { novelId },
        search: id !== null ? { entity: id } : {},
        replace: true,
      });
    },
    [navigate, novelId],
  );

  const selected = selectedId !== undefined ? (entityList.find((entity) => entity.id === selectedId) ?? null) : null;

  // The sibling door and the rail's graph area share one crossing: only a
  // LIVING selection travels — a dead id on the URL resolves to no entity
  // and is never handed to the graph (the review's stale-param finding).
  const goGraph = useCallback(() => {
    void navigate({
      to: GRAPH_PATH,
      params: { novelId },
      search: selected !== null ? { entity: selected.id } : {},
    });
  }, [navigate, novelId, selected]);

  const selectedRelations = useMemo(
    () =>
      selected === null
        ? []
        : relationList.filter(
            (relation) => relation.from_entity_id === selected.id || relation.to_entity_id === selected.id,
          ),
    [relationList, selected],
  );

  // --- The honest states --------------------------------------------------
  const pending = entities.isPending || relations.isPending;
  const failed = entities.isError || relations.isError;
  function retry() {
    void entities.refetch();
    void relations.refetch();
  }

  const selectedTheme = selected !== null ? typeTheme(selected.type) : null;

  return (
    <div id="dossiers-page" data-testid="dossiers-page" tabIndex={-1} className="flex h-full flex-col overflow-hidden focus:outline-none">
      {/* The subbar — the view label, the sibling door to the graph, the
          contract's type tabs and the draft's new-dossier door (live since
          W9: it opens the hand-made create). One consistent mechanism with
          the graph and the sources archive: the bar stands in EVERY state —
          pending, failed, empty, populated — so the sibling doors never
          vanish behind an honest face; only the body below it varies. */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-container-low px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta font-semibold text-foreground shadow-card">
            <span className="text-primary">
              <Icon name="viewList" size={15} />
            </span>
            {t("knowledge.dossiers.title")}
          </span>
          <button
            type="button"
            data-testid="dossiers-graph-door"
            onClick={goGraph}
            className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
          >
            <Icon name="hub" size={14} /> {t("knowledge.graph.title")}
          </button>
          {/* The third sibling door (W5 Task 6): the sources archive keeps
              the library's documents — no entity selection travels there. */}
          <button
            type="button"
            data-testid="dossiers-sources-door"
            onClick={() => {
              void navigate({ to: SOURCES_PATH, params: { novelId }, search: {} });
            }}
            className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
          >
            <Icon name="autoStories" size={14} /> {t("knowledge.sources.title")}
          </button>
          <span aria-hidden="true" className="mx-1 h-4 w-px bg-rule" />
          <div role="group" aria-label={t("knowledge.graph.allTypes")} className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              data-testid="dossier-type-tab"
              aria-pressed={activeType === null}
              onClick={() => setActiveType(null)}
              className={tabClass(activeType === null)}
            >
              <Icon name="gridView" size={14} />
              {t("knowledge.graph.allTypes")}
              <span className={`rounded-full px-1.5 text-[11px] ${activeType === null ? "bg-primary/10" : "bg-surface-container-high"}`}>
                {entityList.length}
              </span>
            </button>
            {Object.keys(TYPE_KEYS).map((type) => {
              const theme = typeTheme(type);
              const active = activeType === type;
              const count = typeCounts.get(type) ?? 0;
              return (
                <button
                  key={type}
                  type="button"
                  data-testid="dossier-type-tab"
                  aria-pressed={active}
                  onClick={() => setActiveType(active ? null : type)}
                  className={tabClass(active)}
                >
                  <span style={{ color: theme.var }}>
                    <Icon name={entityTypeIcon(type)} size={14} />
                  </span>
                  {entityTypeLabel(t, type)}
                  <span className={`rounded-full px-1.5 text-[11px] ${active ? "bg-primary/10" : "bg-surface-container-high"}`}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
        <button
          type="button"
          id="dossiers-new-dossier"
          data-testid="dossiers-new-dossier"
          onClick={() => setCreating(true)}
          className={`flex items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-3 py-1 text-meta text-primary-foreground transition-colors hover:opacity-95 ${FOCUS}`}
        >
          <Icon name="plus" size={14} /> {t("knowledge.dossiers.newDossier")}
        </button>
      </div>

      {/* The body — the honest state's own face; the bar above stays. */}
      {pending ? (
        <div data-testid="dossiers-loading" className="flex min-h-0 flex-1 items-center justify-center">
          <p role="status" className="text-body text-muted">
            {t("knowledge.graph.loading")}
          </p>
        </div>
      ) : failed ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div role="alert" className="space-y-2 rounded-[var(--radius-surface)] border border-danger/40 bg-panel p-5 text-center">
            <p className="text-body text-danger">{t("knowledge.dossiers.loadFailed")}</p>
            <button
              type="button"
              onClick={retry}
              className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
            >
              {t("knowledge.graph.retry")}
            </button>
          </div>
        </div>
      ) : entityList.length === 0 ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div data-testid="dossiers-empty" className="max-w-sm space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-8 text-center">
            <span className="inline-block text-muted">
              <Icon name="viewList" size={28} />
            </span>
            <p className="text-body font-semibold text-foreground">{t("knowledge.graph.empty")}</p>
            <p className="text-meta text-muted">{t("knowledge.graph.emptyNote")}</p>
          </div>
        </div>
      ) : (
        /* The draft's three columns: the list, the dossier detail, the model
           overview. Below lg they stack and the whole body scrolls. */
        <div className="grid min-h-0 flex-1 grid-cols-1 overflow-y-auto lg:grid-cols-12 lg:overflow-hidden">
          {/* The list — the search over name and body, the hint, the cards. */}
          <aside className="flex flex-col gap-3 bg-surface-container-low/40 p-4 lg:col-span-3 lg:min-h-0 lg:overflow-y-auto">
            <div className="flex flex-col gap-2">
              <label className="relative block">
                <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-muted">
                  <Icon name="search" size={14} />
                </span>
                <span className="sr-only">{t("knowledge.dossiers.searchLabel")}</span>
                <input
                  data-testid="dossier-search"
                  type="search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t("knowledge.dossiers.search")}
                  className={`w-full rounded-[var(--radius-control)] border border-rule bg-card py-1.5 pl-8 pr-3 text-body text-foreground shadow-card placeholder:text-muted focus:outline-none ${FOCUS}`}
                />
              </label>
              <p className="px-0.5 text-meta text-muted">{t("knowledge.dossiers.listHint")}</p>
            </div>
            {visible.length === 0 ? (
              <div data-testid="dossiers-no-results" className="space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-4 text-center">
                <p className="text-meta text-muted">{t("knowledge.graph.noResults")}</p>
                <button
                  type="button"
                  onClick={() => {
                    setActiveType(null);
                    setQuery("");
                  }}
                  className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
                >
                  {t("knowledge.graph.clearFilters")}
                </button>
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {visible.map((entity) => {
                  const theme = typeTheme(entity.type);
                  const isSelected = selected?.id === entity.id;
                  const excerpt = entity.content.trim();
                  const count = relationCounts.get(entity.id) ?? 0;
                  return (
                    <button
                      key={entity.id}
                      type="button"
                      data-testid="dossier-card"
                      aria-pressed={isSelected}
                      onClick={() => select(entity.id)}
                      className={`relative overflow-hidden rounded-[var(--radius-surface)] p-3 text-left transition-all ${FOCUS} ${
                        isSelected ? "bg-card shadow-overlay" : "bg-card/70 shadow-card hover:bg-card"
                      }`}
                    >
                      {/* The draft's selected accent bar — the brand ink. */}
                      {isSelected && <span aria-hidden="true" className="absolute bottom-0 left-0 top-0 w-1 bg-primary" />}
                      <span className={`flex items-center gap-2 ${isSelected ? "pl-1" : ""}`}>
                        <span
                          className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-[var(--radius-control)] ${theme.tint}`}
                          style={{ color: theme.var }}
                        >
                          <Icon name={entityTypeIcon(entity.type)} size={13} />
                        </span>
                        <span className="min-w-0 flex-1 truncate text-label font-semibold text-foreground">{entity.name}</span>
                        <span className={`shrink-0 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-foreground ${theme.tint}`}>
                          {entityTypeLabel(t, entity.type)}
                        </span>
                      </span>
                      {excerpt !== "" && (
                        <span className={`mt-1 line-clamp-2 text-meta leading-tight text-muted ${isSelected ? "pl-1" : ""}`}>
                          {excerpt}
                        </span>
                      )}
                      {/* The honest count — never the draft's invented status. */}
                      <span className={`mt-2 block border-t border-rule pt-2 text-meta text-muted ${isSelected ? "pl-1" : ""}`}>
                        {t("knowledge.dossiers.relationCount", { count })}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </aside>

          {/* The detail — the shared dossier, one component two homes. The
              page's own profile gap areas ride its children slot. */}
          <section className="lg:col-span-6 lg:min-h-0 lg:overflow-y-auto">
            {selected !== null ? (
              <EntityDossier
                entity={selected}
                relations={selectedRelations}
                entities={entityList}
                onClose={() => select(null)}
                onSelectEntity={(id) => select(id)}
                focusFallbackId="dossiers-page"
              >
                <div data-testid="dossier-psych-gap" aria-disabled="true" className="flex flex-col gap-2">
                  <h3 className={`${CARD_EYEBROW} flex items-center gap-1.5`}>
                    <Icon name="person" size={13} /> {t("knowledge.dossiers.psychProfile")}
                  </h3>
                  <div className="rounded-[var(--radius-control)] border border-dashed border-border bg-surface-container-low/50 p-3 opacity-70">
                    <p className="text-meta italic text-muted">{t("knowledge.dossiers.laterWaveNote")}</p>
                  </div>
                </div>
                <div data-testid="dossier-linguistic-gap" aria-disabled="true" className="flex flex-col gap-2">
                  <h3 className={`${CARD_EYEBROW} flex items-center gap-1.5`}>
                    <Icon name="chat" size={13} /> {t("knowledge.dossiers.linguisticProfile")}
                  </h3>
                  <div className="rounded-[var(--radius-control)] border border-dashed border-border bg-surface-container-low/50 p-3 opacity-70">
                    <p className="text-meta italic text-muted">{t("knowledge.dossiers.laterWaveNote")}</p>
                  </div>
                </div>
              </EntityDossier>
            ) : (
              <div data-testid="dossiers-no-selection" className="flex h-full items-center justify-center p-6 lg:border-l lg:border-border">
                <div className="max-w-sm space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-8 text-center">
                  <span className="inline-block text-muted">
                    <Icon name="viewList" size={28} />
                  </span>
                  <p className="text-body text-muted">{t("knowledge.dossiers.noSelection")}</p>
                </div>
              </div>
            )}
          </section>

          {/* The overview rail — the selection's real model fields, the live
              graph door and the AI-sparring gap. With no selection there is
              nothing to summarize, so the rail stands empty. */}
          <aside className="bg-surface-container-low/30 p-4 lg:col-span-3 lg:min-h-0 lg:overflow-y-auto lg:border-l lg:border-border">
            {selected !== null && selectedTheme !== null && (
              <div className="flex flex-col gap-4">
                <div data-testid="dossier-overview" className="flex flex-col gap-2 rounded-[var(--radius-surface)] border border-rule bg-card p-3.5 shadow-card">
                  <div className="flex items-center justify-between gap-2">
                    <h4 className="text-label font-semibold text-foreground">{t("knowledge.dossiers.overview")}</h4>
                    <span className="shrink-0 rounded bg-secondary/15 px-1.5 py-0.5 text-[10px] font-semibold text-foreground">
                      {t("knowledge.dossiers.overviewBadge")}
                    </span>
                  </div>
                  <div className="flex flex-col text-meta">
                    <div className="flex items-center justify-between gap-2 border-b border-rule py-1">
                      <span className="shrink-0 text-muted">{t("knowledge.crud.nameLabel")}</span>
                      <span className="truncate font-semibold text-foreground">{selected.name}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2 border-b border-rule py-1">
                      <span className="shrink-0 text-muted">{t("knowledge.crud.typeLabel")}</span>
                      <span className="font-semibold text-primary">{entityTypeLabel(t, selected.type)}</span>
                    </div>
                    <div className="flex items-center justify-between gap-2 py-1">
                      <span className="shrink-0 text-muted">{t("knowledge.dossiers.overviewRelations")}</span>
                      <span className="font-semibold text-foreground">
                        {t("knowledge.dossiers.overviewLinked", { count: selectedRelations.length })}
                      </span>
                    </div>
                  </div>
                </div>

                {/* The draft drew this area disabled; the graph went live this
                    wave, so the honest port is a door to the real thing. */}
                <div className="flex flex-col gap-2 rounded-[var(--radius-surface)] border border-rule bg-card p-3.5 shadow-card">
                  <h4 className={`${CARD_EYEBROW} flex items-center gap-1.5`}>
                    <Icon name="hub" size={13} /> {t("knowledge.dossiers.graphArea")}
                  </h4>
                  <button
                    type="button"
                    data-testid="dossier-open-graph"
                    onClick={goGraph}
                    className={`flex items-center justify-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container-high px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
                  >
                    <Icon name="openInNew" size={13} /> {t("knowledge.dossiers.openGraph")}
                  </button>
                </div>

                <div data-testid="dossier-ai-gap" aria-disabled="true" className="flex flex-col gap-2 rounded-[var(--radius-surface)] border border-border bg-surface-container-low/30 p-3.5 opacity-75">
                  <h4 className={`${CARD_EYEBROW} flex items-center gap-1.5`}>
                    <Icon name="spark" size={13} /> {t("knowledge.dossiers.aiSparring")}
                  </h4>
                  <div className="rounded-[var(--radius-control)] border border-dashed border-border bg-card p-3">
                    <p className="text-center text-meta italic text-muted">{t("knowledge.dossiers.laterWaveNote")}</p>
                  </div>
                </div>
              </div>
            )}
          </aside>
        </div>
      )}

      {creating && (
        <EntityCreateDialog
          novelId={novelId}
          entities={entityList}
          openerId="dossiers-new-dossier"
          onClose={() => setCreating(false)}
          onCreated={(entity) => select(entity.id)}
        />
      )}
    </div>
  );
}
