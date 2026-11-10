import { Link, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import type { Entity, Relation } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { usePageTitle } from "@shell/lib/pageTitle";
import { useEntitiesQuery, useNovelRelationsQuery, useNovelsQuery } from "@shell/lib/query";
import { Button } from "@shell/ui/Button";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

import { entityTypeLabel } from "./entityTypes";
import { layoutGraph } from "./graphLayout";
import { previewText } from "./preview";
import { relationTypeLabel } from "./relations";

// The canvas's own box: wide enough for the type bands to stand apart,
// short enough to fit a desk's viewport beside the page's heading. The
// layout clamps every node inside it, so the SVG owns the page's width
// (`w-full h-auto`) and never manufactures a sideways scroll —
// fit-to-viewport plus the page's own scroll. View-only navigation rides
// on top: the layout never moves, only the window onto it (the `GraphView`
// below) pans and zooms.
const VIEWPORT = { width: 960, height: 600 } as const;

/**
 * The window onto the fixed layout: a scale relative to the fitted view
 * plus the layout point at its centre. The fitted view is
 * `{ zoom: 1, cx: width / 2, cy: height / 2 }` and renders the layout's
 * own `0 0 width height` box; zooming narrows (or widens) the window
 * around a stable centre instead of a corner.
 */
interface GraphView {
  zoom: number;
  cx: number;
  cy: number;
}

/**
 * The navigation bounds, as multiples of the fit scale: half scale pulls
 * back to twice the layout box, fourfold reads the densest band. Panning
 * is bounded by the same promise — once the window fits inside the layout
 * it stays inside it, and while it is larger it stays centred — so the
 * graph can never be dragged out of reach and reset is always one action
 * away.
 */
const MIN_ZOOM = 0.5;
const MAX_ZOOM = 4;
const ZOOM_STEP = 1.25;

function fitGraphView(width: number, height: number): GraphView {
  return { zoom: 1, cx: width / 2, cy: height / 2 };
}

function clampGraphView(view: GraphView, width: number, height: number): GraphView {
  const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, view.zoom));
  const windowWidth = width / zoom;
  const windowHeight = height / zoom;
  const cx =
    windowWidth >= width
      ? width / 2
      : Math.min(width - windowWidth / 2, Math.max(windowWidth / 2, view.cx));
  const cy =
    windowHeight >= height
      ? height / 2
      : Math.min(height - windowHeight / 2, Math.max(windowHeight / 2, view.cy));
  return { zoom, cx, cy };
}

/**
 * Zoom by `factor`, anchored on the window fraction the pointer (or the
 * button: the centre) names. The anchor's layout point stays under the
 * pointer, so the visible centre only moves when the pointer is off it —
 * and button zooms, anchored dead centre, never drift toward a corner.
 */
function zoomGraphView(
  view: GraphView,
  width: number,
  height: number,
  factor: number,
  anchor: { fx: number; fy: number } = { fx: 0.5, fy: 0.5 },
): GraphView {
  const zoom = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, view.zoom * factor));
  if (zoom === view.zoom) return view;
  const windowWidth = width / view.zoom;
  const windowHeight = height / view.zoom;
  const nextWidth = width / zoom;
  const nextHeight = height / zoom;
  const anchorX = view.cx - windowWidth / 2 + anchor.fx * windowWidth;
  const anchorY = view.cy - windowHeight / 2 + anchor.fy * windowHeight;
  // The anchor keeps its window fraction; the centre follows half a window
  // behind it — at fx = 0.5 the anchor is the centre and never moves.
  return clampGraphView(
    {
      zoom,
      cx: anchorX + (0.5 - anchor.fx) * nextWidth,
      cy: anchorY + (0.5 - anchor.fy) * nextHeight,
    },
    width,
    height,
  );
}

