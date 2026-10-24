import { useParams } from "@tanstack/react-router";
import { useId, useState } from "react";

import { useTranslation, type MessageKey } from "@shell/lib/i18n";
import { useEntitiesQuery } from "@shell/lib/query";
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

  const rows = entities.data ?? [];
  // The search reaches the names, case-insensitively: the box and the list
  // share one filter, so what the box narrows is what the list shows.
  const needle = query.trim().toLowerCase();
  const filtered = rows.filter((entity) => entity.name.toLowerCase().includes(needle));
  // The detail follows the selection, not the filter: picking an entity and
  // then narrowing the search must not close what was opened.
  const selected = rows.find((entity) => entity.id === selectedId) ?? null;

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
