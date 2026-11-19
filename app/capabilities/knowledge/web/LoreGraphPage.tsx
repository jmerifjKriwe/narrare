/**
 * The lore graph page (W5 Task 3) — the capability's first own addressable
 * surface, ported from the owner-approved harmonized `lore-graph-2` draft
 * onto the shell's tokens. The novel's real canon drawn as a living web:
 *
 * - Nodes are EntityRead rows (name, type, the body's first line), edges are
 *   RelationRead rows (the type's wording on the line, the note in the
 *   popover). The layout is the pure deterministic pass (graphLayout.ts):
 *   the same entities and relations always draw the same picture.
 * - Zoom (wheel + the HUD buttons) and pan (drag the canvas), with an honest
 *   reset that returns to the fit framing — a pure function of the bounds.
 * - A node click opens the entity's dossier (the shared EntityDossier); the
 *   selection rides the URL's `entity` search param, so the dock chip's deep
 *   link and the back button both work. An edge click opens its note popover.
 * - Type filter chips and a name search narrow the canvas client-side over
 *   the loaded web; the layout stays put (filtering hides, never re-seats).
 * - The draft's CRUD doors (W5 Task 4): draw relation and merge open the
 *   shared dialogs (`crudDialogs.tsx`); the new-entity door has no endpoint
 *   at all (entities are born through review) and stands an honest disabled
 *   gap with its note.
 *
 * The page reads the real API through the shell's query seam and imports no
 * other capability (rule 1). Loading, outage and the empty canon each answer
 * with their own honest face.
 */
import { useParams, useNavigate, useSearch } from "@tanstack/react-router";
import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";

