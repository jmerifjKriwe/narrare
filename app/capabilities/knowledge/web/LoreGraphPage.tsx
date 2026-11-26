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
 *   shared dialogs (`crudDialogs.tsx`), and both wait disabled with their
 *   note until two entities stand — a relation and a merge each need two
 *   ends, so a sparse canon offers no dead-end dialog. The new-entity door
 *   (W9) opens the hand-made create; a saved row is selected at once, so the
 *   dossier shows the entity and its relations without a second click.
 *
 * The page reads the real API through the shell's query seam and imports no
 * other capability (rule 1). Loading, outage and the empty canon each answer
 * with their own honest face — and each answer stands BELOW the subbar,
 * which never leaves: one consistent mechanism with the dossiers and the
 * sources archive, the sibling doors stay reachable in every state — and
 * the viewport's setup rides the canvas
 * element itself, so it wakes however late the canvas mounts (an uncached
 * load): the framing measures the real container and the wheel zoom installs.
 * Parallel edges between the same pair bow apart, each with its note still
 * reachable; a self-loop arcs clear of its node card instead of under it.
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
import { useEntitiesQuery, useNovelRelationsQuery, useAssistantSessionsQuery, useCloseAssistantSession } from "@shell/lib/query";
import { CARD_EYEBROW, FOCUS } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";
import { useToast } from "@shell/ui/toast";

import { EntityDossier } from "./EntityDossier";
import { CreateRelationDialog, MergeDialog } from "./crudDialogs";
import { EntityCreateDialog } from "./entityCreate/EntityCreateDialog";
import type { EntityPrefill } from "./entityCreate";
import { entityTypeIcon, entityTypeLabel, typeTheme } from "./entityTypes";
import { fitTransform, graphBounds, graphSignature, layoutGraph, type Transform } from "./graphLayout";
import { EntityInterview } from "./interview/EntityInterview";
import { relationTypeLabel } from "./relations";

const GRAPH_PATH = "/novels/$novelId/knowledge/graph";
const DOSSIERS_PATH = "/novels/$novelId/knowledge/dossiers";
const SOURCES_PATH = "/novels/$novelId/knowledge/sources";
const MIN_ZOOM = 0.2;
const MAX_ZOOM = 4;
const FIT_PADDING = 72;
/** How far the arrow tip stands off the target's centre, near its card edge. */
const ARROW_OFFSET = 78;
/** The node card's width — the render's own truth (the card's style carries
 *  it), so the self-loop's geometry derives from the card the node really
 *  draws, never a second guess beside its class. */
