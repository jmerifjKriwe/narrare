"use client";

import { ChevronDown, ChevronUp, Pencil, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { UpdateVolumeRequest, Volume, VolumeStats } from "@/types";
import { useControlledInput, VolumeFormFields } from "./VolumeFormFields";

export { VolumeFormFields } from "./VolumeFormFields";

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
  const [confirmOpen, setConfirmOpen] = useState(false);
  const pendingAction = useRef<(() => void) | null>(null);

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
              pendingAction.current = () => onDelete(volume.id);
              setConfirmOpen(true);
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

      {/* Delete confirmation */}
      <ConfirmDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={t("volumes.deleteVolume")}
        description={t("volumes.deleteConfirm")}
        confirmLabel={t("volumes.deleteVolume")}
        variant="destructive"
        onConfirm={() => {
          pendingAction.current?.();
          pendingAction.current = null;
          setConfirmOpen(false);
        }}
      />
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
