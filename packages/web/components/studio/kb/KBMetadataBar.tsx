"use client";

/**
 * KBMetadataBar — Status selector and tags input row for KB entry detail.
 *
 * Extracted from KBEntryDetail for RULE-04 compliance.
 */

import { useTranslations } from "next-intl";
import type { KBEntryStatus } from "@/lib/api/kb";
import { KBTagInput } from "./KBTagInput";

interface KBMetadataBarProps {
  status: KBEntryStatus;
  tags: string[];
  onStatusChange: (status: KBEntryStatus) => void;
  onTagsChange: (tags: string[]) => void;
}

export function KBMetadataBar({ status, tags, onStatusChange, onTagsChange }: KBMetadataBarProps) {
  const t = useTranslations("studio");

  const statusOptions: KBEntryStatus[] = ["draft", "reviewed", "canon", "deprecated"];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
      <div>
        <label
          htmlFor="entry-status"
          className="block text-xs font-medium text-muted-foreground mb-1.5"
        >
          {t("metadataSidebar.status")}
        </label>
        <select
          id="entry-status"
          value={status}
          onChange={(e) => onStatusChange(e.target.value as KBEntryStatus)}
          className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm
            transition-colors duration-150 hover:border-muted-foreground/30
            focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary/20"
        >
          {statusOptions.map((s) => (
            <option key={s} value={s}>
              {t(`kb.status.${s}`)}
            </option>
          ))}
        </select>
      </div>
      <div>
        <span className="block text-xs font-medium text-muted-foreground mb-1.5">
          {t("kb.tags")}
        </span>
        <KBTagInput value={tags} onChange={onTagsChange} placeholder={t("kb.tagsPlaceholder")} />
      </div>
    </div>
  );
}
