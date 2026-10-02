import { beforeEach, describe, expect, it } from "vitest";
import { useWizardStore } from "./wizardStore";

describe("useWizardStore", () => {
  const defaultState = {
    project_name: "",
    writing_language: "en",
    autosave_interval: 30,
    title: "",
    author: "",
    genre: "",
    logline: "",
    story_structure: "three_act" as const,
    tone: "dramatic" as const,
    starter: "blank" as const,
    provider: "anthropic" as const,
    api_key: "",
    model: "",
    ollama_url: "http://localhost:11434",
    zai_endpoint: "general",
  };

  beforeEach(() => {
    useWizardStore.setState({ currentStep: 1, state: { ...defaultState } });
  });

  describe("initial state", () => {
    it("should start at step 1", () => {
      expect(useWizardStore.getState().currentStep).toBe(1);
    });

    it("should have default state values", () => {
      const state = useWizardStore.getState().state;
      expect(state.project_name).toBe("");
      expect(state.writing_language).toBe("en");
      expect(state.story_structure).toBe("three_act");
    });
  });

  describe("setStep", () => {
    it("should set the current step", () => {
      useWizardStore.getState().setStep(3);
      expect(useWizardStore.getState().currentStep).toBe(3);
    });

    it("should allow setting any step between 1 and 5", () => {
      useWizardStore.getState().setStep(5);
      expect(useWizardStore.getState().currentStep).toBe(5);

      useWizardStore.getState().setStep(1);
      expect(useWizardStore.getState().currentStep).toBe(1);
    });
  });

  describe("nextStep", () => {
    it("should increment the current step", () => {
      useWizardStore.getState().nextStep();
      expect(useWizardStore.getState().currentStep).toBe(2);
    });

    it("should stop at step 5 (maximum)", () => {
      useWizardStore.setState({ currentStep: 5 });
      useWizardStore.getState().nextStep();
      expect(useWizardStore.getState().currentStep).toBe(5);
    });

    it("should increment from step 1 to 5", () => {
      for (let i = 1; i < 5; i++) {
        useWizardStore.getState().nextStep();
      }
      expect(useWizardStore.getState().currentStep).toBe(5);
    });
  });

  describe("prevStep", () => {
    it("should decrement the current step", () => {
      useWizardStore.setState({ currentStep: 3 });
      useWizardStore.getState().prevStep();
      expect(useWizardStore.getState().currentStep).toBe(2);
    });

    it("should stop at step 1 (minimum)", () => {
      useWizardStore.setState({ currentStep: 1 });
      useWizardStore.getState().prevStep();
      expect(useWizardStore.getState().currentStep).toBe(1);
    });
  });

  describe("updateStep1", () => {
    it("should update step 1 fields", () => {
      useWizardStore.getState().updateStep1({
        project_name: "My Novel",
        writing_language: "de",
        autosave_interval: 60,
      });

      const state = useWizardStore.getState().state;
      expect(state.project_name).toBe("My Novel");
      expect(state.writing_language).toBe("de");
      expect(state.autosave_interval).toBe(60);
    });

    it("should preserve other state fields", () => {
      useWizardStore.setState({
        state: { ...defaultState, title: "Existing Title" },
      });

      useWizardStore.getState().updateStep1({
        project_name: "New Project",
        writing_language: "de",
        autosave_interval: 60,
      });

      const state = useWizardStore.getState().state;
      expect(state.project_name).toBe("New Project");
      expect(state.writing_language).toBe("de");
      expect(state.autosave_interval).toBe(60);
      expect(state.title).toBe("Existing Title");
    });
  });

  describe("updateStep2", () => {
    it("should update step 2 fields", () => {
      useWizardStore.getState().updateStep2({
        title: "The Great Novel",
        author: "John Doe",
        genre: "fantasy",
        logline: "An epic adventure",
        story_structure: "five_act",
        tone: "humorous",
      });

      const state = useWizardStore.getState().state;
      expect(state.title).toBe("The Great Novel");
      expect(state.author).toBe("John Doe");
      expect(state.genre).toBe("fantasy");
      expect(state.logline).toBe("An epic adventure");
      expect(state.story_structure).toBe("five_act");
      expect(state.tone).toBe("humorous");
    });
  });

  describe("updateStep3", () => {
    it("should update step 3 fields", () => {
      useWizardStore.getState().updateStep3({
        starter: "demo_fantasy",
      });

      const state = useWizardStore.getState().state;
      expect(state.starter).toBe("demo_fantasy");
    });
  });

  describe("updateStep4", () => {
    it("should update step 4 fields", () => {
      useWizardStore.getState().updateStep4({
        provider: "openai",
        api_key: "sk-test-key",
        model: "gpt-4",
        ollama_url: "http://localhost:11434",
        zai_endpoint: "general",
      });

      const state = useWizardStore.getState().state;
      expect(state.provider).toBe("openai");
      expect(state.api_key).toBe("sk-test-key");
      expect(state.model).toBe("gpt-4");
      expect(state.zai_endpoint).toBe("general");
    });
  });

  describe("reset", () => {
    it("should reset step to 1", () => {
      useWizardStore.setState({ currentStep: 4 });
      useWizardStore.getState().reset();
      expect(useWizardStore.getState().currentStep).toBe(1);
    });

    it("should reset state to default values", () => {
      useWizardStore.setState({
        state: {
          project_name: "Modified Project",
          writing_language: "de",
          autosave_interval: 60,
          title: "Modified Title",
          author: "Modified Author",
          genre: "sci-fi",
          logline: "A modified story",
          story_structure: "five_act" as const,
          tone: "humorous" as const,
          starter: "demo_scifi" as const,
          provider: "openai" as const,
          api_key: "some-key",
          model: "gpt-4",
          ollama_url: "http://localhost:11434",
        },
      });

      useWizardStore.getState().reset();

      const state = useWizardStore.getState().state;
      expect(state.project_name).toBe("");
      expect(state.writing_language).toBe("en");
      expect(state.title).toBe("");
      expect(state.author).toBe("");
      expect(state.provider).toBe("anthropic");
    });
  });
});

describe("importSelection", () => {
  it("starts null and is settable", () => {
    useWizardStore.getState().reset();
    expect(useWizardStore.getState().importSelection).toBeNull();
    const file = new File(["# A\nb"], "a.md");
    const selection = { files: [file], excludedIndices: [], titleOverrides: {}, includedCount: 1 };
    useWizardStore.getState().setImportSelection(selection);
    expect(useWizardStore.getState().importSelection).toEqual(selection);
  });

  it("reset() clears importSelection", () => {
    useWizardStore.getState().setImportSelection({
      files: [],
      excludedIndices: [],
      titleOverrides: {},
      includedCount: 0,
    });
    useWizardStore.getState().reset();
    expect(useWizardStore.getState().importSelection).toBeNull();
  });
});
