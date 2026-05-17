"use client";

import { ChevronDown, ChevronUp, Loader2, Pencil, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { UpdateVolumeRequest, Volume, VolumeStats } from "@/types";

// ---------------------------------------------------------------------------
// Volume Card
// ---------------------------------------------------------------------------

interface VolumeCardProps {
  readonly volume: Volume;
  readonly stats: VolumeStats | undefined;
  readonly isEditing: boolean;
  readonly onStartEdit: () => void;
  readonly onCancelEdit: () => void;
  readonly onSave: (id: string, payload: UpdateVolumeRequest) => void;
  readonly onDelete: (id: string) => void;
  readonly onReorderUp: () => void;
  readonly onReorderDown: () => void;
  readonly isFirst: boolean;
  readonly isLast: boolean;
  readonly isSaving: boolean;
}

export function VolumeCard({
  volume,
  stats,
  isEditing,
  onStartEdit,
  onCancelEdit,
  onSave,
  onDelete,
  onReorderUp,
  onReorderDown,
  isFirst,
  isLast,
  isSaving,
}: VolumeCardProps) {
  const t = useTranslations("studio");

  if (isEditing) {
    return (
      <VolumeInlineForm
        volume={volume}
        onSave={(payload) => onSave(volume.id, payload)}
        onCancel={onCancelEdit}
        isSaving={isSaving}
      />
    );
  }

  const completionPct = stats?.completion_percentage ?? null;

  return (
    <div className="bg-card border border-border rounded-lg p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium truncate">{volume.title}</h3>
            {volume.is_default && (
              <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary">
                {t("volumes.defaultBadge")}
              </span>
            )}
          </div>
          {volume.subtitle && (
            <p className="text-xs text-muted-foreground mt-0.5 truncate">{volume.subtitle}</p>
          )}
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            type="button"
            onClick={onReorderUp}
            disabled={isFirst}
            className="p-1.5 rounded hover:bg-accent transition-colors disabled:opacity-30"
            title={t("volumes.reorderUp")}
            aria-label={t("volumes.reorderUp")}
          >
            <ChevronUp className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={onReorderDown}
            disabled={isLast}
            className="p-1.5 rounded hover:bg-accent transition-colors disabled:opacity-30"
            title={t("volumes.reorderDown")}
            aria-label={t("volumes.reorderDown")}
          >
            <ChevronDown className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={onStartEdit}
            className="p-1.5 rounded hover:bg-accent transition-colors"
            title={t("volumes.editVolume")}
            aria-label={t("volumes.editVolume")}
          >
            <Pencil className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              if (volume.is_default) return;
              if (window.confirm(t("volumes.deleteConfirm"))) {
                onDelete(volume.id);
              }
            }}
            disabled={volume.is_default}
            className="p-1.5 rounded hover:bg-accent transition-colors text-muted-foreground hover:text-destructive disabled:opacity-30"
            title={volume.is_default ? t("volumes.cannotDeleteDefault") : t("volumes.deleteVolume")}
            aria-label={t("volumes.deleteVolume")}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span>{t("volumes.chapterCount", { count: stats.chapter_count })}</span>
          <span>{t("volumes.wordCount", { count: stats.word_count })}</span>
          {completionPct !== null ? (
            <span>{t("volumes.completion", { percent: Math.round(completionPct) })}</span>
          ) : (
            <span>{t("volumes.noTarget")}</span>
          )}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Volume Inline Edit Form
// ---------------------------------------------------------------------------

interface VolumeInlineFormProps {
  readonly volume: Volume;
  readonly onSave: (payload: UpdateVolumeRequest) => void;
  readonly onCancel: () => void;
  readonly isSaving: boolean;
}

function VolumeInlineForm({ volume, onSave, onCancel, isSaving }: VolumeInlineFormProps) {
  const t = useTranslations("studio");
  const [title, setTitle] = useControlledInput(volume.title);
  const [subtitle, setSubtitle] = useControlledInput(volume.subtitle ?? "");
  const [description, setDescription] = useControlledInput(volume.description ?? "");
  const [target, setTarget] = useControlledInput(volume.word_count_target?.toString() ?? "");

  return (
    <VolumeFormFields
      title={title}
      subtitle={subtitle}
      description={description}
      target={target}
      onTitleChange={setTitle}
      onSubtitleChange={setSubtitle}
      onDescriptionChange={setDescription}
      onTargetChange={setTarget}
      onSubmit={() =>
        onSave({
          title,
          subtitle: subtitle || null,
          description: description || null,
          word_count_target: target ? Number(target) : null,
        })
      }
      onCancel={onCancel}
      submitLabel={t("volumes.save")}
      isPending={isSaving}
    />
  );
}

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Wrapper around useState for controlled inputs. */
function useControlledInput(initial: string): [string, (v: string) => void] {
  const [value, setValue] = useState(initial);
  return [value, setValue];
}
