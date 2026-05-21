"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { tonesApi } from "@/lib/api/client";
import type { CustomTone } from "@/types";

interface ToneFormDialogProps {
  readonly tone: CustomTone | null;
  readonly onClose: () => void;
}

export function ToneFormDialog({ tone, onClose }: ToneFormDialogProps) {
  const t = useTranslations("studio");
  const queryClient = useQueryClient();
  const isEditing = tone !== null;

  const [name, setName] = useState(tone?.name ?? "");
  const [instructions, setInstructions] = useState(tone?.instructions ?? "");
  const [error, setError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (isEditing && tone) {
        return tonesApi.update(tone.id, { name, instructions });
      }
      return tonesApi.create({ name, instructions });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["customTones"] });
      onClose();
    },
    onError: (e: unknown) => {
      setError(e instanceof Error ? e.message : t("tones.saveFailed"));
    },
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !instructions.trim()) {
      setError(t("tones.validationRequired"));
      return;
    }
    setError(null);
    saveMutation.mutate();
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/40 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={isEditing ? t("tones.editTone") : t("tones.addTone")}
        className="relative w-full max-w-md bg-card border border-border rounded-lg p-6 shadow-2xl"
      >
        <h3 className="text-lg font-medium mb-4">
          {isEditing ? t("tones.editTone") : t("tones.addTone")}
        </h3>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <div>
            <label htmlFor="tone-name" className="block text-sm font-medium mb-1.5">
              {t("tones.toneName")}
            </label>
            <input
              id="tone-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
            />
          </div>

          <div>
            <label htmlFor="tone-instructions" className="block text-sm font-medium mb-1.5">
              {t("tones.toneInstructions")}
            </label>
            <textarea
              id="tone-instructions"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={4}
              maxLength={2000}
              className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm resize-y"
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex justify-end gap-3 mt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
            >
              {t("settings.ai.cancel")}
            </button>
            <button
              type="submit"
              disabled={saveMutation.isPending}
              className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
            >
              {saveMutation.isPending ? t("settings.ai.loading") : t("settings.ai.save")}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
