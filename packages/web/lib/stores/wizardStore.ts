import { create } from "zustand";
import type {
  AIProvider,
  ImportSelection,
  StarterContent,
  StoryStructure,
  StoryTone,
  WizardState,
} from "@/types";

interface WizardStoreState {
  currentStep: number;
  state: WizardState;
  /** Live pick state of the Step-2 inline import panel (ADR-091); null until files are picked. */
  importSelection: ImportSelection | null;

  setStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;
  setImportSelection: (selection: ImportSelection | null) => void;
  updateStep1: (data: {
    project_name: string;
    writing_language: string;
    autosave_interval: number;
  }) => void;
  updateStep2: (data: {
    title: string;
    author: string;
    genre: string;
    logline: string;
    story_structure: StoryStructure;
    tone: StoryTone;
    writing_language?: string;
  }) => void;
  updateStep3: (data: { starter: StarterContent }) => void;
  updateStep4: (data: {
    provider: AIProvider;
    api_key: string;
    model: string;
    ollama_url: string;
    zai_endpoint?: string;
  }) => void;
  reset: () => void;
}

const defaultState: WizardState = {
  project_name: "",
  writing_language: "en",
  autosave_interval: 30,
  title: "",
  author: "",
  genre: "",
  logline: "",
  story_structure: "three_act",
  tone: "dramatic",
  starter: "blank",
  provider: "anthropic",
  api_key: "",
  model: "",
  ollama_url: "http://localhost:11434",
  zai_endpoint: "general",
};

export const useWizardStore = create<WizardStoreState>((set) => ({
  currentStep: 1,
  state: { ...defaultState },
  importSelection: null,

  setStep: (step) => set({ currentStep: step }),
  nextStep: () => set((s) => ({ currentStep: Math.min(s.currentStep + 1, 5) })),
  prevStep: () => set((s) => ({ currentStep: Math.max(s.currentStep - 1, 1) })),

  setImportSelection: (selection) => set({ importSelection: selection }),

  updateStep1: (data) => set((s) => ({ state: { ...s.state, ...data } })),

  updateStep2: (data) => set((s) => ({ state: { ...s.state, ...data } })),

  updateStep3: (data) => set((s) => ({ state: { ...s.state, ...data } })),

  updateStep4: (data) => set((s) => ({ state: { ...s.state, ...data } })),

  reset: () => set({ currentStep: 1, state: { ...defaultState }, importSelection: null }),
}));
