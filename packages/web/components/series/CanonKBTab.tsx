"use client";

/**
 * CanonKBTab — the Series-Canon Knowledge Base tab body.
 *
 * Spec 1, Slice 5, Task 5.5. Replaces the Slice-4 placeholder on
 * ``/series/[id]/canon``.
 *
 * Lists all Series-Canon KB entries via ``useCanonKB(seriesId)`` with loading /
 * error / empty states. The "Create new Canon entry" button opens an inline
 * creation form (entity type + name) backed by ``useCreateCanonEntry``. Each
 * row (``CanonEntryRow``) owns its own edit / delete via the canon CRUD hooks.
 *
 * RULE-04: the row is a focused sub-component (``CanonEntryRow``); this file
 * owns data + list + create. All copy goes through ``useTranslations("studio")``
 * under ``series.canon.*`` / ``kb.*`` (keys added by Task 5.6; until then they
 * render as their key path — the established slice pattern).
 */
import { Loader2, Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { ENTITY_TYPES } from "@/components/studio/kb/constants";
import type { KBEntityType } from "@/lib/api/kb";
import { useCanonKB, useCreateCanonEntry } from "@/lib/hooks/useCanonKB";
import { CanonEntryRow } from "./CanonEntryRow";

interface CanonKBTabProps {
  readonly seriesId: string;
}

export function CanonKBTab({ seriesId }: CanonKBTabProps) {
  const t = useTranslations("studio");
  const { data: entries, isLoading, isError } = useCanonKB(seriesId);
  const create = useCreateCanonEntry(seriesId);

  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [entityType, setEntityType] = useState<KBEntityType>("character");

  function handleCreate(): void {
    create.mutate({ entity_type: entityType, name });
    setName("");
    setCreateOpen(false);
  }

  if (isLoading) {
    return (
      <div
        data-testid="canon-kb-loading"
        className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"
      >
        <Loader2 className="h-5 w-5 animate-spin" />
        {t("series.canon.loading")}
      </div>
    );
  }

  if (isError) {
    return (
      <div data-testid="canon-kb-error" className="py-12 text-center text-sm text-destructive">
        {t("series.canon.error")}
      </div>
    );
  }

  const list = entries ?? [];

  return (
    <section data-testid="canon-kb-tab" className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-lg font-medium">{t("series.canon.title")}</h2>
        <button
          type="button"
          data-testid="canon-kb-create"
          onClick={() => setCreateOpen((o) => !o)}
          className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90"
        >
          <Plus className="h-4 w-4" />
          {t("series.canon.create")}
        </button>
      </div>

      {createOpen ? (
        <div
          data-testid="canon-kb-create-form"
          className="space-y-3 rounded-lg border border-border bg-card p-4"
        >
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("series.canon.entityType")}
            </span>
            <select
              data-testid="canon-kb-create-type"
              value={entityType}
              onChange={(e) => setEntityType(e.target.value as KBEntityType)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            >
              {ENTITY_TYPES.map((et) => (
                <option key={et} value={et}>
                  {t(`kb.${et}s`)}
                </option>
              ))}
            </select>
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("series.canon.name")}
            </span>
            <input
              type="text"
              data-testid="canon-kb-create-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
          <button
            type="button"
            data-testid="canon-kb-create-submit"
            onClick={handleCreate}
            disabled={create.isPending || name.trim() === ""}
            className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
          >
            {create.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {t("series.canon.create")}
          </button>
        </div>
      ) : null}

      {list.length === 0 ? (
        <p
          data-testid="canon-kb-empty"
          className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground"
        >
          {t("series.canon.empty")}
        </p>
      ) : (
        <ul className="space-y-2">
          {list.map((entry) => (
            <li key={entry.id}>
              <CanonEntryRow seriesId={seriesId} entry={entry} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
