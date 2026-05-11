import { create } from "zustand"
import type { WizardState, AIProvider, StarterContent, StoryStructure, StoryTone } from "@/types"

interface WizardStoreState {
  currentStep: number
  state: WizardState

  setStep: (step: number) => void
  nextStep: () => void
  prevStep: () => void
  updateStep1: (data: { project_name: string; language: string; autosave_interval: number }) => void
  updateStep2: (data: {
    title: string
    author: string
    genre: string
    logline: string
    story_structure: StoryStructure
    tone: StoryTone
  }) => void
  updateStep3: (data: { starter: StarterContent; import_path?: string | null }) => void
  updateStep4: (data: { provider: AIProvider; api_key: string; model: string; ollama_url: string }) => void
  reset: () => void
}

const defaultState: WizardState = {
  project_name: "",
  language: "en",
  autosave_interval: 30,
  title: "",
  author: "",
  genre: "",
  logline: "",
  story_structure: "three_act",
  tone: "dramatic",
  starter: "blank",
  import_path: null,
  provider: "anthropic",
  api_key: "",
  model: "",
  ollama_url: "http://localhost:11434",
}

export const useWizardStore = create<WizardStoreState>((set) => ({
  currentStep: 1,
  state: { ...defaultState },

  setStep: (step) => set({ currentStep: step }),
  nextStep: () => set((s) => ({ currentStep: Math.min(s.currentStep + 1, 5) })),
  prevStep: () => set((s) => ({ currentStep: Math.max(s.currentStep - 1, 1) })),

  updateStep1: (data) =>
    set((s) => ({ state: { ...s.state, ...data } })),

  updateStep2: (data) =>
    set((s) => ({ state: { ...s.state, ...data } })),

  updateStep3: (data) =>
    set((s) => ({ state: { ...s.state, ...data } })),

  updateStep4: (data) =>
    set((s) => ({ state: { ...s.state, ...data } })),

  reset: () => set({ currentStep: 1, state: { ...defaultState } }),
}))
