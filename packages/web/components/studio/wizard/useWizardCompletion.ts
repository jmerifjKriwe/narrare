"use client";

import { useRouter } from "next/navigation";
import { importApi, setupApi } from "@/lib/api/client";
import { buildAdjustments } from "@/lib/importing/simulateOperations";
import { writeSuggestExtractFlag } from "@/lib/importing/suggestExtractFlag";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { ImportCommitResponse } from "@/types";

/**
 * Runs wizard completion: `setup.complete`, optional import commit, navigation.
 *
 * starter="import": the backend created an EMPTY novel — the picked files are
 * committed afterwards (ADR-091 §6.3). On commit failure, degrade instead of
 * blocking: the user still lands in the empty novel, and the sidebar banner
 * (flag `narrare:importFailed:{novel_id}`, read by SidebarChapterList) offers
 * a retry via the ImportModal.
 *
 * On commit SUCCESS the mirror flag `narrare:importSuggestExtract:{novel_id}`
 * is set (F2 T8, ADR-092 spec §8.1, D9a): the sidebar offers a bulk KB
 * extraction of the freshly imported chapters. The payload is self-contained
 * (chapter ids + word count, bounded — see suggestExtractFlag.ts), so the CTA
 * needs no extra fetch.
 */
export function useWizardCompletion(hasProviders: boolean): () => Promise<void> {
  const router = useRouter();

  return async () => {
    // Capture BEFORE reset() clears the store (spec §6.3 — order matters):
    // reset() nulls importSelection, so the commit payload must be read first.
    const currentState = useWizardStore.getState().state;
    const importSelection = useWizardStore.getState().importSelection;
    // Tell backend to skip provider creation when already configured
    if (hasProviders) {
      useWizardStore.setState({
        state: { ...currentState, skip_provider: true },
      });
    }
    const { state: updatedState } = useWizardStore.getState();
    const result = await setupApi.complete(updatedState);

    if (updatedState.starter === "import" && importSelection) {
      let importedChapters: ImportCommitResponse["chapters"] | null = null;
      try {
        const commitResult = await importApi.commit(
          importSelection.files,
          result.novel_id,
          buildAdjustments(importSelection),
        );
        importedChapters = commitResult.chapters;
      } catch {
        sessionStorage.setItem(`narrare:importFailed:${result.novel_id}`, "1");
      }
      // AFTER the failure semantics (T8 fix round): a failed suggestion-write
      // (e.g. sessionStorage quota) must never flip the failure flag above —
      // the import itself succeeded, and "Retry import" would re-commit and
      // duplicate chapters. The banner is a convenience (D9a), not a
      // guarantee, so the error is swallowed deliberately.
      if (importedChapters !== null) {
        try {
          writeSuggestExtractFlag(result.novel_id, importedChapters);
        } catch {
          // best-effort only
        }
      }
    }

    useWizardStore.getState().reset();
    // Navigate directly to the novel editor using novel_id.
    // The API returns redirect_to="/dashboard" for blank starters, but
    // the dashboard route is at "/" — navigating to "/dashboard" hits a 404.
    // Using novel_id always lands the user in the editor after setup.
    router.push(`/novel/${result.novel_id}` as Parameters<typeof router.push>[0]);
  };
}
