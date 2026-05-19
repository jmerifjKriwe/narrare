"use client";

/**
 * KB Entry Header — name input, status badge, save/delete buttons.
 */

import { Loader2, type LucideIcon, Save, Trash2 } from "lucide-react";
import { STATUS_COLORS } from "./constants";

interface KBEntryHeaderProps {
  name: string;
  status: string;
  statusLabel: string;
  Icon: LucideIcon;
  namePlaceholder: string;
  isSaving: boolean;
  isDeleting: boolean;
  onNameChange: (name: string) => void;
  onSave: () => void;
  onDelete: () => void;
  deleteLabel: string;
  saveLabel: string;
}

export function KBEntryHeader({
  name,
  status,
  statusLabel,
  Icon,
  namePlaceholder,
  isSaving,
  isDeleting,
  onNameChange,
  onSave,
  onDelete,
  deleteLabel,
  saveLabel,
}: KBEntryHeaderProps) {
  return (
    <div className="flex items-start justify-between">
      <div className="flex items-center gap-4">
        <div className="w-14 h-14 rounded-xl bg-muted flex items-center justify-center shrink-0">
          <Icon className="w-6 h-6 text-muted-foreground" />
        </div>
        <div className="min-w-0">
          <input
            type="text"
            value={name}
            onChange={(e) => onNameChange(e.target.value)}
            className="text-2xl font-semibold bg-transparent border-none outline-none w-full
              placeholder:text-muted-foreground/30 focus:ring-0 p-0"
            placeholder={namePlaceholder}
          />
          <div className="flex items-center gap-2 mt-1">
            <span
              className={`text-xs px-2 py-0.5 rounded-full font-medium ${STATUS_COLORS[status]}`}
            >
              {statusLabel}
            </span>
          </div>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <button
          type="button"
          onClick={onSave}
          disabled={isSaving}
          className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-lg
            hover:opacity-90 transition-all duration-150 shadow-sm text-sm font-medium
            disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saveLabel}
        </button>
        <button
          type="button"
          onClick={onDelete}
          disabled={isDeleting}
          className="p-2 text-destructive hover:bg-destructive/10 rounded-lg transition-colors
            disabled:opacity-50"
          aria-label={deleteLabel}
        >
          <Trash2 className="w-5 h-5" />
        </button>
      </div>
    </div>
  );
}
