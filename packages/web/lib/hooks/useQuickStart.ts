"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { requestFeatureTour } from "@/components/ui/feature-tour";
import { setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { StarterContent, WizardState } from "@/types";

interface UseQuickStartReturn {
  isQuickStarting: boolean;
  /**
   * Creates a project immediately and redirects to the editor.
   * @param projectName  Display name for the new project.
   * @param starter      Optional starter content (e.g. a demo project).
   *                     Defaults to `"blank"` when omitted, preserving the
   *                     original Quick-Start behaviour.
   */
  handleQuickStart: (projectName: string, starter?: StarterContent) => Promise<void>;
}

/**
 * Hook encapsulating the Quick Start flow: creates a project with sensible
 * defaults, requests the feature tour, and redirects to the editor.
 */
export function useQuickStart(): UseQuickStartReturn {
  const router = useRouter();
  const reset = useWizardStore((s) => s.reset);
  const [isQuickStarting, setIsQuickStarting] = useState(false);

  const handleQuickStart = async (projectName: string, starter?: StarterContent) => {
    setIsQuickStarting(true);
    try {
      const state: WizardState = {
        project_name: projectName,
        writing_language: "de",
        autosave_interval: 30,
        title: "",
        author: "",
        genre: "",
        logline: "",
        story_structure: "three_act",
        tone: "dramatic",
        starter: starter ?? "blank",
        import_path: null,
        provider: "anthropic",
        api_key: "",
        model: "",
        ollama_url: "http://localhost:11434",
        zai_endpoint: "general",
        skip_provider: true,
      };
      const result = await setupApi.complete(state);
      reset();
      requestFeatureTour();
      // Navigate directly to the novel editor using novel_id
      // (see WizardShell.handleComplete for rationale)
      router.push(`/novel/${result.novel_id}` as Parameters<typeof router.push>[0]);
    } catch {
      setIsQuickStarting(false);
    }
  };

  return { isQuickStarting, handleQuickStart };
}