import type { Relation } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useEntitiesQuery, useNovelRelationsQuery } from "@shell/lib/query";
import { CARD_EYEBROW, FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { EntityDossier } from "./EntityDossier";
import { CreateRelationDialog, MergeDialog } from "./crudDialogs";
import { entityTypeIcon, entityTypeLabel, typeTheme } from "./entityTypes";
import { fitTransform, graphBounds, graphSignature, layoutGraph, type Transform } from "./graphLayout";
import { relationTypeLabel } from "./relations";

const GRAPH_PATH = "/novels/$novelId/knowledge/graph";
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 4;
const FIT_PADDING = 72;
/** How far the arrow tip stands off the target's centre, near its card edge. */
const ARROW_OFFSET = 78;

function clamp(value: number, lo: number, hi: number): number {
  return Math.min(hi, Math.max(lo, value));
}

/** The first line of the body, the node card's snippet — never an invented
 *  subtitle; an empty body simply shows none. */
function snippet(content: string): string {
  const line = content.trim().split("\n")[0] ?? "";
  return line;
}

export function LoreGraphPage() {
  const t = useTranslation();
  const { novelId } = useParams({ from: GRAPH_PATH });
  const { entity: selectedId } = useSearch({ from: GRAPH_PATH });
  const navigate = useNavigate();
  usePageTitle(t("knowledge.graph.title"));

  const entities = useEntitiesQuery(novelId);
  const relations = useNovelRelationsQuery(novelId);

  const [activeType, setActiveType] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [edgeId, setEdgeId] = useState<string | null>(null);
  // Which subbar CRUD dialog stands open (Task 4); the dossier owns its own.
  const [crud, setCrud] = useState<null | "addRelation" | "merge">(null);

  const entityList = useMemo(() => entities.data ?? [], [entities.data]);
  const relationList = useMemo(() => relations.data ?? [], [relations.data]);

  // The one deterministic layout of the whole web; filtering hides nodes and
  // edges without re-seating the rest, so the picture stays put.
  const layout = useMemo(() => layoutGraph(entityList, relationList), [entityList, relationList]);
  const bounds = useMemo(() => graphBounds(layout.values()), [layout]);
  // The set's stable key: a background refetch of the same rows answers the
  // same key, so the viewport keeps the user's zoom; only a materially
  // different web (a node or edge added or gone) reframes.
  const signature = useMemo(() => graphSignature(entityList, relationList), [entityList, relationList]);

  // --- The viewport -------------------------------------------------------
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (el === null) return;
    const measure = () => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) setSize({ width: rect.width, height: rect.height });
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const fit = useMemo(
    () => fitTransform(bounds, size.width, size.height, FIT_PADDING),
    [bounds, size.width, size.height],
  );
  const fitRef = useRef(fit);
  fitRef.current = fit;
  const sizeRef = useRef(size);
  sizeRef.current = size;
  const boundsRef = useRef(bounds);
  boundsRef.current = bounds;
  const [view, setView] = useState<Transform | null>(null);
  // Reframe only when the SET materially changes (the signature), not on every
  // layout identity change — an identical-rows refetch keeps the user's view.
  // The bounds and size are read live through refs, not re-run keys.
  // biome-ignore lint/correctness/useExhaustiveDependencies: signature is the deliberate re-run trigger (the set's stable key); bounds and size are read live through refs, not triggers.
  useEffect(() => {
    const { width, height } = sizeRef.current;
    setView(fitTransform(boundsRef.current, width, height, FIT_PADDING));
  }, [signature]);
  const effective = view ?? fit;

  const zoomAt = useCallback((px: number, py: number, factor: number) => {
    setView((previous) => {
      const base = previous ?? fitRef.current;
      const k = clamp(base.k * factor, MIN_ZOOM, MAX_ZOOM);
      const ratio = k / base.k;
      return { k, x: px - (px - base.x) * ratio, y: py - (py - base.y) * ratio };
    });
  }, []);

  // The wheel zooms about the cursor; a native non-passive listener so the
  // page does not scroll under the graph.
  useEffect(() => {
    const el = containerRef.current;
    if (el === null) return;
    function onWheel(event: WheelEvent) {
      event.preventDefault();
      const rect = el!.getBoundingClientRect();
      const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
      zoomAt(event.clientX - rect.left, event.clientY - rect.top, factor);
    }
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [zoomAt]);

  const dragRef = useRef<{ x: number; y: number } | null>(null);
  function onPointerDown(event: ReactPointerEvent<HTMLDivElement>) {
    // A press on a node or an edge is its own click, never a pan.
    if ((event.target as HTMLElement).closest("[data-node],[data-edge]")) return;
    dragRef.current = { x: event.clientX, y: event.clientY };
    try {
      event.currentTarget.setPointerCapture(event.pointerId);
    } catch {
      // jsdom has no pointer capture; the drag still tracks the move.
    }
  }
  function onPointerMove(event: ReactPointerEvent<HTMLDivElement>) {
    if (dragRef.current === null) return;
    const dx = event.clientX - dragRef.current.x;
    const dy = event.clientY - dragRef.current.y;
    dragRef.current = { x: event.clientX, y: event.clientY };
    setView((previous) => {
      const base = previous ?? fitRef.current;
      return { ...base, x: base.x + dx, y: base.y + dy };
    });
  }
  function onPointerUp(event: ReactPointerEvent<HTMLDivElement>) {
    dragRef.current = null;
    try {
      event.currentTarget.releasePointerCapture(event.pointerId);
    } catch {
      // jsdom has no pointer capture.
    }
  }

  // --- Selection rides the URL -------------------------------------------
  const select = useCallback(
    (id: string | null) => {
      void navigate({
        to: GRAPH_PATH,
        params: { novelId },
        search: id !== null ? { entity: id } : {},
        replace: true,
      });
    },
    [navigate, novelId],
  );

  // --- The edge popover's focus contract ---------------------------------
  // Each edge is a keyboard button; the refs let Escape (and the close door)
  // hand focus back to the edge that opened the popover.
  const edgeRefs = useRef(new Map<string, SVGGElement>());
  function openEdge(id: string) {
    setEdgeId(id);
  }
  function closeEdge(returnFocus: boolean) {
    if (returnFocus && edgeId !== null) edgeRefs.current.get(edgeId)?.focus();
    setEdgeId(null);
  }
  // Escape closes the popover and returns focus to its opener — the dialog's
  // own dismissal contract, keyboard-first.
  useEffect(() => {
    if (edgeId === null) return;
    const opener = edgeId;
    function onKey(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      event.preventDefault();
      edgeRefs.current.get(opener)?.focus();
      setEdgeId(null);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [edgeId]);

  // --- The client-side filter --------------------------------------------
  const needle = query.trim().toLowerCase();
  const visibleEntities = useMemo(
    () =>
      entityList.filter(
        (entity) =>
          (activeType === null || entity.type === activeType) &&
          (needle === "" || entity.name.toLowerCase().includes(needle)),
      ),
    [entityList, activeType, needle],
  );
  const visibleIds = useMemo(() => new Set(visibleEntities.map((entity) => entity.id)), [visibleEntities]);
  const visibleRelations = useMemo(
    () =>
      relationList.filter(
        (relation) => visibleIds.has(relation.from_entity_id) && visibleIds.has(relation.to_entity_id),
      ),
    [relationList, visibleIds],
  );

  // The type chips: every type the canon carries, with its real count.
  const typeCounts = useMemo(() => {
    const counts = new Map<string, number>();
    for (const entity of entityList) counts.set(entity.type, (counts.get(entity.type) ?? 0) + 1);
    return [...counts.entries()].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0));
  }, [entityList]);

  const selected = selectedId !== undefined ? (entityList.find((entity) => entity.id === selectedId) ?? null) : null;
  const selectedRelations = useMemo(
    () =>
      selected === null
        ? []
        : relationList.filter(
            (relation) => relation.from_entity_id === selected.id || relation.to_entity_id === selected.id,
          ),
    [relationList, selected],
  );
  const nameById = useMemo(() => new Map(entityList.map((entity) => [entity.id, entity])), [entityList]);
  const edge = edgeId !== null ? (relationList.find((relation) => relation.id === edgeId) ?? null) : null;

  // --- The honest states --------------------------------------------------
  const pending = entities.isPending || relations.isPending;
  const failed = entities.isError || relations.isError;
  function retry() {
    void entities.refetch();
    void relations.refetch();
  }

  if (pending) {
    return (
      <div data-testid="graph-loading" className="flex h-full items-center justify-center">
        <p role="status" className="text-body text-muted">
          {t("knowledge.graph.loading")}
        </p>
      </div>
    );
  }
  if (failed) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div role="alert" className="space-y-2 rounded-[var(--radius-surface)] border border-danger/40 bg-panel p-5 text-center">
          <p className="text-body text-danger">{t("knowledge.graph.loadFailed")}</p>
          <button
            type="button"
            onClick={retry}
            className={`rounded border border-border bg-surface-container-low px-3 py-1.5 text-meta font-medium text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
          >
            {t("knowledge.graph.retry")}
          </button>
        </div>
      </div>
    );
  }
  if (entityList.length === 0) {
    return (
      <div className="flex h-full items-center justify-center p-6">
        <div data-testid="graph-empty" className="max-w-sm space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-8 text-center">
          <span className="inline-block text-muted">
            <Icon name="hub" size={28} />
          </span>
          <p className="text-body font-semibold text-foreground">{t("knowledge.graph.empty")}</p>
          <p className="text-meta text-muted">{t("knowledge.graph.emptyNote")}</p>
        </div>
      </div>
    );
  }

  // --- The graph ----------------------------------------------------------
  const worldStyle = {
    transform: `translate(${effective.x}px, ${effective.y}px) scale(${effective.k})`,
    transformOrigin: "0 0",
  };

  function edgeGeometry(relation: Relation) {
    const from = layout.get(relation.from_entity_id);
    const to = layout.get(relation.to_entity_id);
    if (from === undefined || to === undefined) return null;
    if (relation.from_entity_id === relation.to_entity_id) {
      // A self-loop arcs off the node's right side and back.
      const d = `M ${from.x + 34} ${from.y - 26} C ${from.x + 130} ${from.y - 80}, ${from.x + 130} ${from.y + 80}, ${from.x + 34} ${from.y + 26}`;
      return { d, midX: from.x + 96, midY: from.y, tipX: from.x + 34, tipY: from.y + 26, ux: -1, uy: 0 };
    }
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const distance = Math.hypot(dx, dy) || 1;
    const ux = dx / distance;
    const uy = dy / distance;
    const tipX = to.x - ux * ARROW_OFFSET;
    const tipY = to.y - uy * ARROW_OFFSET;
    return {
      d: `M ${from.x} ${from.y} L ${tipX} ${tipY}`,
      midX: (from.x + to.x) / 2,
      midY: (from.y + to.y) / 2,
      tipX,
      tipY,
      ux,
      uy,
    };
  }

  const popoverAnchor =
    edge !== null
      ? (() => {
          const geometry = edgeGeometry(edge);
          if (geometry === null) return null;
          return { x: geometry.midX * effective.k + effective.x, y: geometry.midY * effective.k + effective.y };
        })()
      : null;

  return (
    <div data-testid="graph-page" className="flex h-full flex-col overflow-hidden">
      {/* The subbar — the view label, the type filter chips, the search and
          the draft's CRUD doors (Task 4: relation/merge live, new-entity gap). */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-container-low px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta font-semibold text-foreground shadow-card">
            <span className="text-primary">
              <Icon name="hub" size={15} />
            </span>
            {t("knowledge.graph.title")}
          </span>
          <span aria-hidden="true" className="mx-1 h-4 w-px bg-rule" />
          <div role="group" aria-label={t("knowledge.graph.allTypes")} className="flex flex-wrap items-center gap-1.5">
            <button
              type="button"
              data-testid="type-chip"
              aria-pressed={activeType === null}
              onClick={() => setActiveType(null)}
              className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-meta transition-colors ${FOCUS} ${
                activeType === null
                  ? "bg-primary text-primary-foreground"
                  : "bg-surface-container text-foreground hover:bg-surface-container-high"
              }`}
            >
              {t("knowledge.graph.allTypes")}
              <span className={`rounded-full px-1.5 text-[11px] ${activeType === null ? "bg-surface/20" : "bg-surface-container-high"}`}>
                {entityList.length}
              </span>
            </button>
            {typeCounts.map(([type, count]) => {
              const theme = typeTheme(type);
              const active = activeType === type;
              return (
                <button
                  key={type}
                  type="button"
                  data-testid="type-chip"
                  aria-pressed={active}
                  onClick={() => setActiveType(active ? null : type)}
                  className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-meta transition-colors ${FOCUS} ${
                    active ? `${theme.tint} text-foreground ring-1 ring-border` : "bg-surface-container text-foreground hover:bg-surface-container-high"
                  }`}
                >
                  <span aria-hidden="true" className={`h-2 w-2 rounded-full ${theme.dot}`} />
                  {entityTypeLabel(t, type)} ({count})
                </button>
              );
            })}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="flex items-center gap-1.5 rounded-[var(--radius-control)] border border-rule bg-card px-2.5 py-1 text-meta">
            <span className="text-muted">
              <Icon name="search" size={14} />
            </span>
            <span className="sr-only">{t("knowledge.graph.searchLabel")}</span>
            <input
              data-testid="graph-search"
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("knowledge.graph.search")}
              aria-label={t("knowledge.graph.searchLabel")}
              className="w-40 bg-transparent text-foreground placeholder:text-muted focus:outline-none"
            />
          </label>
          <button
            type="button"
            id="graph-merge"
            disabled={entityList.length < 2}
            onClick={() => setCrud("merge")}
            title={
              entityList.length < 2
                ? `${t("knowledge.graph.merge")} (${t("knowledge.crud.mergeNeedsTwo")})`
                : t("knowledge.graph.merge")
            }
            className={`flex items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container-high px-3 py-1 text-meta text-foreground transition-colors ${FOCUS} ${
              entityList.length < 2 ? "cursor-not-allowed opacity-60" : "hover:bg-surface-container"
            }`}
          >
            <Icon name="copy" size={14} /> {t("knowledge.graph.merge")}
          </button>
          <button
            type="button"
            id="graph-add-edge"
            onClick={() => setCrud("addRelation")}
            className={`flex items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container-high px-3 py-1 text-meta text-foreground transition-colors hover:bg-surface-container ${FOCUS}`}
          >
            <Icon name="hub" size={14} /> {t("knowledge.graph.addEdge")}
          </button>
          <button
            type="button"
            disabled
            title={`${t("knowledge.graph.newEntity")} (${t("knowledge.graph.newEntityNote")})`}
            className="flex cursor-not-allowed items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-3 py-1 text-meta text-primary-foreground opacity-60"
          >
            <Icon name="plus" size={14} /> {t("knowledge.graph.newEntity")}
          </button>
        </div>
      </div>

      {/* The canvas + the dossier dock. */}
      <div className="relative flex min-h-0 flex-1">
        <div
          ref={containerRef}
          data-testid="graph-canvas"
          className="relative min-w-0 flex-1 cursor-grab overflow-hidden bg-surface-container-lowest active:cursor-grabbing"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerLeave={onPointerUp}
        >
          {/* The dot grid — the draft's canvas texture, fixed under the web. */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0 opacity-40"
            style={{ backgroundImage: "radial-gradient(var(--outline) 1px, transparent 1px)", backgroundSize: "24px 24px" }}
          />

          {visibleEntities.length === 0 ? (
            <div className="absolute inset-0 flex items-center justify-center">
              <div data-testid="graph-no-results" className="space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-6 text-center">
                <p className="text-body text-muted">{t("knowledge.graph.noResults")}</p>
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
            </div>
          ) : (
            <div data-testid="graph-world" className="absolute left-0 top-0" style={worldStyle}>
              <svg
                className="absolute left-0 top-0 overflow-visible"
                width={1}
                height={1}
                role="group"
                aria-label={t("knowledge.graph.relationCount", { count: visibleRelations.length })}
              >
                {visibleRelations.map((relation) => {
                  const geometry = edgeGeometry(relation);
                  if (geometry === null) return null;
                  const fromType = nameById.get(relation.from_entity_id)?.type ?? "generic";
                  const ink = typeTheme(fromType).var;
                  const label = relationTypeLabel(t, relation.relation_type);
                  const labelWidth = label.length * 6.2 + 14;
                  const fromName = nameById.get(relation.from_entity_id)?.name ?? relation.from_entity_id;
                  const toName = nameById.get(relation.to_entity_id)?.name ?? relation.to_entity_id;
                  // The arrowhead: a small triangle at the tip, oriented along
                  // the edge, its base perpendicular to the direction.
                  const { tipX, tipY, ux, uy } = geometry;
                  const bx = tipX - ux * 12;
                  const by = tipY - uy * 12;
                  const px = -uy * 6;
                  const py = ux * 6;
                  const arrow = `${tipX},${tipY} ${bx + px},${by + py} ${bx - px},${by - py}`;
                  return (
                    <g
                      key={relation.id}
                      ref={(node) => {
                        if (node !== null) edgeRefs.current.set(relation.id, node);
                        else edgeRefs.current.delete(relation.id);
                      }}
                      data-edge
                      data-edge-id={relation.id}
                      data-testid="graph-edge"
                      role="button"
                      tabIndex={0}
                      aria-label={`${fromName} → ${toName}, ${label}`}
                      className="cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
                      onClick={(event) => {
                        event.stopPropagation();
                        openEdge(relation.id);
                      }}
                      onKeyDown={(event) => {
                        if (event.key !== "Enter" && event.key !== " ") return;
                        event.preventDefault();
                        event.stopPropagation();
                        openEdge(relation.id);
                      }}
                    >
                      {/* The geometry is decorative; the button's aria-label
                          names the edge, so the drawing stays hidden from AT. */}
                      <g aria-hidden="true">
                        {/* A wide transparent stroke makes the thin line easy to click. */}
                        <path d={geometry.d} fill="none" stroke="transparent" strokeWidth={14} />
                        <path d={geometry.d} fill="none" style={{ stroke: ink }} strokeWidth={2} />
                        <polygon points={arrow} style={{ fill: ink }} />
                        <g transform={`translate(${geometry.midX}, ${geometry.midY})`}>
                          <rect x={-labelWidth / 2} y={-11} width={labelWidth} height={22} rx={4} className="fill-surface-container-low stroke-border" strokeWidth={1} />
                          <text textAnchor="middle" y={4} fontSize={11} fontWeight={600} style={{ fill: ink }}>
                            {label}
                          </text>
                        </g>
                      </g>
                    </g>
                  );
                })}
              </svg>
              {visibleEntities.map((entity) => {
                const point = layout.get(entity.id);
                if (point === undefined) return null;
                const theme = typeTheme(entity.type);
                const isSelected = selected?.id === entity.id;
                const line = snippet(entity.content);
                return (
                  <div
                    key={entity.id}
                    data-node
                    data-testid="graph-node"
                    className="absolute z-10 -translate-x-1/2 -translate-y-1/2"
                    style={{ left: point.x, top: point.y }}
                  >
                    <button
                      type="button"
                      onClick={(event) => {
                        event.stopPropagation();
                        setEdgeId(null);
                        select(entity.id);
                      }}
                      aria-pressed={isSelected}
                      className={`flex w-60 items-center gap-2.5 rounded-[var(--radius-surface)] border bg-card px-3.5 py-2.5 text-left shadow-card transition-all hover:shadow-overlay ${FOCUS} ${
                        isSelected ? "border-primary ring-2 ring-primary/30" : "border-rule hover:border-outline"
                      }`}
                    >
                      <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-control)] ${theme.tint}`} style={{ color: theme.var }}>
                        <Icon name={entityTypeIcon(entity.type)} size={20} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider text-foreground ${theme.tint}`}>
                          <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${theme.dot}`} />
                          {entityTypeLabel(t, entity.type)}
                        </span>
                        <span className="mt-0.5 block truncate text-label font-semibold text-foreground">{entity.name}</span>
                        {line !== "" && <span className="block truncate text-[11px] text-muted">{line}</span>}
                      </span>
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* The viewport HUD — zoom in/out and the honest reset. A press here
              is the HUD's own, never a pan (the popover's own guard). */}
          <div
            data-testid="graph-hud"
            onPointerDown={(event) => event.stopPropagation()}
            className="absolute left-4 top-4 z-20 flex flex-col gap-1 rounded-[var(--radius-surface)] border border-rule bg-panel/95 p-1 shadow-overlay"
          >
            <button
              type="button"
              data-testid="zoom-in"
              aria-label={t("knowledge.graph.zoomIn")}
              title={t("knowledge.graph.zoomIn")}
              onClick={() => zoomAt(size.width / 2, size.height / 2, 1.25)}
              className={`flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
            >
              <Icon name="plus" size={16} />
            </button>
            <button
              type="button"
              data-testid="zoom-out"
              aria-label={t("knowledge.graph.zoomOut")}
              title={t("knowledge.graph.zoomOut")}
              onClick={() => zoomAt(size.width / 2, size.height / 2, 1 / 1.25)}
              className={`flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
            >
              <Icon name="minus" size={16} />
            </button>
            <span aria-hidden="true" className="my-0.5 h-px w-full bg-rule" />
            <button
              type="button"
              data-testid="reset-view"
              aria-label={t("knowledge.graph.resetView")}
              title={t("knowledge.graph.resetView")}
              onClick={() => setView(fit)}
              className={`flex h-8 w-8 items-center justify-center rounded-[var(--radius-control)] text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
            >
              <Icon name="focus" size={16} />
            </button>
          </div>

          {/* The legend — the types present and the filtered counts. A press
              here is the legend's own, never a pan. */}
          <div
            data-testid="graph-legend"
            onPointerDown={(event) => event.stopPropagation()}
            className="absolute bottom-4 left-4 z-20 flex flex-wrap items-center gap-3 rounded-[var(--radius-surface)] border border-rule bg-panel/95 px-3.5 py-2 text-meta text-muted shadow-card"
          >
            {typeCounts.map(([type]) => {
              const theme = typeTheme(type);
              return (
                <span key={type} className="flex items-center gap-1.5">
                  <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${theme.dot}`} />
                  {entityTypeLabel(t, type)}
                </span>
              );
            })}
            <span aria-hidden="true" className="text-outline-variant">|</span>
            <span className="font-semibold text-foreground">
              {t("knowledge.dock.entityCount", { count: visibleEntities.length })} • {t("knowledge.graph.relationCount", { count: visibleRelations.length })}
            </span>
          </div>

          {/* The edge note popover — anchored at the edge's midpoint. */}
          {edge !== null && popoverAnchor !== null && (
            <div
              data-testid="edge-popover"
              role="dialog"
              aria-label={t("knowledge.graph.edgeNote")}
              className="absolute z-30 w-64 -translate-x-1/2 -translate-y-full rounded-[var(--radius-surface)] border border-border bg-panel p-3 shadow-overlay"
              style={{ left: clamp(popoverAnchor.x, 130, size.width - 130), top: Math.max(popoverAnchor.y - 12, 90) }}
              onPointerDown={(event) => event.stopPropagation()}
            >
              <div className="flex items-start justify-between gap-2">
                <span className={CARD_EYEBROW}>{t("knowledge.graph.edgeNote")}</span>
                <button
                  type="button"
                  onClick={() => closeEdge(true)}
                  aria-label={t("knowledge.graph.closeNote")}
                  className={`flex h-6 w-6 items-center justify-center rounded text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
                >
                  <Icon name="cross" size={13} />
                </button>
              </div>
              <p className="mt-1 text-meta font-semibold text-foreground">
                {nameById.get(edge.from_entity_id)?.name ?? edge.from_entity_id} → {nameById.get(edge.to_entity_id)?.name ?? edge.to_entity_id}
              </p>
              <p className="text-[11px] text-primary">{relationTypeLabel(t, edge.relation_type)}</p>
              <p className="mt-1 text-meta leading-relaxed text-muted">
                {edge.note !== null && edge.note.trim() !== "" ? edge.note : t("knowledge.graph.edgeNoNote")}
              </p>
            </div>
          )}
        </div>

        {/* The dossier dock — the selected entity's inline panel. */}
        {selected !== null && (
          <div className="w-[360px] shrink-0">
            <EntityDossier
              entity={selected}
              relations={selectedRelations}
              entities={entityList}
              onClose={() => select(null)}
              onSelectEntity={(id) => select(id)}
            />
          </div>
        )}
      </div>

      {/* The subbar's CRUD dialogs (Task 4). The selected entity is the fixed
          end when one stands; the merge moves the selection to the survivor.
          Each mutation refetches the server's truth — no optimistic graph. */}
      {crud === "addRelation" && (
        <CreateRelationDialog
          novelId={novelId}
          entities={entityList}
          from={selected}
          openerId="graph-add-edge"
          onClose={() => setCrud(null)}
        />
      )}
      {crud === "merge" && (
        <MergeDialog
          novelId={novelId}
          entities={entityList}
          source={selected}
          openerId="graph-merge"
          onClose={() => setCrud(null)}
          onMerged={(id) => select(id)}
        />
      )}
    </div>
  );
}
