import { useNavigate, useParams, useSearch } from "@tanstack/react-router";
import { useCallback, useEffect, useId, useState } from "react";

import { useTranslation } from "@shell/lib/i18n";
import {
  useDebouncedValue,
  useEntitiesQuery,
  usePassageSearch,
} from "@shell/lib/query";
import { ComboBox } from "@shell/ui/ComboBox";
import { Field, Select } from "@shell/ui/field";
import { GridList } from "@shell/ui/GridList";
import { Notice } from "@shell/ui/Notice";

import { EntityDetail } from "./EntityDetail";
import { TYPE_KEYS, entityTypeLabel } from "./entityTypes";

/** The novel's entities: searched and filtered against the server,
 *  listed, and opened into a detail view on selection. */
export function EntitiesPanel() {
  const t = useTranslation();
  const { id: novelId } = useParams({ from: "/novels/$id" });
  // The selection's address is the URL, the workspace chapter param's
  // sibling on this route: a deep link opens the dock on the entity it
  // names, and selecting writes the param — a replace, because selection
  // is state, not navigation history (unlike chapters, a click here must
  // not own a back-button step). The row is judged against the novel's
  // own list, so a dead id is no selection, never an error.
  const { entity: entityParam } = useSearch({ from: "/novels/$id/knowledge" });
  const navigate = useNavigate();
  // Two views of one list: the unfiltered ask feeds the filters' options,
  // the detail and the pickers; the narrowed ask is what the rows show.
  // While no filter is set both are the same question — and share the
  // cache entry, so the options cost nothing extra until they are used.
  const all = useEntitiesQuery(novelId);
  const [query, setQuery] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [tagFilter, setTagFilter] = useState("");
  const headingId = useId();
  const passagesId = useId();

  // The box's words reach the server once the typing pauses; the filters
  // answer at once. An empty box is no `q`, an "all" option is no filter.
  const debouncedQuery = useDebouncedValue(query, 300);
  const narrowed = useEntitiesQuery(novelId, {
    type: typeFilter || undefined,
    tag: tagFilter || undefined,
    q: debouncedQuery.trim() || undefined,
  });

  const rows = all.data ?? [];
  const shown = narrowed.data ?? [];

  // The filters offer what the novel's rows actually carry — the types in
  // the contract's order, the tags alphabetically.
  const typeOrder = Object.keys(TYPE_KEYS);
  const typeOptions = [...new Set(rows.map((row) => row.type))].sort((a, b) => {
    const rank = (type: string) => {
      const index = typeOrder.indexOf(type);
      return index === -1 ? typeOrder.length : index;
    };
    return rank(a) - rank(b) || a.localeCompare(b);
  });
  const tagOptions = [...new Set(rows.flatMap((row) => row.tags))].sort((a, b) =>
    a.localeCompare(b),
  );

  // A refresh can remove the last entity carrying a selected filter. Clear
  // that stale value so the select and the results agree on the live list.
  // biome-ignore lint/correctness/useExhaustiveDependencies: semantic key — the options' `join("\0")` serialization, not the array identity, decides the re-run; the arrays themselves are rebuilt every render.
  useEffect(() => {
    if (typeFilter && !typeOptions.includes(typeFilter)) setTypeFilter("");
    if (tagFilter && !tagOptions.includes(tagFilter)) setTagFilter("");
  }, [typeFilter, tagFilter, typeOptions.join("\0"), tagOptions.join("\0")]);

  // The detail follows the selection, not the filter: picking an entity and
  // then narrowing the search must not close what was opened. The param is
  // the selection: it is judged against the unfiltered list, and a param
  // the list does not hold is no selection at all.
  const selected = rows.find((entity) => entity.id === entityParam) ?? null;

  // Selecting is one router write: the param lands with a replace, so the
  // back button leaves the dock instead of walking the clicks. Clearing —
  // a delete, or the dead-param cleanup below — is the same write with
  // nothing left to name.
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
  // a replace, so the cleanup is not a history step. Waiting for the rows
  // before judging keeps a just-selected address alive: the param is never
  // judged against an answer that has not landed.
  useEffect(() => {
    if (entityParam === undefined || all.data === undefined) return;
    if (all.data.some((entity) => entity.id === entityParam)) return;
    select(null);
  }, [entityParam, all.data, select]);

  // The box's second tier: the same words, asked of the semantic search
  // (debounced, in the hook) while they are in the box at all.
  const passages = usePassageSearch(query);
  const searching = query.trim() !== "";

  return (
    <section aria-labelledby={headingId} className="mt-6">
      <h3 id={headingId} className="text-body font-semibold">
        {t("knowledge.entitiesHeading")}
      </h3>
      <div className="mt-2">
        <ComboBox
          label={t("knowledge.entitySearchLabel")}
          value={query}
          onChange={setQuery}
          onPick={select}
          items={shown.map((entity) => ({ id: entity.id, text: entity.name }))}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-2">
        <Field label={t("knowledge.typeFilterLabel")}>
          <Select
            value={typeFilter}
            onChange={(event) => setTypeFilter(event.target.value)}
          >
            <option value="">{t("knowledge.filterAllTypes")}</option>
            {typeOptions.map((type) => (
              <option key={type} value={type}>
                {entityTypeLabel(t, type)}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t("knowledge.tagFilterLabel")}>
          <Select
            value={tagFilter}
            onChange={(event) => setTagFilter(event.target.value)}
          >
            <option value="">{t("knowledge.filterAllTags")}</option>
            {tagOptions.map((tag) => (
              <option key={tag} value={tag}>
                {tag}
              </option>
            ))}
          </Select>
        </Field>
      </div>
      {all.isPending || (narrowed.isPending && narrowed.data === undefined) ? (
        // The answer has not arrived yet: the panel asks rather than
        // claims — not the list, and not its empty state either, since no
        // answer is not the fact "no entities". A narrowed ask in flight
        // keeps its previous answer on screen (the hook's own patience),
        // so this state is the first load's alone.
        <Notice tone="quiet" live="status" className="mt-2">
          {t("knowledge.loading")}
        </Notice>
      ) : all.isError || narrowed.isError ? (
        // An unreachable service names itself here, never as an empty
        // list (the outage test stops the real API and reloads — the
        // empty state would be the mask of a missing answer).
        <Notice tone="danger" live="alert" className="mt-2">
          {t("knowledge.errorLoad")}
        </Notice>
      ) : rows.length === 0 ? (
        <Notice tone="quiet" className="mt-2">
          {t("knowledge.noEntities")}
        </Notice>
      ) : shown.length === 0 ? (
        <Notice tone="quiet" className="mt-2">
          {t("knowledge.noResults")}
        </Notice>
      ) : (
        <div className="mt-2">
          <GridList
            label={t("knowledge.entitiesHeading")}
            flush
            items={shown}
            getId={(entity) => entity.id}
            textOf={(entity) => entity.name}
            selectedId={entityParam ?? null}
            onSelect={select}
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
          <h4 id={passagesId} className="text-body font-semibold">
            {t("knowledge.passagesHeading")}
          </h4>
          {passages.isPending ? (
            // The ask is debounced, so the block asks while the words
            // settle and the answer flies — the same patience the entity
            // list's own loading state has.
            <Notice tone="quiet" live="status" className="mt-2">
              {t("knowledge.loading")}
            </Notice>
          ) : passages.isError ? (
            <Notice tone="danger" live="alert" className="mt-2">
              {t("knowledge.errorPassages")}
            </Notice>
          ) : (passages.data ?? []).length === 0 ? (
            <Notice tone="quiet" className="mt-2">
              {t("knowledge.noPassages")}
            </Notice>
          ) : (
            // A hit is a row on the rule, not a card: the snippet with its
            // document's title, the tier reading as one column.
            <ul className="mt-2 flex flex-col">
              {(passages.data ?? []).map((hit) => (
                <li key={hit.chunk_id} className="border-b border-rule py-2">
                  <p className="text-label font-semibold">{hit.document_title}</p>
                  <p className="mt-1 text-body leading-relaxed text-muted">{hit.text}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      ) : null}
      {selected ? (
        /* The detail is keyed by the row: selecting another entity remounts
            it with that row's values, and the corrections' own state (the
            form fields, the picked merge target) never crosses rows. The
            whole unfiltered list rides along: the card reads the other
            ends' names from it, and the pickers offer it. */
        <EntityDetail
          key={selected.id}
          entity={selected}
          rows={rows}
          novelId={novelId}
          onSelect={select}
        />
      ) : null}
    </section>
  );
}
