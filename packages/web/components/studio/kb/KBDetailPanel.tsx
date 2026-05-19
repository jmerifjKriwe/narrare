"use client";

/**
 * KB Detail Panel — Column 3 of the 3-column KB browser.
 *
 * Routes between three modes:
 * 1. Empty state — no entry selected
 * 2. Detail/Edit mode — viewing an entry (KBEntryDetail)
 * 3. Create mode — creating a new entry (KBCreateForm)
 */

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import type { KBEntry, KBRelationship } from "@/lib/api/kb";
import { KBCreateForm } from "./KBCreateForm";
import { KBEntryDetail } from "./KBEntryDetail";

interface KBDetailPanelProps {
  novelId: string;
  entry: KBEntry | null;
  relationships: KBRelationship[];
  isCreating: boolean;
  initialEntityType?: import("@/lib/api/kb").KBEntityType;
  onCreateCancel: () => void;
  onCreated: (entryId: string) => void;
  onDeleted: () => void;
}

export function KBDetailPanel({
  novelId,
  entry,
  relationships,
  isCreating,
  initialEntityType,
  onCreateCancel,
  onCreated,
  onDeleted,
}: KBDetailPanelProps) {
  const t = useTranslations("studio");

  if (isCreating) {
    return (
      <KBCreateForm
        novelId={novelId}
        initialEntityType={initialEntityType}
        onCancel={onCreateCancel}
        onCreated={onCreated}
      />
    );
  }

  if (!entry) {
    return (
      <div className="flex-1 overflow-y-auto bg-background">
        <div className="flex flex-col items-center justify-center min-h-[60vh] text-muted-foreground">
          <Plus className="w-16 h-16 mx-auto mb-4 opacity-10" />
          <p className="text-lg mb-1">{t("kb.selectEntry")}</p>
          <p className="text-sm">{t("kb.orCreate")}</p>
        </div>
      </div>
    );
  }

  return (
    <KBEntryDetail
      novelId={novelId}
      entry={entry}
      relationships={relationships}
      onDeleted={onDeleted}
    />
  );
}