/** Pan by a screen delta: the content follows the pointer, then clamps. */
function panGraphView(
  view: GraphView,
  width: number,
  height: number,
  dx: number,
  dy: number,
  rectWidth: number,
  rectHeight: number,
): GraphView {
  if (rectWidth <= 0 || rectHeight <= 0) return view;
  const windowWidth = width / view.zoom;
  const windowHeight = height / view.zoom;
  return clampGraphView(
    {
      ...view,
      cx: view.cx - (dx * windowWidth) / rectWidth,
      cy: view.cy - (dy * windowHeight) / rectHeight,
    },
    width,
    height,
  );
}

const NODE_RADIUS = 18;

/**
 * The entity graph as a full page: the novel's entities as named nodes,
 * its relations as lines between them, and the selected node's detail
 * beside the canvas. Read-only throughout — selecting shows, editing
 * stays in the dock behind the one door the detail names. The novel
 * arrives as the `?novel=` search param (the dock's `?entity=` sibling:
 * tolerant in, absent means the picker); a param naming nothing the
 * read returns degrades to the empty state, never an error.
 */
export function GraphPage() {
  const t = useTranslation();
  usePageTitle(t("knowledge.graphHeading"));
  const { novel: novelId } = useSearch({ from: "/knowledge/graph" });
  // A param naming no novel is no novel: the empty string is the absent
  // state, not a novel called "".
  const current = novelId === "" ? undefined : novelId;

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-10">
      <h1 className="text-title font-semibold tracking-tight">{t("knowledge.graphHeading")}</h1>
      <p className="mt-2 text-body text-muted">
        <Link
          to="/knowledge"
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("nav.back")}
        </Link>
      </p>
      {current === undefined ? <NovelPicker /> : <NovelGraph novelId={current} />}
    </div>
  );
}

/** No novel named: the novels to graph, one link each. */
function NovelPicker() {
  const t = useTranslation();
  const novels = useNovelsQuery();

  if (novels.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("knowledge.loading")}
      </Notice>
    );
  }
  if (novels.isError) {
    return (
      <Notice
        tone="danger"
        live="alert"
        className="mt-6"
        action={
          <Button variant="secondary" onClick={() => void novels.refetch()}>
            {t("knowledge.retry")}
          </Button>
        }
      >
        {t("knowledge.errorLoad")}
      </Notice>
    );
  }
  const rows = novels.data ?? [];
  if (rows.length === 0) {
    return (
      <Notice tone="quiet" className="mt-6">
        {t("knowledge.noEntities")}
      </Notice>
    );
  }
  return (
    <nav aria-label={t("knowledge.graphPickNovel")} className="mt-6 flex flex-col gap-2">
      {(rows ?? []).map((novel) => (
        <Link
          key={novel.id}
          to="/knowledge/graph"
          search={{ novel: novel.id }}
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {novel.title}
        </Link>
      ))}
    </nav>
  );
}

