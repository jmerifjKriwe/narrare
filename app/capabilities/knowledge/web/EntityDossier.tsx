/**
 * The entity dossier (W5 Task 3) — the graph's inline panel and the first
 * home of the shared detail component the dossiers page (Task 5) formalizes.
 * One component, two homes: it reads the REAL EntityRead fields (name, type,
 * the Markdown body as the description, aliases, tags) and the entity's real
 * relations, and renders the draft's invented fields as honest disabled
 * areas with their gap notes — never fake content:
 *
 * - The status line („Aktiv • …" in the draft) is invented: no per-entity
 *   status exists on any model, so it stands as a neutral gap row.
 * - Manuscript excerpts: no mention tracking exists — a disabled area with
 *   its gap note, never an invented quotation.
 * - Bookmark / export: no endpoint serves them — disabled with their notes.
 * - Edit / quick-add relation: the API carries them, but the dialogs are
 *   Task 4's — disabled placeholders naming that, no dead promise.
 * - Jump to manuscript: no mention tracking — disabled with its gap note.
 *
 * The panel imports no other capability (rule 1); it speaks through the
 * shell's tokens and the capability's own type/relation vocabulary.
 */
import type { Entity, Relation } from "@shell/lib/api/client";
import { useTranslation } from "@shell/lib/i18n";
import { CARD_EYEBROW, FOCUS, NeutralRow } from "@shell/ui/card";
import { Icon } from "@shell/ui/icons";

import { entityTypeLabel, typeTheme } from "./entityTypes";
import { relationTypeLabel } from "./relations";

/** The brand serif, the BookCover pattern: one stack, read from the token. */
const SERIF = "[font-family:var(--font-serif)]";

/** The first letter of the name, the avatar's monogram — or a neutral mark. */
function monogram(name: string): string {
  return Array.from(name.trim())[0]?.toUpperCase() ?? "?";
}

/** A disabled action with its honest gap note as the tooltip — the draft's
 *  button geometry, no dead promise. */
function GapButton({
  label,
  note,
  icon,
  primary = false,
}: {
  label: string;
  note: string;
  icon: Parameters<typeof Icon>[0]["name"];
  primary?: boolean;
}) {
  return (
    <button
      type="button"
      disabled
      title={`${label} (${note})`}
      aria-label={`${label} (${note})`}
      className={`flex w-full items-center justify-center gap-1.5 rounded-[var(--radius-control)] px-3 py-1.5 text-meta font-medium opacity-60 cursor-not-allowed ${
        primary
          ? "bg-primary text-primary-foreground"
          : "bg-surface-container-high text-foreground"
      }`}
    >
      <Icon name={icon} size={14} />
      <span>{label}</span>
    </button>
  );
}

