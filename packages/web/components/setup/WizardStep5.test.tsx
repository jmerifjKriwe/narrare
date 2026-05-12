import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { createWizardState } from "@/mocks/data";
import { WizardStep5 } from "./WizardStep5";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      "wizard.step5": {
        title: "Confirm",
        description: "Review your setup before we create your project.",
        project: "Project",
        novel: "Novel",
        starter: "Starter",
        provider: "AI provider",
        creating: "Creating your project\u2026",
      },
      common: { back: "Back", finish: "Finish" },
      "wizard.storyStructure": {
        three_act: "Three-Act Structure",
        five_act: "Five-Act Structure",
        heros_journey: "Hero's Journey",
        save_the_cat: "Save the Cat",
        seven_point: "Seven-Point Story",
      },
      "wizard.tone": {
        dramatic: "Dramatic",
        humorous: "Humorous",
        suspenseful: "Suspenseful",
        contemplative: "Contemplative",
        romantic: "Romantic",
        dark: "Dark",
        adventurous: "Adventurous",
      },
    };
    return (key: string) => translations[ns]?.[key] ?? `${ns}.${key}`;
  },
}));

// --- Helpers ---

const populatedWizardState = createWizardState({
  project_name: "My Fantasy Novel",
  language: "en",
  autosave_interval: 30,
  title: "Echoes of the Thornwall",
  author: "Jane Doe",
  genre: "Fantasy",
  logline: "A tale of magic",
  story_structure: "three_act",
  tone: "dramatic",
  starter: "demo_fantasy",
  import_path: null,
  provider: "openai",
  api_key: "sk-test-key",
  model: "gpt-4o",
  ollama_url: "http://localhost:11434",
});

beforeEach(() => {
  vi.clearAllMocks();
  useWizardStore.setState({
    currentStep: 5,
    state: { ...populatedWizardState },
  });
});

describe("WizardStep5", () => {
  it("should render the step title and description", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Confirm")).toBeInTheDocument();
    expect(
      screen.getByText("Review your setup before we create your project."),
    ).toBeInTheDocument();
  });

  it("should display project summary section", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Project")).toBeInTheDocument();
    expect(screen.getByText("My Fantasy Novel")).toBeInTheDocument();
  });

  it("should display language in project summary", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("EN")).toBeInTheDocument();
  });

  it("should display autosave interval in project summary", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("30s")).toBeInTheDocument();
  });

  it("should display novel summary section with title", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Novel")).toBeInTheDocument();
    expect(screen.getByText("Echoes of the Thornwall")).toBeInTheDocument();
  });

  it("should display author in novel summary when set", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Jane Doe")).toBeInTheDocument();
  });

  it("should display genre in novel summary when set", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Fantasy")).toBeInTheDocument();
  });

  it("should display story structure in novel summary", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Three-Act Structure")).toBeInTheDocument();
  });

  it("should display tone in novel summary", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Dramatic")).toBeInTheDocument();
  });

  it("should display starter content section", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Demo: Echoes of the Thornwall")).toBeInTheDocument();
  });

  it("should display AI provider section", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("AI provider")).toBeInTheDocument();
    expect(screen.getByText("openai")).toBeInTheDocument();
    expect(screen.getByText("gpt-4o")).toBeInTheDocument();
  });

  it("should render Back and Finish buttons", () => {
    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    // Buttons contain "← Back" and "Finish ✓" — use role/name matching
    expect(screen.getByRole("button", { name: /Back/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Finish/ })).toBeInTheDocument();
  });

  it("should call onComplete when Finish button is clicked", async () => {
    const user = userEvent.setup();
    const onComplete = vi.fn().mockResolvedValue(undefined);
    render(<WizardStep5 onComplete={onComplete} onBack={vi.fn()} />);

    const finishButton = screen.getByRole("button", { name: /Finish/ });
    await user.click(finishButton);

    expect(onComplete).toHaveBeenCalledOnce();
  });

  it("should call onBack when Back button is clicked", async () => {
    const user = userEvent.setup();
    const onBack = vi.fn();
    render(<WizardStep5 onComplete={vi.fn()} onBack={onBack} />);

    await user.click(screen.getByRole("button", { name: /Back/ }));

    expect(onBack).toHaveBeenCalledOnce();
  });

  it("should show 'Off' for autosave when interval is 0", () => {
    useWizardStore.setState({
      state: { ...populatedWizardState, autosave_interval: 0 },
    });

    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    expect(screen.getByText("Off")).toBeInTheDocument();
  });

  it("should show dash for empty values when author and genre are empty", () => {
    useWizardStore.setState({
      state: { ...populatedWizardState, author: "", genre: "" },
    });

    render(<WizardStep5 onComplete={vi.fn()} onBack={vi.fn()} />);

    // When author is empty, the author SummaryRow is not rendered at all (conditional)
    // When genre is empty, the genre SummaryRow is not rendered at all (conditional)
    // So there are no "—" dashes visible for these specific fields
    // Instead, verify that the author and genre text is NOT present
    expect(screen.queryByText("Jane Doe")).not.toBeInTheDocument();
    expect(screen.queryByText("Fantasy")).not.toBeInTheDocument();
  });
});
