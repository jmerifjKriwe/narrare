import { Link, useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useMemo } from "react";

import type { Entity } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { useEntitiesQuery, useEntityRelationsQuery } from "@shell/lib/query";
import { Notice } from "@shell/ui/Notice";

import { layoutGraph } from "./graphLayout";

// The lens's own box: the dock's column is narrow, so the canvas is small —
// the layout clamps every node inside it, and the SVG owns the dock's width
// (`w-full h-auto`), never a sideways scroll. The full graph stays the
// `/knowledge/graph` canvas behind the cross-link below.
const VIEWPORT = { width: 480, height: 360 } as const;
const NODE_RADIUS = 18;

/**
 * The neighborhood lens: the selected entity's local graph beside the
 * manuscript — the entity itself, its direct neighbors, and the edges among
 * them. Selection is the list's `?entity=` address, so the two views read
 * one selection: picking in either view re-targets the lens. Read-only
 * throughout — editing stays in the list's detail, the full graph behind
 * the one cross-link. No writes, no new endpoint: the entities list and the
 * selected entity's own relations answer are the whole read.
 */
export function NeighborhoodLens() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  const { entity: entityParam } = useSearch({ from: "/novels/$id/knowledge" });
  const navigate = useNavigate();
  const entities = useEntitiesQuery(novelId);

  const rows = entities.data ?? [];
  // Judged against the unfiltered list, the list's own rule: a param the
  // novel does not hold is no selection, never an error.
  const selected = rows.find((entity) => entity.id === entityParam) ?? null;

  // One router write, the list's own contract: the param lands with a
  // replace, so the back button leaves the dock instead of walking the
  // clicks.
  const select = useCallback(
    (entityId: string | null) => {
      void navigate({
        to: ".",
        search: (prev) => ({ ...prev, entity: entityId ?? undefined }),
        replace: true,
      });
    },
    [navigate],
  );

  // A param naming an entity the novel does not have is a dead link: the
  // selection above stayed empty, and the dead value leaves the address —
  // the list's cleanup, mirrored so the lens standing alone (the list
  // unmounted) degrades the same way instead of keeping the dead id.
  useEffect(() => {
    if (entityParam === undefined || entities.data === undefined) return;
    if (entities.data.some((entity) => entity.id === entityParam)) return;
    select(null);
  }, [entityParam, entities.data, select]);

  if (entities.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-2">
        {t("knowledge.loading")}
      </Notice>
    );
  }
  if (entities.isError) {
    return (
      <Notice tone="danger" live="alert" className="mt-2">
        {t("knowledge.errorLoad")}
      </Notice>
    );
  }
  if (rows.length === 0) {
    return (
      <Notice tone="quiet" className="mt-2">
        {t("knowledge.noEntities")}
      </Notice>
    );
  }
  if (selected === null) {
    // No selection yet — or a dead id on its way out through the cleanup
    // above: either way the next step stands in words, not an empty canvas.
    return (
      <Notice tone="quiet" className="mt-2">
        {t("knowledge.neighborhoodEmpty")}
      </Notice>
    );
  }
  return <NeighborhoodGraph novelId={novelId} selected={selected} rows={rows} onSelect={select} />;
}

/** The selected entity's hop-1 graph: the entity, its neighbors, their edges. */
function NeighborhoodGraph({
  novelId,
  selected,
  rows,
  onSelect,
}: {
  novelId: string;
  selected: Entity;
  rows: Entity[];
  onSelect: (entityId: string | null) => void;
}) {
  const t = useTranslation();
  const relations = useEntityRelationsQuery(selected.id);

  const byId = useMemo(() => new Map(rows.map((entity) => [entity.id, entity])), [rows]);
  const edges = useMemo(() => relations.data ?? [], [relations.data]);

  // Hop-1: the selected entity's direct neighbors — the other ends the
  // endpoint's edges touch that the novel still holds. A stale end (an edge
  // whose other side the list no longer has) is no neighbor.
  const neighborIds = useMemo(() => {
    const ids = new Set<string>();
    for (const relation of edges) {
      if (relation.from_entity_id === selected.id && byId.has(relation.to_entity_id)) {
        ids.add(relation.to_entity_id);
      } else if (relation.to_entity_id === selected.id && byId.has(relation.from_entity_id)) {
        ids.add(relation.from_entity_id);
      }
    }
    return ids;
  }, [edges, byId, selected.id]);

  const subEntities = useMemo(
    () => [selected, ...rows.filter((entity) => neighborIds.has(entity.id))],
    [selected, rows, neighborIds],
  );
  const subIds = useMemo(
    () => new Set(subEntities.map((entity) => entity.id)),
    [subEntities],
  );
  // The edges among those nodes: the endpoint's answer with both ends held.
  // Every returned edge touches the selection, so this is the hop-1 set —
  // never a second ring.
  const subEdges = useMemo(
    () =>
      edges.filter(
        (relation) =>
          subIds.has(relation.from_entity_id) && subIds.has(relation.to_entity_id),
      ),
    [edges, subIds],
  );

  const layout = useMemo(
    () =>
      layoutGraph(
        subEntities.map((entity) => ({ id: entity.id, name: entity.name, type: entity.type })),
        subEdges.map((relation) => ({
          id: relation.id,
          from_entity_id: relation.from_entity_id,
          to_entity_id: relation.to_entity_id,
          relation_type: relation.relation_type,
        })),
        VIEWPORT,
      ),
    [subEntities, subEdges],
  );
  const byNodeId = useMemo(
    () => new Map(layout.nodes.map((node) => [node.id, node])),
    [layout.nodes],
  );

  if (relations.isPending) {
    return (
      <Notice tone="quiet" live="status" className="mt-2">
        {t("knowledge.loading")}
      </Notice>
    );
  }
  if (relations.isError) {
    return (
      <Notice tone="danger" live="alert" className="mt-2">
        {t("knowledge.errorRelations")}
      </Notice>
    );
  }

  return (
    <section aria-label={t("knowledge.dockViewNeighborhood")} className="mt-2">
      <svg
        role="group"
        aria-label={t("knowledge.dockViewNeighborhood")}
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        className="mt-2 h-auto w-full rounded-[var(--radius)] border border-rule bg-card"
      >
        {layout.edges.map((edge) => {
          const from = byNodeId.get(edge.from);
          const to = byNodeId.get(edge.to);
          if (from === undefined || to === undefined) return null;
          // A loop collapses a line to zero length, so a small loop glyph
          // stands in — the canvas's own idiom.
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
          const active = node.id === selected.id;
          return (
            <g
              key={node.id}
              role="button"
              tabIndex={0}
              aria-label={node.name}
              aria-pressed={active}
              onClick={() => onSelect(active ? null : node.id)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(active ? null : node.id);
                }
              }}
              // The keyboard's position on the lens: the canvas's ring idiom
              // as an outline — a box-shadow ring does not paint on an inner
              // SVG element, while the outline reads around the node's box.
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
                fill="var(--foreground)"
              >
                {node.name}
              </text>
            </g>
          );
        })}
      </svg>
      {subEdges.length === 0 ? (
        // The entity alone: one node on the canvas, and the fact said in
        // words beside it — not silence where relations would stand.
        <Notice tone="quiet" className="mt-2">
          {t("knowledge.neighborhoodAlone", { name: selected.name })}
        </Notice>
      ) : null}
      <p className="mt-2 text-body text-muted">
        <Link
          to="/knowledge/graph"
          search={{ novel: novelId }}
          className="underline-offset-4 hover:underline focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-focus"
        >
          {t("knowledge.graphOpenLink")}
        </Link>
      </p>
    </section>
  );
}
