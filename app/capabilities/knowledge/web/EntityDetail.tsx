import { useTranslation } from "@shell/lib/i18n";
import type { Entity, Relation } from "@shell/lib/api/client";
import { useEntityRelationsQuery } from "@shell/lib/query";
import { Notice } from "@shell/ui/Notice";
import { Panel } from "@shell/ui/Panel";

import { DeleteEntityDialog } from "./DeleteEntityDialog";
import { EditEntityDialog } from "./EditEntityDialog";
import { entityTypeLabel } from "./entityTypes";
import { MergeEntityDialog } from "./MergeEntityDialog";
import { previewText } from "./preview";
import { relationTypeLabel } from "./relations";

// The card previews the body as the source it is (D2: WP3 brings the
// editor), cut where a glance ends and the detail dialog begins.
const PREVIEW_LENGTH = 140;

/** One direction group of the card's read-only edges: the group's name and
 *  the lines it holds — the other end's name and the type's wording, the
 *  same sentence the old arrow lines carried, cut of its arrows. */
function EdgeGroup({
  label,
  edges,
  entityId,
  nameOf,
}: {
  label: string;
  edges: Relation[];
  entityId: string;
  nameOf: (id: string) => string;
}) {
  const t = useTranslation();
  return (
    <div className="mt-1">
      <h6 className="text-label text-muted">{label}</h6>
      <ul className="mt-0.5 flex flex-col">
        {edges.map((relation) => (
          <li key={relation.id} className="text-body text-muted">
            {`${nameOf(
              relation.from_entity_id === entityId
                ? relation.to_entity_id
                : relation.from_entity_id,
            )} · ${relationTypeLabel(t, relation.relation_type)}`}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The selected entity's detail, kept compact (D9): what review filed —
 *  name, type, chips, the body's source preview, every edge by direction
 *  and the self-relations under their mark — and the doors to the
 *  corrections, which all live in dialogs. */
export function EntityDetail({
  entity,
  rows,
  novelId,
  onSelect,
}: {
  entity: Entity;
  rows: Entity[];
  novelId: string;
  onSelect: (id: string | null) => void;
}) {
  const t = useTranslation();
  const relations = useEntityRelationsQuery(entity.id);
  const edges = relations.data ?? [];
  const nameOf = (id: string) => rows.find((row) => row.id === id)?.name ?? id;
  const loops = edges.filter((relation) => relation.from_entity_id === relation.to_entity_id);
  const outgoing = edges.filter(
    (relation) =>
      relation.from_entity_id === entity.id && relation.to_entity_id !== entity.id,
  );
  const incoming = edges.filter(
    (relation) =>
      relation.to_entity_id === entity.id && relation.from_entity_id !== entity.id,
  );

  return (
    // The section is the region the tests and the focus contract name (the
    // row it opened); the panel inside is its one painted surface.
    <section aria-label={entity.name} className="mt-3">
      <Panel>
        {/* The name is a card title (§8.2: text-emph, 600), not an
            eyebrow — it heads the body, with the type beside it. */}
        <div className="flex flex-wrap items-center gap-2">
          <h4 className="text-emph font-semibold">{entity.name}</h4>
          <span className="rounded-full bg-panel px-2 py-0.5 text-label">
            {entityTypeLabel(t, entity.type)}
          </span>
        </div>
        {entity.aliases.length > 0 ? (
          <ChipRow label={t("knowledge.entityAliasesLabel")} values={entity.aliases} />
        ) : null}
        {entity.tags.length > 0 ? (
          <ChipRow label={t("knowledge.entityTagsLabel")} values={entity.tags} />
        ) : null}
        {entity.content ? (
          // The body as the glance reads it: the stored Markdown's display
          // copy — entities decoded, serializer escapes stripped (preview.ts)
          // — cut for a glance. The store keeps the canonical bytes; the
          // editor, not the preview, is where the document renders.
          <p className="mt-2 whitespace-pre-wrap text-body leading-relaxed">
            {truncate(previewText(entity.content))}
          </p>
        ) : null}
        {relations.isError ? (
          <Notice tone="danger" live="alert" className="mt-2">
            {t("knowledge.errorRelations")}
          </Notice>
        ) : edges.length > 0 ? (
          <div className="mt-2">
            <h5 className="text-label font-medium">{t("knowledge.relationsHeading")}</h5>
            {loops.map((relation) => (
              <p key={relation.id} className="mt-1 text-body text-muted">
                {`${relationTypeLabel(t, relation.relation_type)} · ${t("knowledge.relationSelf")}`}
              </p>
            ))}
            {outgoing.length > 0 ? (
              <EdgeGroup
                label={t("knowledge.relationsOutgoing")}
                edges={outgoing}
                entityId={entity.id}
                nameOf={nameOf}
              />
            ) : null}
            {incoming.length > 0 ? (
              <EdgeGroup
                label={t("knowledge.relationsIncoming")}
                edges={incoming}
                entityId={entity.id}
                nameOf={nameOf}
              />
            ) : null}
          </div>
        ) : null}
        <div className="mt-3 flex flex-wrap gap-2">
          <EditEntityDialog entity={entity} rows={rows} novelId={novelId} />
          <MergeEntityDialog
            entity={entity}
            others={rows.filter((row) => row.id !== entity.id)}
            novelId={novelId}
            onSelect={onSelect}
          />
          <DeleteEntityDialog entity={entity} novelId={novelId} onSelect={onSelect} />
        </div>
      </Panel>
    </section>
  );
}

/** A labeled row of read-only chips: what the card shows of the aliases
 *  and tags the dialog edits. */
function ChipRow({ label, values }: { label: string; values: string[] }) {
  return (
    <div className="mt-2 flex flex-wrap items-center gap-1">
      <span className="text-label text-muted">{label}:</span>
      {values.map((value) => (
        <span key={value} className="rounded-full bg-panel px-2 py-0.5 text-label">
          {value}
        </span>
      ))}
    </div>
  );
}

function truncate(content: string): string {
  return content.length > PREVIEW_LENGTH ? `${content.slice(0, PREVIEW_LENGTH)}…` : content;
}
