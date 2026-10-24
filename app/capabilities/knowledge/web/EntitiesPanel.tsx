import { useParams } from "@tanstack/react-router";
import { useId, useState } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { useEntitiesQuery, usePassageSearch } from "@shell/lib/query";
import { ComboBox } from "@shell/ui/ComboBox";
import { GridList } from "@shell/ui/GridList";

// The extraction contract's kinds (knowledge's prompt vocabulary), as
// catalog keys. A kind the contract later adds falls back to "thing" rather
// than crashing the render; the list is the contract's, so it lives beside
// its first consumer and the review queue imports it from here.
const KIND_KEYS = {
  character: "knowledge.kind.character",
  place: "knowledge.kind.place",
  thing: "knowledge.kind.thing",
} as const;

/** An entity kind in the user's language — the list's and the review
 *  queue's shared wording for what a filed row is. */
export function entityKindLabel(t: (key: MessageKey) => string, kind: string): string {
  return kind in KIND_KEYS ? t(KIND_KEYS[kind as keyof typeof KIND_KEYS]) : t("knowledge.kind.thing");
}

/** The novel's entities: searched with the combo box, listed, and opened
 *  into a detail view on selection. */
export function EntitiesPanel() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  const entities = useEntitiesQuery(novelId);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const headingId = useId();
  const detailId = useId();
  const passagesId = useId();

  const rows = entities.data ?? [];
  // The search reaches the names, case-insensitively: the box and the list
  // share one filter, so what the box narrows is what the list shows.
  const needle = query.trim().toLowerCase();
  const filtered = rows.filter((entity) => entity.name.toLowerCase().includes(needle));
  // The detail follows the selection, not the filter: picking an entity and
  // then narrowing the search must not close what was opened.
  const selected = rows.find((entity) => entity.id === selectedId) ?? null;

  // The box's second tier: the same words, asked of the semantic search
  // (debounced, in the hook) while they are in the box at all.
  const passages = usePassageSearch(query);
  const searching = query.trim() !== "";

  return (
    <section aria-labelledby={headingId} className="mt-6">
      <h3 id={headingId} className="text-sm font-semibold">
        {t("knowledge.entitiesHeading")}
      </h3>
      <div className="mt-2">
        <ComboBox
          label={t("knowledge.entitySearchLabel")}
          value={query}
          onChange={setQuery}
          onPick={setSelectedId}
          items={filtered.map((entity) => ({ id: entity.id, text: entity.name }))}
        />
      </div>
      {entities.isPending ? (
        // The answer has not arrived yet: the panel asks rather than
        // claims — not the list, and not its empty state either, since no
        // answer is not the fact "no entities".
        <p className="mt-2 text-sm text-muted">{t("knowledge.loading")}</p>
      ) : entities.isError ? (
        // An unreachable service names itself here, never as an empty
        // list (the outage test stops the real API and reloads — the
        // empty state would be the mask of a missing answer).
        <p role="alert" className="mt-2 text-sm text-danger">
          {t("knowledge.errorLoad")}
        </p>
      ) : rows.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("knowledge.noEntities")}</p>
      ) : filtered.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{t("knowledge.noResults")}</p>
      ) : (
        <div className="mt-2">
          <GridList
            label={t("knowledge.entitiesHeading")}
            items={filtered}
            getId={(entity) => entity.id}
            selectedId={selectedId}
            onSelect={setSelectedId}
            render={(entity) => entity.name}
          />
        </div>
      )}
      {searching ? (
        /* The box's second tier renders under the list it shares the words
            with: the corpus's passages, each with its document's title. Its
            error names itself in this tier's own words (errorPassages, not
            the standalone page's errorSearch) because the dock can show it
            beside the entity list's and the queue's outages — three
            failures at once must stay nameable apart. */
        <section aria-labelledby={passagesId} className="mt-4">
          <h4 id={passagesId} className="text-sm font-semibold">
            {t("knowledge.passagesHeading")}
          </h4>
          {passages.isPending ? (
            // The ask is debounced, so the block asks while the words
            // settle and the answer flies — the same patience the entity
            // list's own loading state has.
            <p className="mt-2 text-sm text-muted">{t("knowledge.loading")}</p>
          ) : passages.isError ? (
            <p role="alert" className="mt-2 text-sm text-danger">
              {t("knowledge.errorPassages")}
            </p>
          ) : (passages.data ?? []).length === 0 ? (
            <p className="mt-2 text-sm text-muted">{t("knowledge.noPassages")}</p>
          ) : (
            <ul className="mt-2 flex flex-col gap-2">
              {(passages.data ?? []).map((hit) => (
                <li key={hit.chunk_id} className="rounded-lg border border-border bg-card p-3">
                  <strong className="text-sm font-semibold">{hit.document_title}</strong>
                  <p className="mt-1 text-sm leading-relaxed text-muted">{hit.text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
      {selected ? (
        <section
          aria-labelledby={detailId}
          className="mt-3 rounded-lg border border-border bg-card p-4"
        >
          <h4 id={detailId} className="text-sm font-semibold">
            {selected.name}
          </h4>
          <p className="mt-1 text-sm text-muted">{entityKindLabel(t, selected.kind)}</p>
          {selected.description ? (
            <p className="mt-2 text-sm leading-relaxed">{selected.description}</p>
          ) : null}
        </section>
      ) : null}
    </section>
  );
}
