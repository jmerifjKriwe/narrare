import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { WizardStep2 } from "./WizardStep2";

// --- Mocks ---

vi.mock("next-intl", () => ({
  useTranslations: (ns: string) => {
    const translations: Record<string, Record<string, string>> = {
      "wizard.step2": {
        title: "Your novel",
        description: "Tell us about the story you're writing.",
        novelTitle: "Title",
        novelTitlePlaceholder: "What is your novel called?",
        author: "Author name",
        authorPlaceholder: "Your name (optional)",
        genre: "Genre",
        genrePlaceholder: "e.g. Fantasy, Thriller, Romance",
        logline: "Logline",
        loglinePlaceholder: "One sentence that captures your story.",
        structure: "Story structure",
        tone: "Tone",
      },
      common: { next: "Next", back: "Back" },
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

vi.mock("@/lib/api/client", () => ({
  setupApi: {
    validateStep2: vi.fn().mockResolvedValue({ valid: true }),
  },
}));

// --- Helpers ---

beforeEach(() => {
  vi.clearAllMocks();
  useWizardStore.getState().reset();
});

describe("WizardStep2", () => {
  it("should render the step title and description", () => {
    const onNext = vi.fn();
    const onBack = vi.fn();
    render(<WizardStep2 onNext={onNext} onBack={onBack} />);

    expect(screen.getByText("Your novel")).toBeInTheDocument();
    expect(screen.getByText("Tell us about the story you're writing.")).toBeInTheDocument();
  });

  it("should render novel title input", () => {
    const onNext = vi.fn();
    const onBack = vi.fn();
    render(<WizardStep2 onNext={onNext} onBack={onBack} />);

    expect(screen.getByLabelText("Title")).toBeInTheDocument();
  });

  it("should render author input", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByLabelText("Author name")).toBeInTheDocument();
  });

  it("should render genre input", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByLabelText("Genre")).toBeInTheDocument();
  });

  it("should render logline input", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByLabelText("Logline")).toBeInTheDocument();
  });

  it("should render story structure select", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByLabelText("Story structure")).toBeInTheDocument();
  });

  it("should render tone select", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByLabelText("Tone")).toBeInTheDocument();
  });

  it("should render Back and Next buttons", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);

    // Buttons contain "← Back" and "Next →" text
    expect(screen.getByRole("button", { name: /Back/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Next/ })).toBeInTheDocument();
  });

  it("should show validation error when title is empty on submit", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    const onBack = vi.fn();

    render(<WizardStep2 onNext={onNext} onBack={onBack} />);

    const titleInput = screen.getByLabelText("Title");
    await user.clear(titleInput);
    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(screen.getByText("Title is required")).toBeInTheDocument();
    });

    expect(onNext).not.toHaveBeenCalled();
  });

  it("should call onBack when Back button is clicked", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    const onBack = vi.fn();

    render(<WizardStep2 onNext={onNext} onBack={onBack} />);

    await user.click(screen.getByRole("button", { name: /Back/ }));

    expect(onBack).toHaveBeenCalledOnce();
  });

  it("should call onNext with valid data after submission", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    const onBack = vi.fn();

    render(<WizardStep2 onNext={onNext} onBack={onBack} />);

    const titleInput = screen.getByLabelText("Title");
    await user.clear(titleInput);
    await user.type(titleInput, "My Awesome Novel");

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(onNext).toHaveBeenCalledOnce();
    });
  });

  it("should update wizard store with form data on valid submission", async () => {
    const user = userEvent.setup();
    const onNext = vi.fn();
    const onBack = vi.fn();

    render(<WizardStep2 onNext={onNext} onBack={onBack} />);

    const titleInput = screen.getByLabelText("Title");
    await user.clear(titleInput);
    await user.type(titleInput, "Test Novel");

    const authorInput = screen.getByLabelText("Author name");
    await user.clear(authorInput);
    await user.type(authorInput, "Jane Doe");

    await user.click(screen.getByRole("button", { name: /Next/ }));

    await waitFor(() => {
      expect(useWizardStore.getState().state.title).toBe("Test Novel");
      expect(useWizardStore.getState().state.author).toBe("Jane Doe");
    });
  });

  it("should render story structure options", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByText("Three-Act Structure")).toBeInTheDocument();
    expect(screen.getByText("Hero's Journey")).toBeInTheDocument();
  });

  it("should render tone options", () => {
    render(<WizardStep2 onNext={vi.fn()} onBack={vi.fn()} />);
    expect(screen.getByText("Dramatic")).toBeInTheDocument();
    expect(screen.getByText("Humorous")).toBeInTheDocument();
  });
});
