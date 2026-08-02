"use client";

/**
 * ScopeToggle — switch a KB entry between Series-Canon and Novel-Overlay.
 *
 * Spec 1, Slice 5, Task 5.3.
 *
 * Behaviour:
 *   - Resolves the novel's Series via ``useNovelSeries``. While that query is
 *     loading, or when the novel is standalone (no series), the component
 *     renders nothing — it only makes sense inside a series.
 *   - Shows a two-button segmented control (Canon / Overlay). The button
 *     matching the entry's current ``scope`` is marked active (``aria-pressed``)
 *     and disabled; clicking the inactive button opens a ``ConfirmDialog``
 *     because both directions have side effects (promote removes the entry from
 *     this novel's list; demote re-scopes it to a single novel).
 *   - Promote → ``usePromoteToCanon(novelId, entryId)``.
 *     Demote  → ``useDemoteToOverlay(seriesId, entryId)`` with the current novel
 *     as both the routing anchor and the overlay target.
 *
 * The ``entry`` prop is the minimal ``{ id, scope }`` discriminator (plus an
 * optional ``series_id`` for series-scoped entries). It is structurally
 * compatible with ``ScopedKBEntry`` so callers may pass a full canon/overlay
 * entry, but it does NOT require the full shape — see Task 5.4 where the
 * novel editor adapts its legacy ``KBEntry`` to ``{ id, scope: "novel" }``.
 *
 * All copy goes through ``useTranslations("studio")`` under ``kb.scope.*``
 * (keys added by Task 5.6; until then they render as their key path — the
 * established slice pattern).
 */
import { useTranslations } from "next-intl";
import { useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useDemoteToOverlay, usePromoteToCanon } from "@/lib/hooks/useKBScope";
import { useNovelSeries } from "@/lib/hooks/useNovelSeries";
import type { KBScope } from "@/types";

/** Minimal entry shape ScopeToggle consumes — the id + scope discriminator. */
export interface ScopeToggleEntry {
  readonly id: string;
  readonly scope: KBScope;
  /** Present when ``scope="series"`` (the canon entry's owning series id). */
  readonly series_id?: string | null;
}

interface ScopeToggleProps {
  readonly entry: ScopeToggleEntry;
  readonly novelId: string;
}

export function ScopeToggle({ entry, novelId }: ScopeToggleProps) {
  const t = useTranslations("studio");
  const seriesQuery = useNovelSeries(novelId);

  // For a canon entry the owning series comes from the entry itself; for an
  // overlay it comes from the resolved novel→series chain.
  const seriesId =
    entry.scope === "series" ? (entry.series_id ?? "") : (seriesQuery.data?.id ?? "");

  const promote = usePromoteToCanon(novelId, entry.id);
  const demote = useDemoteToOverlay(seriesId, entry.id);

  const [pendingScope, setPendingScope] = useState<KBScope | null>(null);

  // Hooks are all called above; now the visibility guard.
  if (seriesQuery.isLoading || !seriesQuery.data) return null;

  const isPending = promote.isPending || demote.isPending;
  const isPromoting = pendingScope === "series";

  function handleConfirm(): void {
    // Only clear pendingScope (→ close the ConfirmDialog) on success. On error
    // the dialog stays open so the inline error surfaces and the user can
    // retry (I-F3).
    const onSuccess = () => setPendingScope(null);
    if (pendingScope === "series") {
      promote.mutate(undefined, { onSuccess });
    } else if (pendingScope === "novel") {
      demote.mutate({ novelId, targetNovelId: novelId }, { onSuccess });
    }
  }

  const hasError = promote.isError || demote.isError;

  return (
    <div data-testid="scope-toggle-wrap">
      <fieldset
        data-testid="scope-toggle"
        className="inline-flex items-center gap-1 rounded-lg border border-border bg-muted/40 p-1"
      >
        <legend className="sr-only">{t("kb.scope.label")}</legend>
        <button
          type="button"
          data-testid="scope-toggle-canon"
          aria-pressed={entry.scope === "series"}
          disabled={isPending || entry.scope === "series"}
          onClick={() => setPendingScope("series")}
          className="rounded-md px-3 py-1 text-xs font-medium transition-colors aria-pressed:bg-primary aria-pressed:text-primary-foreground disabled:cursor-default disabled:opacity-100"
        >
          {t("kb.scope.canon")}
        </button>
        <button
          type="button"
          data-testid="scope-toggle-overlay"
          aria-pressed={entry.scope === "novel"}
          disabled={isPending || entry.scope === "novel"}
          onClick={() => setPendingScope("novel")}
          className="rounded-md px-3 py-1 text-xs font-medium transition-colors aria-pressed:bg-primary aria-pressed:text-primary-foreground disabled:cursor-default disabled:opacity-100"
        >
          {t("kb.scope.overlay")}
        </button>

        <ConfirmDialog
          open={pendingScope !== null}
          onOpenChange={(open) => {
            if (!open) setPendingScope(null);
          }}
          title={isPromoting ? t("kb.scope.promoteTitle") : t("kb.scope.demoteTitle")}
          description={
            isPromoting ? t("kb.scope.promoteDescription") : t("kb.scope.demoteDescription")
          }
          confirmLabel={t("kb.scope.confirm")}
          onConfirm={handleConfirm}
        />
      </fieldset>

      {hasError ? (
        <p role="alert" data-testid="scope-toggle-error" className="mt-1 text-xs text-destructive">
          {t("kb.scope.error")}
        </p>
      ) : null}
    </div>
  );
}
