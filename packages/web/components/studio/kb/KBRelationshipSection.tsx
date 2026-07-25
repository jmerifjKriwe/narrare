"use client";

/**
 * KB Relationship Section — shows and manages relationships for an entry.
 *
 * Includes add relationship dialog with target search.
 */

import { Plus, X } from "lucide-react";
import { AnimatePresence } from "motion/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import type { KBEntry, KBRelationship } from "@/lib/api/kb";
import { useCreateKBRelationship, useDeleteKBRelationship } from "@/lib/hooks/useKB";
import { AddRelationshipDialog } from "./AddRelationshipDialog";

interface KBRelationshipSectionProps {
  novelId: string;
  entry: KBEntry;
  relationships: KBRelationship[];
}

export function KBRelationshipSection({
  novelId,
  entry,
  relationships,
}: KBRelationshipSectionProps) {
  const t = useTranslations("studio");
  const [showDialog, setShowDialog] = useState(false);

  const createRelMutation = useCreateKBRelationship(novelId, entry.id);
  const deleteRelMutation = useDeleteKBRelationship(novelId, entry.id);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-medium text-muted-foreground">{t("kb.relationships")}</h3>
        <button
          type="button"
          onClick={() => setShowDialog(true)}
          className="flex items-center gap-1 px-3 py-1.5 text-sm border border-border rounded-md hover:bg-accent transition-colors"
        >
          <Plus className="w-3.5 h-3.5" />
          {t("kb.addRelationship")}
        </button>
      </div>

      {relationships.length === 0 ? (
        <p className="text-sm text-muted-foreground">{t("kb.noEntries")}</p>
      ) : (
        <div className="space-y-2">
          {relationships.map((rel) => (
            <RelationshipRow
              key={rel.id}
              relationship={rel}
              entryId={entry.id}
              onDelete={() => deleteRelMutation.mutate(rel.id)}
              isDeleting={deleteRelMutation.isPending}
            />
          ))}
        </div>
      )}

      <AnimatePresence>
        {showDialog && (
          <AddRelationshipDialog
            novelId={novelId}
            sourceEntryId={entry.id}
            onClose={() => setShowDialog(false)}
            onCreate={(data) => {
              createRelMutation.mutate(data, { onSuccess: () => setShowDialog(false) });
            }}
            isPending={createRelMutation.isPending}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// --- Relationship row ---

interface RelationshipRowProps {
  relationship: KBRelationship;
  entryId: string;
  onDelete: () => void;
  isDeleting: boolean;
}

function RelationshipRow({
  relationship: rel,
  entryId,
  onDelete,
  isDeleting,
}: RelationshipRowProps) {
  const t = useTranslations("studio");
  const targetName =
    rel.source_id === entryId
      ? (rel.target_name ?? rel.target_id)
      : (rel.source_name ?? rel.source_id);

  return (
    <div className="flex items-center justify-between bg-muted/30 rounded-md px-3 py-2 text-sm">
      <span>
        <span className="font-medium">{targetName}</span>
        <span className="mx-2 text-muted-foreground">{t("kb.arrow")}</span>
        <span className="text-muted-foreground">{rel.rel_type}</span>
        {rel.label && <span className="ml-2 text-muted-foreground">({rel.label})</span>}
      </span>
      <button
        type="button"
        onClick={onDelete}
        disabled={isDeleting}
        className="p-1 text-muted-foreground hover:text-destructive transition-colors"
        aria-label="Delete relationship"
      >
        <X className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}
