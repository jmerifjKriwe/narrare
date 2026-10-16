"use client";

/**
 * AddRelationshipDialog — Modal dialog for creating a new KB relationship.
 *
 * Extracted from KBRelationshipSection for RULE-04 compliance.
 */

import { X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useTranslations } from "next-intl";
import { dialogVariants, overlayVariants } from "@/lib/motion-variants";
import { AddRelationshipForm } from "./AddRelationshipForm";

interface AddRelationshipDialogProps {
  readonly open: boolean;
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
  open,
  novelId,
  sourceEntryId,
  onClose,
  onCreate,
  isPending,
}: AddRelationshipDialogProps) {
  const t = useTranslations("studio");

  // The overlay MUST be gated on `open`. Rendered unconditionally it is an
  // invisible `fixed inset-0 z-50` layer that intercepts every pointer
  // event on the KB view — the detail page is mouse-dead the moment an
  // entry is selected (caught by the Task 7 KB-management E2E,
  // 2026-10-16). AnimatePresence keeps the exit animation intact.
  return (
    <AnimatePresence>
      {open && (
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
            <AddRelationshipForm
              novelId={novelId}
              sourceEntryId={sourceEntryId}
              onClose={onClose}
              onCreate={onCreate}
              isPending={isPending}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