/** The named novel's canvas: nodes, edges, and the selected node's detail. */
function NovelGraph({ novelId }: { novelId: string }) {
  const t = useTranslation();
  const entities = useEntitiesQuery(novelId);
  const relations = useNovelRelationsQuery(novelId);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const dragRef = useRef<{ x: number; y: number } | null>(null);

  const rows = useMemo(() => entities.data ?? [], [entities.data]);
  const edges = useMemo(() => relations.data ?? [], [relations.data]);
  const layout = useMemo(
    () =>
      layoutGraph(
        rows.map((entity) => ({ id: entity.id, name: entity.name, type: entity.type })),
        edges.map((relation) => ({
          id: relation.id,
          from_entity_id: relation.from_entity_id,
          to_entity_id: relation.to_entity_id,
          relation_type: relation.relation_type,
        })),
        VIEWPORT,
      ),
    [rows, edges],
  );
  const byId = useMemo(() => new Map(rows.map((entity) => [entity.id, entity])), [rows]);
  const byNodeId = useMemo(() => new Map(layout.nodes.map((node) => [node.id, node])), [layout.nodes]);
  const [view, setView] = useState<GraphView>(() => fitGraphView(layout.width, layout.height));
  // A new novel is a new canvas: the zoom the last one ended at never
  // carries over. Keyed on the novel id alone — resetting on every render
  // would steal the zoom the wheel and the buttons just set. The body reads
  // no novel value (the fit is the same window), so the dep is the reset
  // trigger, not a read.
  // biome-ignore lint/correctness/useExhaustiveDependencies: the novel id is the reset trigger by design, not a value the body reads.
  useEffect(() => {
    setView(fitGraphView(VIEWPORT.width, VIEWPORT.height));
  }, [novelId]);
  // The rendered window: the layout's coordinates, narrowed or widened
  // around the view's centre. Nodes keep their layout positions, so
  // selection, rings and glyphs never learn the view exists.
  const viewBox = useMemo(() => {
    const windowWidth = layout.width / view.zoom;
    const windowHeight = layout.height / view.zoom;
    const round = (n: number) => Math.round(n * 100) / 100;
    return `${round(view.cx - windowWidth / 2)} ${round(view.cy - windowHeight / 2)} ${round(windowWidth)} ${round(windowHeight)}`;
  }, [view, layout.width, layout.height]);

  // Plain wheel over the canvas zooms — the documented intent: the canvas
  // is one fixed box inside a page that scrolls from everywhere else, so
  // the wheel here navigates the graph instead of nudging the page. The
  // listener is native and non-passive so the page truly stays put.
  //
  // It attaches through the canvas's own ref callback, not an effect keyed
  // on viewport constants: on a cold load the canvas mounts only after the
  // reads resolve, when a constant-dep effect has long since run against
  // no element and never runs again. The ref fires with the mounted
  // element, the handler ref always calls through to the latest render's
  // handler, and the state update is functional — so the closure never
  // goes stale and the listener never re-registers.
  const layoutSizeRef = useRef(layout);
  layoutSizeRef.current = layout;
  const wheelHandlerRef = useRef<(event: WheelEvent, svg: SVGSVGElement) => void>(() => {});
  wheelHandlerRef.current = (event, svg) => {
    // A sideways scroll carries no vertical delta: not a zoom, and the
    // gesture stays the page's — preventing it would trap the trackpad
    // over the canvas (deltaY == 0 used to read as zoom-out).
    if (event.deltaY === 0) return;
    event.preventDefault();
    const rect = svg.getBoundingClientRect();
    const anchor =
      rect.width > 0 && rect.height > 0
        ? {
            fx: Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width)),
            fy: Math.min(1, Math.max(0, (event.clientY - rect.top) / rect.height)),
          }
        : { fx: 0.5, fy: 0.5 };
    const { width, height } = layoutSizeRef.current;
    setView((current) =>
      zoomGraphView(current, width, height, event.deltaY < 0 ? ZOOM_STEP : 1 / ZOOM_STEP, anchor),
    );
  };
  const attachWheel = useCallback((svg: SVGSVGElement | null) => {
    if (svg === null) return;
    const onWheel = (event: WheelEvent) => wheelHandlerRef.current(event, svg);
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      svg.removeEventListener("wheel", onWheel);
    };
  }, []);
  // A selection the answer no longer holds is no selection: the dead id
  // leaves with the refetch that dropped it, like the dock's dead param.
  const selected = selectedId === null ? null : (byId.get(selectedId) ?? null);

  async function retry() {
    // The two reads fail independently: a rejecting entities refetch must
    // not keep the relations retry from going out, so both re-ask
    // together instead of awaiting one after the other.
    await Promise.allSettled([entities.refetch(), relations.refetch()]);
  }

  if (entities.isPending || relations.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-6">
        {t("knowledge.loading")}
      </Notice>
    );
  }
  if (entities.isError || relations.isError) {
    return (
      <Notice
        tone="danger"
        live="alert"
        className="mt-6"
        action={
          <Button variant="secondary" onClick={() => void retry()}>
            {t("knowledge.retry")}
          </Button>
        }
      >
        {entities.isError ? t("knowledge.errorLoad") : t("knowledge.errorRelations")}
      </Notice>
    );
  }
  if (rows.length === 0) {
    return (
      <Notice tone="quiet" className="mt-6">
        {t("knowledge.noEntities")}
      </Notice>
    );
  }

  return (
    <div className="mt-6">
      <p className="text-label text-muted">
        {t("knowledge.graphShowing", {
          entities: layout.shownNodes,
          totalEntities: layout.totalNodes,
          relations: layout.shownEdges,
          totalRelations: layout.totalEdges,
        })}
      </p>
      <div className="mt-2 flex flex-wrap gap-2">
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            setView((current) => zoomGraphView(current, layout.width, layout.height, ZOOM_STEP))
          }
        >
          {t("knowledge.graphZoomIn")}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() =>
            setView((current) =>
              zoomGraphView(current, layout.width, layout.height, 1 / ZOOM_STEP),
            )
          }
        >
          {t("knowledge.graphZoomOut")}
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => setView(fitGraphView(layout.width, layout.height))}
        >
          {t("knowledge.graphResetView")}
        </Button>
      </div>
      <svg
        ref={attachWheel}
        role="group"
        aria-label={t("knowledge.graphHeading")}
        viewBox={viewBox}
        className="mt-2 h-auto w-full touch-none cursor-grab rounded-[var(--radius)] border border-rule bg-card active:cursor-grabbing"
        onPointerDown={(event) => {
          // Background-only: a press that starts on a node is a selection,
          // never a drag. The capture keeps the drag alive under fast
          // pointers; a DOM without it (tests) still pans via the moves.
          if (event.button !== 0 || event.target !== event.currentTarget) return;
          dragRef.current = { x: event.clientX, y: event.clientY };
          const target = event.target as Element;
          if (typeof target.setPointerCapture === "function") {
            try {
              target.setPointerCapture(event.pointerId);
            } catch {
              // No capture in this DOM — the moves still arrive.
            }
          }
        }}
        onPointerMove={(event) => {
          const last = dragRef.current;
          if (last === null) return;
          const rect = event.currentTarget.getBoundingClientRect();
          const dx = event.clientX - last.x;
          const dy = event.clientY - last.y;
          dragRef.current = { x: event.clientX, y: event.clientY };
          setView((current) =>
            panGraphView(
              current,
              layout.width,
              layout.height,
              dx,
              dy,
              rect.width,
              rect.height,
            ),
          );
        }}
        onPointerUp={() => {
          dragRef.current = null;
        }}
        onPointerCancel={() => {
          dragRef.current = null;
        }}
      >
        {layout.edges.map((edge) => {
          const from = byNodeId.get(edge.from);
          const to = byNodeId.get(edge.to);
          if (from === undefined || to === undefined) return null;
          // Self-loop: from === to would collapse a line to zero length, so a small loop glyph stands in.
          if (edge.from === edge.to) {
            return (
              <circle
                key={edge.id}
                data-testid="self-loop"
                aria-hidden="true"
                pointer-events="none"
                cx={from.x + NODE_RADIUS}
                cy={from.y - NODE_RADIUS}
                r={10}
                fill="none"
                stroke="var(--rule)"
                strokeWidth={1.5}
              />
            );
          }
          return (
            <line
              key={edge.id}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              stroke="var(--rule)"
              strokeWidth={1.5}
            />
          );
        })}
        {layout.nodes.map((node) => {
          const active = node.id === selected?.id;
          return (
            <g
              key={node.id}
              role="button"
              tabIndex={0}
              aria-label={node.name}
              aria-pressed={active}
              onClick={() => setSelectedId(active ? null : node.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  setSelectedId(active ? null : node.id);
                }
              }}
              // The keyboard's position on the canvas: the file's ring idiom
              // as an outline — a box-shadow ring does not paint on an
              // inner SVG element, while the outline reads around the
              // node's box in both themes.
              className="cursor-pointer focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
            >
              <circle
                cx={node.x}
                cy={node.y}
                r={NODE_RADIUS}
                fill={active ? "var(--focus)" : "var(--panel)"}
                stroke="var(--foreground)"
                strokeWidth={active ? 3 : 1.5}
              />
              <text
                x={node.x}
                y={node.y + NODE_RADIUS + 14}
                textAnchor="middle"
                aria-hidden="true"
                // The label's own ink: SVG text defaults to black, which
                // reads on the light card but dies on the dark one — the
                // token resolves in both, like the circle's own paint.
                fill="var(--foreground)"
              >
                {node.name}
              </text>
            </g>
          );
        })}
      </svg>
      {selected === null ? null : (
        <GraphDetail entity={selected} rows={rows} edges={edges} novelId={novelId} />
      )}
    </div>
  );
}