const NODE_CARD_WIDTH = 240;
/** How far the k-th of n parallel edges bows off the pair's centre line. */
const EDGE_SPACING = 36;

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
  const toast = useToast();
  const { novelId } = useParams({ from: GRAPH_PATH });
  const { entity: selectedId, interview } = useSearch({ from: GRAPH_PATH });
  const navigate = useNavigate();
  usePageTitle(t("knowledge.graph.title"));

  const entities = useEntitiesQuery(novelId);
  const relations = useNovelRelationsQuery(novelId);
  // The door's count and the panel's list read the same cached rows; the
  // panel opens on the newest open session, or on the type chooser.
  const interviewSessions = useAssistantSessionsQuery(novelId);
  const openInterviewCount = (interviewSessions.data ?? []).filter(
    (session) => session.closed_at === null,
  ).length;

  const [activeType, setActiveType] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [edgeId, setEdgeId] = useState<string | null>(null);
  // Which subbar CRUD dialog stands open (Task 4; the create since W9); the
  // dossier owns its own.
  const [crud, setCrud] = useState<null | "addRelation" | "merge" | "create">(null);
  /** The interview's draft while the create dialog is open through the
   *  handover; null is the hand-made door, which starts empty. */
  const [prefill, setPrefill] = useState<EntityPrefill | null>(null);
  /** The handover's close failed after the row landed: the panel stays and
   *  names the failed end until it is ended again. */
  const [closeFailed, setCloseFailed] = useState(false);
  const closeInterview = useCloseAssistantSession();

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

  // Parallel edges: relations that share an unordered pair of ends would
  // otherwise draw the identical centre line — the earlier edge and its
  // note unreachable under the later. Each takes a bow of its own, indexed
  // in the canonical id order (the layout's own edge-sort convention), so
  // the same set always draws the same picture whatever the rows' arrival
  // order. A self-loop keys on its node alone: its slot fans successive
  // loops off the same node apart.
  const parallelSlot = useMemo(() => {
    const groups = new Map<string, string[]>();
    for (const relation of relationList) {
      const key = [relation.from_entity_id, relation.to_entity_id].sort((a, b) => a.localeCompare(b)).join("\u0000");
      const group = groups.get(key);
      if (group === undefined) groups.set(key, [relation.id]);
      else group.push(relation.id);
    }
    const slots = new Map<string, { index: number; count: number }>();
    for (const group of groups.values()) {
      group.sort((a, b) => a.localeCompare(b));
      group.forEach((id, index) => slots.set(id, { index, count: group.length }));
    }
    return slots;
  }, [relationList]);

  // --- The viewport -------------------------------------------------------
  // The canvas element is state, not a bare ref: on an uncached load the
  // pending and failed faces render no container at all, and a bare ref
  // never tells the setup effects below that one appeared — the measure
  // never ran and the wheel listener never installed, so the graph framed
  // for the 800×600 default with a dead wheel. Carrying the element in
  // state re-runs the setup when the container mounts (an uncached load,
  // a retry landing) and cleans it up when it goes.
  const [container, setContainer] = useState<HTMLDivElement | null>(null);
  const [size, setSize] = useState({ width: 800, height: 600 });
  // Whether a real container has ever been measured. The passive reframe
  // (the signature effect below) can run before the late-mounting
  // container's first measure lands — React flushes it ahead of the render
  // that carries the element — so that first measure reframes once itself;
  // every later measure (a resize) leaves the view alone, as designed.
  const measuredRef = useRef(false);
  useLayoutEffect(() => {
    if (container === null) return;
    const measure = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        const first = !measuredRef.current;
        measuredRef.current = true;
        setSize({ width: rect.width, height: rect.height });
        if (first) setView(fitTransform(boundsRef.current, rect.width, rect.height, FIT_PADDING));
      }
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(container);
    return () => observer.disconnect();
  }, [container]);

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
  // page does not scroll under the graph. Like the measure above it rides
  // the container state, so it installs however late the canvas appears.
  useEffect(() => {
    if (container === null) return;
    const el = container;
    function onWheel(event: WheelEvent) {
      event.preventDefault();
      const rect = el.getBoundingClientRect();
      const factor = event.deltaY < 0 ? 1.15 : 1 / 1.15;
      zoomAt(event.clientX - rect.left, event.clientY - rect.top, factor);
    }
    container.addEventListener("wheel", onWheel, { passive: false });
    return () => container.removeEventListener("wheel", onWheel);
  }, [zoomAt, container]);

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
        search: {
          ...(id !== null ? { entity: id } : {}),
          ...(interview !== undefined ? { interview } : {}),
        },
        replace: true,
      });
    },
    [interview, navigate, novelId],
  );

  // The panel's open state rides the URL beside the selection, as the
  // selected entity does: a reload restores the conversation, and closing
  // the panel only drops the parameter — the session stays open.
  const setInterview = useCallback(
    (target: string | null) => {
      void navigate({
        to: GRAPH_PATH,
        params: { novelId },
        search: {
          ...(selectedId !== undefined ? { entity: selectedId } : {}),
          ...(target !== null ? { interview: target } : {}),
        },
        replace: true,
      });
    },
    [navigate, novelId, selectedId],
  );

  async function openInterviewDoor() {
    // The list is the door's truth: the newest open session, or the chooser.
    // A click that beats the first list read awaits it rather than guessing.
    setCloseFailed(false);
    const rows = interviewSessions.data ?? (await interviewSessions.refetch()).data ?? [];
    const newest = rows.find((session) => session.closed_at === null);
    setInterview(newest !== undefined ? newest.id : "new");
  }

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
      // A self-loop arcs off the node's right side and back, standing clear
      // of the card's real bounds — the card draws OVER the svg, so a loop
      // inside them would hide with its arrow and its label, and its wide
      // hover stroke would sit under the card, unreachable. Successive
      // loops on one node fan apart vertically around the node's level
      // (nested bows at one height would stack their labels); the lone
      // loop — index 0 of 1 — keeps the shape unchanged.
      const slot = parallelSlot.get(relation.id) ?? { index: 0, count: 1 };
      const fan = (slot.index - (slot.count - 1) / 2) * EDGE_SPACING;
      const standX = from.x + NODE_CARD_WIDTH / 2 + 10;
      const bowX = from.x + NODE_CARD_WIDTH / 2 + 84;
      const y = from.y + fan;
      const d = `M ${standX} ${y - 30} C ${bowX} ${y - 88}, ${bowX} ${y + 88}, ${standX} ${y + 30}`;
      // The cubic's true midpoint, t=0.5: (P0 + 3·C1 + 3·C2 + P3) / 8 — the
      // symmetric spread keeps it level with the loop's own centre.
      return { d, midX: (standX + 3 * bowX) / 4, midY: y, tipX: standX, tipY: y + 30, ux: -1, uy: 0 };
    }
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const distance = Math.hypot(dx, dy) || 1;
    const ux = dx / distance;
    const uy = dy / distance;
    const tipX = to.x - ux * ARROW_OFFSET;
    const tipY = to.y - uy * ARROW_OFFSET;
    const slot = parallelSlot.get(relation.id);
    if (slot === undefined || slot.count === 1) {
      // The pair's only edge: the straight centre line, the label between
      // the two centres — the common case, drawn exactly as before.
      return { d: `M ${from.x} ${from.y} L ${tipX} ${tipY}`, midX: (from.x + to.x) / 2, midY: (from.y + to.y) / 2, tipX, tipY, ux, uy };
    }
    // Parallel edges bow apart. The bow rides the pair's canonical
    // perpendicular — first id to second, whatever this edge's direction —
    // so A→B and B→A separate too instead of collapsing onto one side. The
    // quadratic's control point carries twice the bow, which puts B(0.5),
    // the label's anchor and the popover's, exactly one bow off the chord.
    // The tip itself staggers half the bow along the same perpendicular,
    // so two same-direction parallels end in two visible arrowheads
    // instead of one drawn twice; a pair's only edge bows nothing and its
    // tip stands exactly where the straight line's did.
    const flipped = relation.to_entity_id < relation.from_entity_id;
    const px = flipped ? uy : -uy;
    const py = flipped ? -ux : ux;
    const bow = (slot.index - (slot.count - 1) / 2) * EDGE_SPACING;
    const tip2X = tipX + px * (bow / 2);
    const tip2Y = tipY + py * (bow / 2);
    return {
      d: `M ${from.x} ${from.y} Q ${(from.x + tip2X) / 2 + px * bow * 2} ${(from.y + tip2Y) / 2 + py * bow * 2} ${tip2X} ${tip2Y}`,
      midX: (from.x + tip2X) / 2 + px * bow,
      midY: (from.y + tip2Y) / 2 + py * bow,
      tipX: tip2X,
      tipY: tip2Y,
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
    <div id="graph-page" data-testid="graph-page" tabIndex={-1} className="flex h-full flex-col overflow-hidden focus:outline-none">
      {/* The subbar — the view label, the type filter chips, the search and
          the draft's CRUD doors (relation/merge live since Task 4, the
          new-entity create since W9). One consistent mechanism with the
          dossiers and the sources archive: the bar stands in EVERY state —
          pending, failed, empty, populated — so the sibling doors never
          vanish behind an honest face; only the body below it varies. */}
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-container-low px-4 py-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta font-semibold text-foreground shadow-card">
            <span className="text-primary">
              <Icon name="hub" size={15} />
            </span>
            {t("knowledge.graph.title")}
          </span>
          {/* The sibling door (W5 Task 5): the dossiers browse the same cast;
              only a living selection travels — a dead id on the URL resolves
              to no entity and never crosses (the review's stale-param finding). */}
          <button
            type="button"
            data-testid="graph-dossiers-door"
            onClick={() => {
              void navigate({
                to: DOSSIERS_PATH,
                params: { novelId },
                search: selected !== null ? { entity: selected.id } : {},
              });
            }}
            className={`flex items-center gap-1.5 rounded-full border border-rule bg-card px-3 py-1 text-meta text-foreground shadow-card transition-colors hover:bg-surface-container ${FOCUS}`}
          >
            <Icon name="viewList" size={14} /> {t("knowledge.dossiers.title")}
          </button>
          {/* The third sibling door (W5 Task 6): the sources archive keeps
              the library's documents — no entity selection travels there. */}
          <button
            type="button"
            data-testid="graph-sources-door"
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
            disabled={entityList.length < 2}
            onClick={() => setCrud("addRelation")}
            title={
              entityList.length < 2
                ? `${t("knowledge.graph.addEdge")} (${t("knowledge.crud.relationNeedsTwo")})`
                : t("knowledge.graph.addEdge")
            }
            className={`flex items-center gap-1.5 rounded-[var(--radius-control)] bg-surface-container-high px-3 py-1 text-meta text-foreground transition-colors ${FOCUS} ${
              entityList.length < 2 ? "cursor-not-allowed opacity-60" : "hover:bg-surface-container"
            }`}
          >
            <Icon name="hub" size={14} /> {t("knowledge.graph.addEdge")}
          </button>
          <button
            type="button"
            id="graph-new-entity"
            data-testid="graph-new-entity"
            onClick={openInterviewDoor}
            title={t("knowledge.graph.newEntity")}
            className={`flex items-center gap-1.5 rounded-[var(--radius-control)] bg-primary px-3 py-1 text-meta text-primary-foreground transition-colors hover:opacity-95 ${FOCUS}`}
          >
            {/* The visible row (and its count badge) is the sighted label; the
                spoken name carries the count as a whole sentence. */}
            <span aria-hidden="true" className="flex items-center gap-1.5">
              <Icon name="plus" size={14} /> {t("knowledge.graph.newEntity")}
              {openInterviewCount > 0 && (
                <span
                  aria-hidden="true"
                  data-testid="graph-new-entity-count"
                  className="flex h-4 min-w-4 items-center justify-center rounded-full bg-secondary-container px-1 font-mono text-[10px] font-bold text-primary"
                >
                  {openInterviewCount}
                </span>
              )}
            </span>
            <span className="sr-only">
              {openInterviewCount > 0
                ? t("knowledge.graph.newEntityWithOpen", { count: openInterviewCount })
                : t("knowledge.graph.newEntity")}
            </span>
          </button>
        </div>
      </div>

      {/* The body — the honest state's own face; the bar above stays. While
          the interview parameter stands, the panel owns the right column and
          the selected dossier yields; closing the panel returns it. */}
      <div className="relative flex min-h-0 flex-1">
        <div className="flex min-h-0 min-w-0 flex-1 flex-col">
          {pending ? (
        <div data-testid="graph-loading" className="flex min-h-0 flex-1 items-center justify-center">
          <p role="status" className="text-body text-muted">
            {t("knowledge.graph.loading")}
          </p>
        </div>
      ) : failed ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
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
      ) : entityList.length === 0 ? (
        <div className="flex min-h-0 flex-1 items-center justify-center p-6">
          <div data-testid="graph-empty" className="max-w-sm space-y-2 rounded-[var(--radius-surface)] border border-border bg-panel p-8 text-center">
            <span className="inline-block text-muted">
              <Icon name="hub" size={28} />
            </span>
            <p className="text-body font-semibold text-foreground">{t("knowledge.graph.empty")}</p>
            <p className="text-meta text-muted">{t("knowledge.graph.emptyNote")}</p>
          </div>
        </div>
      ) : (
        /* The canvas + the dossier dock. */
        <div className="relative flex min-h-0 flex-1">
          <div
            ref={setContainer}
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
              <div
                className="absolute inset-0 flex items-center justify-center"
                // A press on the no-results face is its own, never a pan: the
                // canvas captures the pointer otherwise, and the captured
                // click never reaches the clear button (the HUD/legend guard's
                // sibling — invisible to jsdom, which has no pointer capture;
                // the E2E's clear-filters leg pins it live).
                onPointerDown={(event) => event.stopPropagation()}
              >
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
                        style={{ width: NODE_CARD_WIDTH }}
                        className={`flex items-center gap-2.5 rounded-[var(--radius-surface)] border bg-card px-3.5 py-2.5 text-left shadow-card transition-all hover:shadow-overlay ${FOCUS} ${
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

          {/* The dossier dock — the selected entity's inline panel. It yields
              while the interview panel owns the column. */}
          {interview === undefined && selected !== null && (
            <div className="w-[360px] shrink-0">
              <EntityDossier
                entity={selected}
                relations={selectedRelations}
                entities={entityList}
                onClose={() => select(null)}
                onSelectEntity={(id) => select(id)}
                focusFallbackId="graph-page"
              />
            </div>
          )}
        </div>
          )}
        </div>

        {/* The interview host stands for the page's lifetime; the panel inside
            it renders only while the `interview` parameter stands, so hiding
            it never loses a running turn, a failure or an unsent draft. */}
        <EntityInterview
          novelId={novelId}
          sessionId={interview === undefined ? undefined : interview === "new" ? null : interview}
          onSelectSession={(target) => {
            setCloseFailed(false);
            setInterview(target);
          }}
          onClose={() => {
            setCloseFailed(false);
            setInterview(null);
          }}
          onManual={() => {
            setCrud("create");
          }}
          onSave={(draft) => {
            setCloseFailed(false);
            setPrefill(draft);
            setCrud("create");
          }}
          returnFocusId="graph-new-entity"
          closeFailed={closeFailed}
        />
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
      {crud === "create" && (
        <EntityCreateDialog
          novelId={novelId}
          entities={entityList}
          rosterSettled={!entities.isPending}
          openerId={prefill === null ? "entity-interview-manual" : "entity-interview-save"}
          source={prefill === null ? "manual" : "interview"}
          prefill={prefill ?? undefined}
          onClose={() => {
            // The handover's draft belongs to this dialog: a later manual
            // door must never inherit it.
            setPrefill(null);
            setCrud(null);
          }}
          onCreated={(entity, relations) => {
            const closesInterview =
              prefill !== null && interview !== undefined && interview !== "new";
            const sessionId = interview;
            setPrefill(null);
            toast.show(t("knowledge.create.created", { count: relations }));
            // The interview's proposal became the row: close the session and
            // leave its parameter behind, so the graph owns the column again.
            // A failed close is not a failed save: the panel stays beside the
            // selected row and names the failed end above its own action.
            if (closesInterview && sessionId !== undefined) {
              closeInterview.mutate(sessionId, {
                onSuccess: () => {
                  setCloseFailed(false);
                  void navigate({
                    to: GRAPH_PATH,
                    params: { novelId },
                    search: { entity: entity.id },
                    replace: true,
                  });
                },
                onError: () => {
                  setCloseFailed(true);
                  select(entity.id);
                },
              });
              return;
            }
            // A hand-made row born from the panel returns to the graph too: the
            // panel yields the column so the new row's dossier can show.
            if (sessionId !== undefined) {
              void navigate({
                to: GRAPH_PATH,
                params: { novelId },
                search: { entity: entity.id },
                replace: true,
              });
            } else {
              select(entity.id);
            }
          }}
        />
      )}
    </div>
  );
}
