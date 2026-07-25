"use client";

/**
 * AddRelationshipDialog — Modal dialog for creating a new KB relationship.
 *
 * Extracted from KBRelationshipSection for RULE-04 compliance.
 */

import { X } from "lucide-react";
import { motion } from "motion/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { useKBEntries } from "@/lib/hooks/useKB";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";

interface AddRelationshipDialogProps {
  novelId: string;
  sourceEntryId: string;
  onClose: () => void;
  onCreate: (data: {
    source_id: string;
    target_id: string;
    rel_type: string;
    label?: string | null;
    direction?: "directed" | "mutual";
  }) => void;
  isPending: boolean;
}

export function AddRelationshipDialog({
  novelId,
  sourceEntryId,
  onClose,
  onCreate,
  isPending,
}: AddRelationshipDialogProps) {
  const t = useTranslations("studio");

  const [searchQ, setSearchQ] = useState("");
  const [selectedTargetId, setSelectedTargetId] = useState("");
  const [relType, setRelType] = useState("");
  const [label, setLabel] = useState("");
  const [direction, setDirection] = useState<"directed" | "mutual">("directed");

  const { data: searchData } = useKBEntries(novelId, { page_size: 50 });
  const filtered = (searchData?.items ?? []).filter(
    (e) =>
      e.id !== sourceEntryId &&
      (e.name.toLowerCase().includes(searchQ.toLowerCase()) || searchQ === ""),
  );

  function handleCreate() {
    if (!selectedTargetId || !relType) return;
    onCreate({
      source_id: sourceEntryId,
      target_id: selectedTargetId,
      rel_type: relType,
      label: label || null,
      direction,
    });
  }

  return (
    <motion.div
      className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4"
      variants={overlayVariants}
      initial="hidden"
      animate="visible"
      exit="exit"
    >
      <motion.div
        className="bg-card border border-border rounded-xl shadow-2xl max-w-xl w-full overflow-hidden"
        variants={dialogVariants}
        initial="hidden"
        animate="visible"
        exit="exit"
      >
        <div className="p-6 border-b border-border flex items-center justify-between">
          <h3 className="font-medium">{t("kb.addRelationship")}</h3>
          <button
            type="button"
            onClick={onClose}
            className="p-1 hover:bg-accent rounded-md"
            aria-label={t("kb.cancel")}
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-6 space-y-4">
          {/* Target search */}
          <div>
            <label htmlFor="rel-target" className="block text-sm font-medium mb-1.5">
              {t("kb.targetEntry")}
            </label>
            <input
              id="rel-target"
              type="text"
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
              placeholder={t("kb.targetEntryPlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            />
            {searchQ && (
              <div className="mt-1 border border-border rounded-md max-h-32 overflow-y-auto">
                {filtered.slice(0, 8).map((e) => (
                  <button
                    key={e.id}
                    type="button"
                    onClick={() => {
                      setSelectedTargetId(e.id);
                      setSearchQ(e.name);
                    }}
                    className={`w-full text-left px-3 py-1.5 text-sm hover:bg-accent ${
                      selectedTargetId === e.id ? "bg-accent" : ""
                    }`}
                  >
                    {e.name} ({e.entity_type})
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Rel type */}
          <div>
            <label htmlFor="rel-type" className="block text-sm font-medium mb-1.5">
              {t("kb.relType")}
            </label>
            <input
              id="rel-type"
              type="text"
              value={relType}
              onChange={(e) => setRelType(e.target.value)}
              placeholder={t("kb.relTypePlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            />
          </div>

          {/* Direction */}
          <fieldset className="flex items-center gap-4">
            <legend className="text-sm font-medium">{t("kb.direction")}</legend>
            <label className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                name="direction"
                checked={direction === "directed"}
                onChange={() => setDirection("directed")}
              />
              {t("kb.directed")}
            </label>
            <label className="flex items-center gap-1.5 text-sm">
              <input
                type="radio"
                name="direction"
                checked={direction === "mutual"}
                onChange={() => setDirection("mutual")}
              />
              {t("kb.mutual")}
            </label>
          </fieldset>

          {/* Label */}
          <div>
            <label htmlFor="rel-label" className="block text-sm font-medium mb-1.5">
              {t("kb.relLabel")}
            </label>
            <input
              id="rel-label"
              type="text"
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder={t("kb.relLabelPlaceholder")}
              className="w-full px-3 py-2 bg-input-background border border-border rounded-md text-sm"
            />
          </div>
        </div>
        <div className="p-6 border-t border-border flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            className="flex items-center gap-2 px-4 py-2 border border-border rounded-md hover:bg-accent transition-colors text-sm"
          >
            {t("kb.cancel")}
          </button>
          <button
            type="button"
            onClick={handleCreate}
            disabled={!selectedTargetId || !relType || isPending}
            className="flex items-center gap-2 px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm shadow-sm disabled:opacity-50"
          >
            {t("kb.create")}
          </button>
        </div>
      </motion.div>
    </motion.div>
  );
}
