"use client";

import { ChevronDown, ChevronLeft, ChevronRight, ChevronUp, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { ScenePlan, SceneStatus } from "@/types/planning";
import { SceneForm } from "./SceneForm";

interface SceneCardProps {
  scene: ScenePlan;
  /** 0-based index in the chapter's scene list (for move-button boundaries). */
  index: number;
  total: number;
  novelId: string;
  chapterId: string;
  onEdit: (next: ScenePlan) => void;
  onMoveUp: () => void;
  onMoveDown: () => void;
  onRemove: () => void;
}

const CHIP_CLASS =
  "inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium whitespace-nowrap";
const ICON_BUTTON_CLASS =
  "p-1 rounded hover:bg-accent text-muted-foreground disabled:opacity-40 disabled:pointer-events-none";

/** Colour map mirrors the SyncStatusBadge idioms (SYNC status ≡ scene status hues). */
const STATUS_CHIP_CLASS: Record<SceneStatus, string> = {
  planned: "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400",
  in_progress: "bg-yellow-100 text-yellow-600 dark:bg-yellow-900/40 dark:text-yellow-400",
  complete: "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400",
};

const STATUS_LABEL_KEY: Record<SceneStatus, string> = {
  planned: "statusPlanned",
  in_progress: "statusInProgress",
  complete: "statusComplete",
};

/** Compact scene display — collapsed preview, expandable to the full SceneForm. */
export function SceneCard({
  scene,
  index,
  total,
  novelId,
  chapterId,
  onEdit,
  onMoveUp,
  onMoveDown,
  onRemove,
}: SceneCardProps) {
  const t = useTranslations("studio.planning.scenes");
  const [expanded, setExpanded] = useState(false);

  return (
    <li className="border border-border rounded-md bg-card">
      <div className="flex items-center gap-1.5 px-2 py-1.5">
        <span className="text-[10px] text-muted-foreground font-mono shrink-0">
          #{scene.position}
        </span>
        <button
          type="button"
          onClick={() => setExpanded((value) => !value)}
          aria-label={expanded ? t("collapse") : t("expand")}
          aria-expanded={expanded}
          className="min-w-0 flex-1 flex items-center gap-1 text-left"
        >
          <span className="text-xs font-medium truncate flex-1 hover:underline">
            {scene.title || t("untitled")}
          </span>
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5 shrink-0" aria-hidden="true" />
          )}
        </button>
        <span className={`${CHIP_CLASS} ${STATUS_CHIP_CLASS[scene.status]} shrink-0`}>
          {t(STATUS_LABEL_KEY[scene.status])}
        </span>
        <button
          type="button"
          aria-label={t("moveUp")}
          disabled={index === 0}
          onClick={onMoveUp}
          className={ICON_BUTTON_CLASS}
        >
          <ChevronLeft className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          aria-label={t("moveDown")}
          disabled={index === total - 1}
          onClick={onMoveDown}
          className={ICON_BUTTON_CLASS}
        >
          <ChevronRight className="w-3.5 h-3.5" />
        </button>
        <button
          type="button"
          aria-label={t("remove")}
          onClick={onRemove}
          className={`${ICON_BUTTON_CLASS} hover:text-destructive`}
        >
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      {!expanded && (
        <div className="px-2 pb-1.5 space-y-0.5">
          {scene.purpose && (
            <p className="text-xs text-muted-foreground truncate">{scene.purpose}</p>
          )}
          {scene.beats.length > 0 && (
            <p className="text-[10px] text-muted-foreground/80 truncate">
              {scene.beats.join(" · ")}
            </p>
          )}
        </div>
      )}

      {expanded && (
        <div className="px-2 pb-2">
          <SceneForm scene={scene} novelId={novelId} chapterId={chapterId} onChange={onEdit} />
        </div>
      )}
    </li>
  );
}
