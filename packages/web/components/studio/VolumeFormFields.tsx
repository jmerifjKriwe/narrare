"use client";

import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

// ---------------------------------------------------------------------------
// Shared Form Fields (used by both create and edit)
// ---------------------------------------------------------------------------

interface VolumeFormFieldsProps {
  readonly title: string;
  readonly subtitle: string;
  readonly description: string;
  readonly target: string;
  readonly onTitleChange: (v: string) => void;
  readonly onSubtitleChange: (v: string) => void;
  readonly onDescriptionChange: (v: string) => void;
  readonly onTargetChange: (v: string) => void;
  readonly onSubmit: () => void;
  readonly onCancel: () => void;
  readonly submitLabel: string;
  readonly isPending: boolean;
}

export function VolumeFormFields({
  title,
  subtitle,
  description,
  target,
  onTitleChange,
  onSubtitleChange,
  onDescriptionChange,
  onTargetChange,
  onSubmit,
  onCancel,
  submitLabel,
  isPending,
}: VolumeFormFieldsProps) {
  const t = useTranslations("studio");

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-3">
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div>
          <label
            htmlFor="vol-title"
            className="block text-xs font-medium text-muted-foreground mb-1"
          >
            {t("volumes.titleLabel")} *
          </label>
          <input
            id="vol-title"
            type="text"
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
            className="w-full px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring/15"
          />
        </div>
        <div>
          <label
            htmlFor="vol-subtitle"
            className="block text-xs font-medium text-muted-foreground mb-1"
          >
            {t("volumes.subtitleLabel")}
          </label>
          <input
            id="vol-subtitle"
            type="text"
            value={subtitle}
            onChange={(e) => onSubtitleChange(e.target.value)}
            className="w-full px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring/15"
          />
        </div>
      </div>
      <div>
        <label htmlFor="vol-desc" className="block text-xs font-medium text-muted-foreground mb-1">
          {t("volumes.descriptionLabel")}
        </label>
        <textarea
          id="vol-desc"
          value={description}
          onChange={(e) => onDescriptionChange(e.target.value)}
          rows={2}
          className="w-full px-3 py-1.5 text-sm border border-border rounded-md bg-background resize-y focus:outline-none focus:ring-2 focus:ring-ring/15"
        />
      </div>
      <div className="w-48">
        <label
          htmlFor="vol-target"
          className="block text-xs font-medium text-muted-foreground mb-1"
        >
          {t("volumes.wordCountTargetLabel")}
        </label>
        <input
          id="vol-target"
          type="number"
          value={target}
          onChange={(e) => onTargetChange(e.target.value)}
          min={0}
          className="w-full px-3 py-1.5 text-sm border border-border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-ring/15"
        />
      </div>
      <div className="flex justify-end gap-3 pt-1">
        <button
          type="button"
          onClick={onCancel}
          className="px-4 py-1.5 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          {t("volumes.cancel")}
        </button>
        <button
          type="button"
          onClick={onSubmit}
          disabled={isPending || !title.trim()}
          className="px-4 py-1.5 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : submitLabel}
        </button>
      </div>
    </div>
  );
}

/** Wrapper around useState for controlled inputs. */
export function useControlledInput(initial: string): [string, (v: string) => void] {
  const [value, setValue] = useState(initial);
  return [value, setValue];
}
