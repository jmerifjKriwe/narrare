"use client";

import { useRouter } from "next/navigation";
import { importApi, setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";

/**
 * Runs wizard completion: `setup.complete`, optional import commit, navigation.
 *
 * starter="import": the backend created an EMPTY novel — the picked files are
 * committed afterwards (ADR-091 §6.3). On commit failure, degrade instead of
 * blocking: the user still lands in the empty novel, and the sidebar banner
 * (flag `narrare:importFailed:{novel_id}`, read by SidebarChapterList) offers
 * a retry via the ImportModal.
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
      try {
        await importApi.commit(importSelection.files, result.novel_id, {
          excluded_indices: importSelection.excludedIndices,
          title_overrides: importSelection.titleOverrides,
        });
      } catch {
        sessionStorage.setItem(`narrare:importFailed:${result.novel_id}`, "1");
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