/** The selected node's read-only glance: what review filed, both edge
 *  directions in the card's own words, and the one door out — the dock,
 *  opened on this entity, where the corrections live. No edit, merge or
 *  delete controls: the canvas never writes. */
function GraphDetail({
  entity,
  rows,
  edges,
  novelId,
}: {
  entity: Entity;
  rows: Entity[];
  edges: Relation[];
  novelId: string;
}) {
  const t = useTranslation();
  const nameOf = (id: string) => rows.find((row) => row.id === id)?.name ?? id;
  const loops = edges.filter(
    (relation) =>
      relation.from_entity_id === relation.to_entity_id &&
      relation.from_entity_id === entity.id,
  );
  const outgoing = edges.filter(
    (relation) =>
      relation.from_entity_id === entity.id && relation.to_entity_id !== entity.id,
  );
  const incoming = edges.filter(
    (relation) =>
      relation.to_entity_id === entity.id && relation.from_entity_id !== entity.id,
  );

  return (
    <section aria-label={entity.name} className="mt-4">
      <Panel>
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-emph font-semibold">{entity.name}</h2>
          <span className="rounded-full bg-panel px-2 py-0.5 text-label">
            {entityTypeLabel(t, entity.type)}
          </span>
        </div>
        {entity.aliases.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-1">
            <span className="text-label text-muted">{t("knowledge.entityAliasesLabel")}:</span>
            {entity.aliases.map((value) => (
              <span key={value} className="rounded-full bg-panel px-2 py-0.5 text-label">
                {value}
              </span>
            ))}
          </div>
        ) : null}
        {entity.tags.length > 0 ? (
          <div className="mt-2 flex flex-wrap items-center gap-1">
            <span className="text-label text-muted">{t("knowledge.entityTagsLabel")}:</span>
            {entity.tags.map((value) => (
              <span key={value} className="rounded-full bg-panel px-2 py-0.5 text-label">
                {value}
              </span>
            ))}
          </div>
        ) : null}
        {entity.content ? (
          <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed">
            {previewText(entity.content)}
          </p>
        ) : null}
        {loops.length + outgoing.length + incoming.length > 0 ? (
          <div className="mt-2">
            <h3 className="text-label font-medium">{t("knowledge.relationsHeading")}</h3>
            {loops.map((relation) => (
              <p key={relation.id} className="mt-1 text-body text-muted">
                {`${relationTypeLabel(t, relation.relation_type)} · ${t("knowledge.relationSelf")}`}
              </p>
            ))}
            {outgoing.length > 0 ? (
              <div className="mt-1">
                <h4 className="text-label text-muted">{t("knowledge.relationsOutgoing")}</h4>
                <ul className="mt-0.5 flex flex-col">
                  {outgoing.map((relation) => (
                    <li key={relation.id} className="text-body text-muted">
                      {`${nameOf(relation.to_entity_id)} · ${relationTypeLabel(t, relation.relation_type)}`}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
            {incoming.length > 0 ? (
              <div className="mt-1">
                <h4 className="text-label text-muted">{t("knowledge.relationsIncoming")}</h4>
                <ul className="mt-0.5 flex flex-col">
                  {incoming.map((relation) => (
                    <li key={relation.id} className="text-body text-muted">
                      {`${nameOf(relation.from_entity_id)} · ${relationTypeLabel(t, relation.relation_type)}`}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : null}
        <div className="mt-3">
          <Link
            to="/novels/$id/knowledge"
            params={{ id: novelId }}
            search={{ entity: entity.id }}
            className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
          >
            {t("knowledge.graphEditInDock")}
          </Link>
        </div>
      </Panel>
    </section>
  );
}
