"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import {
  clearSuggestExtractFlag,
  type ImportSuggestion,
  readSuggestExtractFlag,
} from "@/lib/importing/suggestExtractFlag";
import { BulkExtractionPanel } from "../extraction/BulkExtractionPanel";
import { ImportFailedBanner } from "./ImportFailedBanner";
import { ImportModal } from "./ImportModal";
import { ImportSuggestExtractBanner } from "./ImportSuggestExtractBanner";

/**
 * ImportLaunchSection — the sidebar's import→extraction entry surface (F2 T8).
 *
 * Owns every piece of launch state that used to sit inline in
 * SidebarChapterList (RULE-04: the sidebar file exceeded the component size
 * limit with this pipeline inline): the ImportModal with its failure flag, the
 * post-import extraction suggestion (sessionStorage flag, spec §8.1) and the
 * BulkExtractionPanel host — the one surface hosting both entry points (modal
 * CTA + wizard suggestion banner). Renders as a fragment so the sidebar footer
 * DOM is unchanged.
 */
interface ImportLaunchSectionProps {
  readonly novelId: string;
}

export function ImportLaunchSection({ novelId }: ImportLaunchSectionProps) {
  const t = useTranslations("studio");

  // Import entry + failure-banner state. The flag lives in sessionStorage
  // (`narrare:importFailed:{novelId}`, set by the wizard's failed commit and
  // read defensively here). Read in an effect — not a useState initializer —
  // because this client component still server-renders: storage access during
  // render would crash SSR and desync hydration (same reason the chapter
  // restore in the sidebar is an effect).
  const [importOpen, setImportOpen] = useState(false);
  const [importFailed, setImportFailed] = useState(false);

  useEffect(() => {
    setImportFailed(sessionStorage.getItem(`narrare:importFailed:${novelId}`) === "1");
  }, [novelId]);

  // Post-import extraction suggestion (F2 T8, spec §8.1): same effect-read
  // lifecycle as the failure flag above, JSON payload via the shared flag
  // contract. The bulk panel state is lifted here — the one surface hosting
  // both entry points (modal CTA + wizard suggestion banner).
  const [suggest, setSuggest] = useState<ImportSuggestion | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkChapterIds, setBulkChapterIds] = useState<string[]>([]);

  useEffect(() => {
    setSuggest(readSuggestExtractFlag(novelId));
  }, [novelId]);

  const openBulkPanel = (chapterIds: readonly string[]) => {
    setBulkChapterIds([...chapterIds]);
    setBulkOpen(true);
  };

  const startSuggestedExtraction = () => {
    if (!suggest) return;
    clearSuggestExtractFlag(novelId);
    const chapterIds = [...suggest.chapterIds];
    setSuggest(null);
    openBulkPanel(chapterIds);
  };

  const dismissSuggestedExtraction = () => {
    clearSuggestExtractFlag(novelId);
    setSuggest(null);
  };

  return (
    <>
      {importFailed && (
        <ImportFailedBanner
          onRetry={() => setImportOpen(true)}
          onDismiss={() => {
            sessionStorage.removeItem(`narrare:importFailed:${novelId}`);
            setImportFailed(false);
          }}
        />
      )}
      {suggest && (
        <ImportSuggestExtractBanner
          chapterIds={suggest.chapterIds}
          wordCount={suggest.wordCount}
          onStart={startSuggestedExtraction}
          onDismiss={dismissSuggestedExtraction}
        />
      )}
      <button
        type="button"
        data-testid="import-chapters-btn"
        onClick={() => setImportOpen(true)}
        className="mt-2 w-full rounded-md border border-border px-4 py-2 text-sm hover:bg-accent transition-colors"
      >
        {t("sidebar.importChapters")}
      </button>
      <ImportModal
        novelId={novelId}
        open={importOpen}
        // Re-evaluate the flag when the modal closes: a successful commit
        // clears the sessionStorage key inside the modal, so the banner must
        // not outlive it (spec §6.2 — banner shows while the key is set).
        onOpenChange={(open) => {
          setImportOpen(open);
          if (!open)
            setImportFailed(sessionStorage.getItem(`narrare:importFailed:${novelId}`) === "1");
        }}
        // Post-commit CTA (F2 T8): the modal hands over the committed ids;
        // the panel mounts here and starts the job over exactly that seed.
        onExtract={openBulkPanel}
      />
      {bulkOpen && (
        <BulkExtractionPanel
          novelId={novelId}
          chapterIds={bulkChapterIds}
          onClose={() => setBulkOpen(false)}
        />
      )}
    </>
  );
}
