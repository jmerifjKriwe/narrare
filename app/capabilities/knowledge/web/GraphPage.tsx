import { Link, useSearch } from "@tanstack/react-router";
import { useMemo, useState } from "react";

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
// layout clamps every node inside it, so the SVG can own the page's width
// (`w-full h-auto`) and never manufacture a sideways scroll — fit-to-
// viewport plus the page's own scroll, no pan or zoom. Interactive
// pan/zoom is a recorded follow-up (the canvas slice owns the read;
// navigating a 200-node graph by scroll alone will not stay enough),
// not a silent absence.
const VIEWPORT = { width: 960, height: 600 } as const;
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
  // A selection the answer no longer holds is no selection: the dead id
  // leaves with the refetch that dropped it, like the dock's dead param.
  const selected = selectedId === null ? null : (byId.get(selectedId) ?? null);

  async function retry() {
    await entities.refetch();
    await relations.refetch();
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
      <svg
        role="group"
        aria-label={t("knowledge.graphHeading")}
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        className="mt-2 h-auto w-full rounded-[var(--radius)] border border-rule bg-card"
      >
        {layout.edges.map((edge) => {
          const from = byNodeId.get(edge.from);
          const to = byNodeId.get(edge.to);
          if (from === undefined || to === undefined) return null;
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
