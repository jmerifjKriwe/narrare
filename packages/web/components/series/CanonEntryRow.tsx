"use client";

/**
 * CanonEntryRow — one Series-Canon KB entry in the Canon tab list.
 *
 * Spec 1, Slice 5, Task 5.5.
 *
 * A keyboard-accessible toggle button header (entity badge, name, and a
 * truncated body preview when collapsed) expands an inline edit form
 * (name + body) with save / delete. Delete is gated by a ConfirmDialog
 * (destructive). The edit form is a sibling of the header button — not nested
 * inside it — so its inputs never trigger the expand toggle. All copy via
 * ``useTranslations``.
 */
import { BookOpen, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { TYPE_ICONS, TYPE_LABEL_KEYS } from "@/components/studio/kb/constants";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { KBEntityType } from "@/lib/api/kb";
import { useDeleteCanonEntry, useUpdateCanonEntry } from "@/lib/hooks/useCanonKB";
import type { SeriesKBEntry } from "@/types";

interface CanonEntryRowProps {
  readonly seriesId: string;
  readonly entry: SeriesKBEntry;
}

/** Truncate a body to a single-line preview (keeps short text intact for tests). */
function previewBody(body: string | null): string {
  if (!body) return "";
  const trimmed = body.trim();
  return trimmed.length > 140 ? `${trimmed.slice(0, 140)}…` : trimmed;
}

export function CanonEntryRow({ seriesId, entry }: CanonEntryRowProps) {
  const t = useTranslations("studio");
  const update = useUpdateCanonEntry(seriesId, entry.id);
  const remove = useDeleteCanonEntry(seriesId);

  const [expanded, setExpanded] = useState(false);
  const [name, setName] = useState(entry.name);
  const [body, setBody] = useState(entry.body ?? "");
  const [confirmOpen, setConfirmOpen] = useState(false);

  // entity_type is a free string on the wire; cast to the known union with a
  // safe fallback for unknown types.
  const entityType = entry.entity_type as KBEntityType;
  const Icon = TYPE_ICONS[entityType] ?? BookOpen;
  const labelKey = TYPE_LABEL_KEYS[entityType] ?? "kb.entity";

  function handleSave(): void {
    update.mutate({ name, body });
  }

  function handleDelete(): void {
    remove.mutate(entry.id);
    setConfirmOpen(false);
  }

  return (
    <article
      data-testid="canon-entry-row"
      className="rounded-lg border border-border bg-card p-4 transition-colors hover:border-primary/40"
    >
      <button
        type="button"
        data-testid="canon-entry-toggle"
        aria-expanded={expanded}
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-3 text-left"
      >
        <span
          data-testid="canon-entry-badge"
          className="inline-flex shrink-0 items-center gap-1.5 rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground"
        >
          <Icon className="h-3.5 w-3.5" />
          {t(labelKey)}
        </span>
        <span className="truncate font-medium text-foreground">{entry.name}</span>
      </button>

      {!expanded && entry.body ? (
        <p
          data-testid="canon-entry-preview"
          className="mt-2 line-clamp-2 text-sm text-muted-foreground"
        >
          {previewBody(entry.body)}
        </p>
      ) : null}

      {expanded ? (
        <div data-testid="canon-entry-edit" className="mt-3 space-y-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("kb.namePlaceholder")}
            </span>
            <input
              type="text"
              data-testid="canon-entry-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-muted-foreground">
              {t("kb.scope.body")}
            </span>
            <textarea
              data-testid="canon-entry-body"
              value={body}
              onChange={(e) => setBody(e.target.value)}
              rows={4}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
            />
          </label>
          <div className="flex items-center gap-2">
            <button
              type="button"
              data-testid="canon-entry-save"
              onClick={handleSave}
              disabled={update.isPending}
              className="inline-flex items-center gap-1.5 rounded-md bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground disabled:opacity-50"
            >
              {update.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {t("kb.save")}
            </button>
            <button
              type="button"
              data-testid="canon-entry-delete"
              onClick={() => setConfirmOpen(true)}
              disabled={remove.isPending}
              className="rounded-md px-3 py-1.5 text-sm font-medium text-destructive hover:bg-destructive/10 disabled:opacity-50"
            >
              {t("kb.deleteEntry")}
            </button>
          </div>
        </div>
      ) : null}

      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("kb.deleteEntry")}
        description={t("kb.deleteConfirm")}
        confirmLabel={t("kb.deleteEntry")}
        variant="destructive"
        onConfirm={handleDelete}
      />
    </article>
  );
}
