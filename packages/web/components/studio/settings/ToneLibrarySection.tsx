"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Pencil, Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { tonesApi } from "@/lib/api/client";
import type { CustomTone } from "@/types";
import { ToneFormDialog } from "./ToneFormDialog";

const MAX_CUSTOM_TONES = 20;

export function ToneLibrarySection() {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();

  const [editingTone, setEditingTone] = useState<CustomTone | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const { data: tones = [], isLoading } = useQuery({
    queryKey: ["customTones"],
    queryFn: () => tonesApi.list(),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => tonesApi.delete(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customTones"] });
    },
  });

  function handleEdit(tone: CustomTone) {
    setEditingTone(tone);
    setIsCreating(false);
  }

  function handleCreate() {
    setIsCreating(true);
    setEditingTone(null);
  }

  function handleCloseDialog() {
    setEditingTone(null);
    setIsCreating(false);
  }

  const canCreate = tones.length < MAX_CUSTOM_TONES;

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("tones.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("tones.description")}</p>
      </div>

      {/* Header with create button */}
      <div className="flex items-center justify-between mb-4">
        <p className="text-sm text-muted-foreground">
          {t("tones.countLabel", { count: tones.length, max: MAX_CUSTOM_TONES })}
        </p>
        <button
          type="button"
          onClick={handleCreate}
          disabled={!canCreate}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm hover:opacity-90 transition-opacity disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Plus className="w-4 h-4" />
          {t("tones.addTone")}
        </button>
      </div>

      {!canCreate && (
        <p className="text-sm text-amber-600 dark:text-amber-400 mb-4">
          {t("tones.maxTonesReached")}
        </p>
      )}

      {/* Loading state */}
      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Empty state */}
      {!isLoading && tones.length === 0 && (
        <div className="text-center py-12 border border-dashed border-border rounded-lg">
          <p className="text-muted-foreground text-sm">{t("tones.emptyState")}</p>
        </div>
      )}

      {/* Tone list */}
      {!isLoading && tones.length > 0 && (
        <ul className="flex flex-col gap-2">
          {tones.map((tone) => (
            <li
              key={tone.id}
              className="flex items-center justify-between px-4 py-3 border border-border rounded-lg hover:bg-accent/10 transition-colors"
            >
              <div className="flex flex-col gap-0.5 min-w-0 flex-1">
                <span className="text-[0.9375rem] font-medium text-foreground truncate">
                  {tone.name}
                </span>
                <span className="text-[0.75rem] text-muted-foreground line-clamp-2">
                  {tone.instructions}
                </span>
              </div>
              <div className="flex items-center gap-1 shrink-0 ml-4">
                <button
                  type="button"
                  onClick={() => handleEdit(tone)}
                  className="p-2 rounded-lg text-muted-foreground hover:text-foreground hover:bg-secondary transition-colors"
                  aria-label={t("tones.editTone")}
                >
                  <Pencil className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => deleteMutation.mutate(tone.id)}
                  disabled={deleteMutation.isPending}
                  className="p-2 rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors disabled:opacity-50"
                  aria-label={t("tones.deleteTone")}
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}

      {/* Create / Edit dialog */}
      {(isCreating || editingTone) && (
        <ToneFormDialog tone={editingTone} onClose={handleCloseDialog} />
      )}
    </div>
  );
}
