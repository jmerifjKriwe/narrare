/**
 * Setup Wizard API — validation and completion.
 */

import type { AIProvider, DemoProjectInfo, ModelCatalogProvenance, WizardState } from "@/types";
import { fetchApi } from "./core";

export const setupApi = {
  validateStep1: (data: {
    project_name: string;
    writing_language: string;
    autosave_interval: number;
  }) =>
    fetchApi<{ valid: boolean }>("/setup/validate/step-1", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  validateStep2: (data: {
    title: string;
    author?: string;
    genre?: string;
    logline?: string;
    story_structure?: string;
    tone?: string;
  }) =>
    fetchApi<{ valid: boolean }>("/setup/validate/step-2", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  validateStep3: (data: { starter: string; import_path?: string | null }) =>
    fetchApi<{ valid: boolean; starter: string; demo_info: DemoProjectInfo | null }>(
      "/setup/validate/step-3",
      { method: "POST", body: JSON.stringify(data) },
    ),

  validateStep4: (data: {
    provider: AIProvider;
    api_key: string;
    model: string;
    ollama_url?: string;
    zai_endpoint?: string;
  }) =>
    fetchApi<{ valid: boolean }>("/setup/validate/step-4", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getProviderModels: (provider: AIProvider, apiKey = "", ollamaUrl = "http://localhost:11434") => {
    const params = new URLSearchParams({ api_key: apiKey, ollama_url: ollamaUrl });
    return fetchApi<{
      provider: AIProvider;
      models: { id: string; name: string }[];
      provenance?: ModelCatalogProvenance | null;
    }>(`/setup/providers/${provider}/models?${params.toString()}`);
  },

  complete: (state: WizardState) =>
    fetchApi<{ novel_id: string; redirect_to: string; message: string }>("/setup/complete", {
      method: "POST",
      body: JSON.stringify({ state }),
    }),

  /** List available demo projects for the dashboard. */
  listDemos: () => fetchApi<{ demos: DemoProjectInfo[] }>("/setup/demos").then((r) => r.demos),
};
