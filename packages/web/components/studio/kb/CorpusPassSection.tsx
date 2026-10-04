"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { BulkExtractionPanel } from "@/components/studio/extraction/BulkExtractionPanel";
import { CorpusEstimateDialog } from "./CorpusEstimateDialog";

/**
 * CorpusPassSection — sidebar entry for the novel-wide corpus pass (F3 T4,
 * D19a). Chains entry → CorpusEstimateDialog → the F2 panel hosting the
 * PRE-started corpus job (adopted via initialJobId — the job exists
 * server-side before the panel mounts).
 *
 * Extracted from SidebarChapterList.tsx (RULE-04). The zero-chapter gate is
 * NOVEL-wide (an honest zero estimate can't run); the gate decision is
 * computed by the parent — an empty active volume never hides the entry.
 */
export function CorpusPassSection({
  novelId,
  hasNovelChapters,
}: {
  novelId: string;
  hasNovelChapters: boolean;
}) {
  const t = useTranslations("studio");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [jobId, setJobId] = useState<string | null>(null);
  const [panelOpen, setPanelOpen] = useState(false);

  const startPanel = (startedJobId: string) => {
    setJobId(startedJobId);
    setDialogOpen(false);
    setPanelOpen(true);
  };

  return (
    <>
      {hasNovelChapters && (
        <button
          type="button"
          data-testid="corpus-pass-btn"
          onClick={() => setDialogOpen(true)}
          className="mt-2 w-full rounded-md border border-border px-4 py-2 text-sm hover:bg-accent transition-colors"
        >
          {t("kb.corpusPass.entry")}
        </button>
      )}
      <CorpusEstimateDialog
        novelId={novelId}
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onStart={startPanel}
      />
      {panelOpen && jobId !== null && (
        <BulkExtractionPanel
          novelId={novelId}
          chapterIds={[]}
          initialJobId={jobId}
          onClose={() => setPanelOpen(false)}
        />
      )}
    </>
  );
}