export function EntityDossier({
  entity,
  relations,
  entities,
  onClose,
  onSelectEntity,
}: {
  entity: Entity;
  relations: readonly Relation[];
  entities: readonly Entity[];
  onClose: () => void;
  onSelectEntity: (id: string) => void;
}) {
  const t = useTranslation();
  const theme = typeTheme(entity.type);
  const nameById = new Map(entities.map((row) => [row.id, row]));

  return (
    <aside
      data-testid="entity-dossier"
      aria-label={t("knowledge.dossier.title")}
      className="flex h-full w-full flex-col overflow-y-auto border-l border-border bg-panel"
    >
      <div className="flex flex-col gap-5 p-5">
        {/* The panel header — the eyebrow left, the invented bookmark/export
            doors disabled with their notes, and the close that folds it. */}
        <div className="flex items-center justify-between border-b border-rule pb-3">
          <span className={CARD_EYEBROW}>{t("knowledge.dossier.title")}</span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              disabled
              title={`${t("knowledge.dossier.bookmark")} (${t("knowledge.dossier.bookmarkNote")})`}
              aria-label={`${t("knowledge.dossier.bookmark")} (${t("knowledge.dossier.bookmarkNote")})`}
              className="flex h-7 w-7 cursor-not-allowed items-center justify-center rounded text-muted opacity-60"
            >
              <Icon name="bookmarkCollection" size={15} />
            </button>
            <button
              type="button"
              disabled
              title={`${t("knowledge.dossier.export")} (${t("knowledge.dossier.exportNote")})`}
              aria-label={`${t("knowledge.dossier.export")} (${t("knowledge.dossier.exportNote")})`}
              className="flex h-7 w-7 cursor-not-allowed items-center justify-center rounded text-muted opacity-60"
            >
              <Icon name="export" size={15} />
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label={t("knowledge.dossier.close")}
              className={`flex h-7 w-7 items-center justify-center rounded text-muted transition-colors hover:bg-surface-container hover:text-foreground ${FOCUS}`}
            >
              <Icon name="cross" size={15} />
            </button>
          </div>
        </div>

        {/* The bio card — the avatar in the type's tint, the name, the type
            badge (the colour is the dot; the words stay neutral for AA), and
            the invented status as a neutral gap row. */}
        <div className="flex items-start gap-3.5">
          <div
            className={`${SERIF} flex h-12 w-12 shrink-0 items-center justify-center rounded-[var(--radius-surface)] text-title font-bold italic ${theme.tint}`}
            style={{ color: theme.var }}
            aria-hidden="true"
          >
            {monogram(entity.name)}
          </div>
          <div className="min-w-0 flex-1">
            <h2 className={`${SERIF} truncate text-title font-bold text-foreground`}>{entity.name}</h2>
            <div className="mt-1 flex items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-foreground ${theme.tint}`}>
                <span aria-hidden="true" className={`h-2 w-2 rounded-full ${theme.dot}`} />
                {entityTypeLabel(t, entity.type)}
              </span>
            </div>
          </div>
        </div>

        {/* The invented status — no model carries it, so the neutral gap row
            stands in the draft's place, never a fake „Aktiv". */}
        <NeutralRow label={t("knowledge.dossier.status")} />

        {/* The description — the entity's real Markdown body, shown as the
            plain source the storage keeps; an empty body reads as empty. */}
        <div className="rounded-[var(--radius-surface)] border border-rule bg-surface-container-low p-3.5">
          <span className={`${CARD_EYEBROW} mb-1 block`}>{t("knowledge.dossier.description")}</span>
          {entity.content.trim() !== "" ? (
            <p className="whitespace-pre-wrap text-body leading-relaxed text-foreground">{entity.content}</p>
          ) : (
            <p className="text-body italic text-muted">{t("knowledge.dossier.noDescription")}</p>
          )}
        </div>

        {/* Aliases and tags — real fields, shown only when the row carries
            them; an empty list invents no block. */}
        {entity.aliases.length > 0 && (
          <div className="space-y-1.5">
            <span className={CARD_EYEBROW}>{t("knowledge.dossier.aliases")}</span>
            <div className="flex flex-wrap gap-1.5">
              {entity.aliases.map((alias) => (
                <span key={alias} className="rounded-full bg-surface-container-high px-2 py-0.5 text-meta text-foreground">
                  {alias}
                </span>
              ))}
            </div>
          </div>
        )}
        {entity.tags.length > 0 && (
          <div className="space-y-1.5">
            <span className={CARD_EYEBROW}>{t("knowledge.dossier.tags")}</span>
            <div className="flex flex-wrap gap-1.5">
              {entity.tags.map((tag) => (
                <span key={tag} className="rounded-full bg-surface-container-high px-2 py-0.5 text-meta text-muted">
                  {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* The relations — the entity's real edges, both directions. Each
            card names the other end (a door that selects it), the type's
            wording and the note. The quick-add is Task 4's, disabled. */}
        <div className="flex flex-col gap-2.5">
          <div className="flex items-center justify-between">
            <h3 className={CARD_EYEBROW}>
              {t("knowledge.dossier.relations")} ({relations.length})
            </h3>
            <button
              type="button"
              disabled
              title={`${t("knowledge.dossier.addRelation")} (${t("knowledge.dossier.addRelationNote")})`}
              aria-label={`${t("knowledge.dossier.addRelation")} (${t("knowledge.dossier.addRelationNote")})`}
              className="flex cursor-not-allowed items-center gap-0.5 text-meta text-primary opacity-60"
            >
              <Icon name="plus" size={13} /> {t("knowledge.dossier.addRelation")}
            </button>
          </div>
          {relations.length === 0 ? (
            <p className="text-meta italic text-muted">{t("knowledge.dossier.noRelations")}</p>
          ) : (
            <ul className="flex flex-col gap-2">
              {relations.map((relation) => {
                const outgoing = relation.from_entity_id === entity.id;
                const otherId = outgoing ? relation.to_entity_id : relation.from_entity_id;
                const other = nameById.get(otherId);
                const otherTheme = typeTheme(other?.type ?? "generic");
                return (
                  <li key={relation.id}>
                    <button
                      type="button"
                      onClick={() => onSelectEntity(otherId)}
                      className={`w-full rounded-[var(--radius-control)] border border-rule bg-surface-container-low p-2.5 text-left transition-colors hover:bg-surface-container ${FOCUS}`}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="flex min-w-0 items-center gap-1.5">
                          <span aria-hidden="true" className={`h-2 w-2 shrink-0 rounded-full ${otherTheme.dot}`} />
                          <span className="truncate text-meta font-semibold text-foreground">
                            {other?.name ?? otherId}
                          </span>
                          <span aria-hidden="true" className="shrink-0 text-muted">
                            {outgoing ? "→" : "←"}
                          </span>
                        </span>
                        <span className="shrink-0 text-[11px] text-primary">
                          {relationTypeLabel(t, relation.relation_type)}
                        </span>
                      </span>
                      {relation.note !== null && relation.note.trim() !== "" && (
                        <span className="mt-1 block text-meta leading-relaxed text-muted">{relation.note}</span>
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        {/* Manuscript excerpts — invented: no mention tracking exists. The
            area stands disabled with its gap note, never a fake quotation. */}
        <div className="flex flex-col gap-2">
          <h3 className={CARD_EYEBROW}>{t("knowledge.dossier.excerpts")}</h3>
          <div
            aria-disabled="true"
            className="rounded-[var(--radius-control)] border border-dashed border-border bg-surface-container-low/50 p-3 opacity-70"
          >
            <p className="text-meta italic text-muted">{t("knowledge.dossier.excerptsGap")}</p>
          </div>
        </div>
      </div>

      {/* The action footer — edit is Task 4's dialog, jump needs mention
          tracking; both stand disabled with their honest notes. */}
      <div className="mt-auto flex flex-col gap-2 border-t border-rule bg-surface-container-low p-5">
        <GapButton label={t("knowledge.dossier.edit")} note={t("knowledge.dossier.editNote")} icon="editNote" primary />
        <GapButton label={t("knowledge.dossier.jump")} note={t("knowledge.dossier.jumpNote")} icon="menuBook" />
      </div>
    </aside>
  );
}
