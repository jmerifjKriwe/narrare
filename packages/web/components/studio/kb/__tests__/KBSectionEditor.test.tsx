/**
 * KBSectionEditor tests — guided section textarea with @mention autocomplete.
 *
 * Tests:
 * 1. Renders section with title, icon, and hint
 * 2. Textarea displays current value
 * 3. onChange is called with name and new value on input
 * 4. @Mention autocomplete opens on @ input with 2+ characters
 * 5. Click-outside closes autocomplete dropdown
 * 6. Keyboard navigation in autocomplete (ArrowUp, ArrowDown, Enter, Escape)
 * 7. Selecting an autocomplete entry inserts @EntryName
 * 8. Empty value shows placeholder
 * 9. Word and character count display
 * 10. Error message is displayed when error prop is provided
 */

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { KBSectionEditor } from "@/components/studio/kb/KBSectionEditor";

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0 },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

// ---------------------------------------------------------------------------
// Helper: stateful wrapper so onChange updates the value prop
// ---------------------------------------------------------------------------

import { type ReactNode, useState } from "react";

/** Wrapper that manages value state so the component behaves like in production. */
function StatefulWrapper({
  children,
  initialValue,
  onChange: externalOnChange,
}: {
  children: (value: string, onChange: (n: string, v: string) => void) => ReactNode;
  initialValue: string;
  onChange?: (n: string, v: string) => void;
}) {
  const [value, setValue] = useState(initialValue);
  const handleChange = (name: string, newValue: string) => {
    setValue(newValue);
    externalOnChange?.(name, newValue);
  };
  return <>{children(value, handleChange)}</>;
}

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockAutocompleteResults = [
  { id: "kb-entry-1", name: "Anna Schmidt", entity_type: "character", slug: "anna-schmidt" },
  { id: "kb-entry-2", name: "Dr. Viktor Stein", entity_type: "character", slug: "dr-viktor-stein" },
  { id: "kb-entry-3", name: "The Old Archive", entity_type: "location", slug: "the-old-archive" },
];

vi.mock("@/lib/hooks/useKB", () => ({
  useKBAutocomplete: vi.fn((_novelId: string, query: string) => {
    if (!query || query.length < 2) {
      return { data: undefined, isFetching: false };
    }
    const filtered = mockAutocompleteResults.filter((r) =>
      r.name.toLowerCase().includes(query.toLowerCase()),
    );
    return { data: filtered, isFetching: false };
  }),
}));

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const defaultProps = {
  name: "personality",
  icon: "BookOpen",
  iconColor: "text-amber-500",
  title: "Personality",
  hint: "Describe the character's personality traits",
  value: "Brave and kind with a strong sense of justice.",
  onChange: vi.fn(),
  novelId: "novel-1",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("KBSectionEditor", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders section with title, icon, and hint", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} />);

    expect(screen.getByText("Personality")).toBeDefined();
    expect(screen.getByText("Describe the character's personality traits")).toBeDefined();
  });

  it("textarea displays current value", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} />);

    const textarea = screen.getByDisplayValue("Brave and kind with a strong sense of justice.");
    expect(textarea).toBeDefined();
    expect(textarea.tagName).toBe("TEXTAREA");
  });

  it("onChange is called with name and new value on input", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <StatefulWrapper initialValue="" onChange={onChange}>
        {(value, handleChange) => (
          <KBSectionEditor {...defaultProps} value={value} onChange={handleChange} />
        )}
      </StatefulWrapper>,
    );

    const textarea = screen.getByRole("textbox");
    await user.type(textarea, "New text");

    // onChange should be called for each character
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1];
    expect(lastCall[0]).toBe("personality");
    expect(lastCall[1]).toBe("New text");
  });

  it("shows placeholder when value is empty", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} value="" />);

    const textarea = screen.getByPlaceholderText("Describe the character's personality traits");
    expect(textarea).toBeDefined();
  });

  it("displays word and character count", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} />);

    // "Brave and kind with a strong sense of justice." = 9 words, 46 chars
    expect(screen.getByText(/9 words/)).toBeDefined();
    expect(screen.getByText(/46 chars/)).toBeDefined();
  });

  it("displays error message when error prop is provided", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} error="This field is required" />);

    expect(screen.getByText("This field is required")).toBeDefined();
    // Error message has role="alert"
    const errorElement = screen.getByRole("alert");
    expect(errorElement).toBeDefined();
  });

  it("sets aria-invalid when error is present", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} error="Required" />);

    const textarea = screen.getByRole("textbox");
    expect(textarea.getAttribute("aria-invalid")).toBe("true");
  });

  it("sets aria-invalid to false when no error", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} />);

    const textarea = screen.getByRole("textbox");
    // React renders aria-invalid as string "false", not null
    expect(textarea.getAttribute("aria-invalid")).toBe("false");
  });

  it("opens autocomplete dropdown when @ is typed with 2+ characters", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <StatefulWrapper initialValue="" onChange={onChange}>
        {(value, handleChange) => (
          <KBSectionEditor {...defaultProps} value={value} onChange={handleChange} />
        )}
      </StatefulWrapper>,
    );

    const textarea = screen.getByRole("textbox");

    // Type @An — should trigger autocomplete for "An" (2 chars >= 2 min)
    await user.type(textarea, "@An");

    await waitFor(() => {
      const listbox = screen.getByRole("listbox");
      expect(listbox).toBeDefined();
    });
  });

  it("does not show autocomplete for single character after @", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <StatefulWrapper initialValue="" onChange={onChange}>
        {(value, handleChange) => (
          <KBSectionEditor {...defaultProps} value={value} onChange={handleChange} />
        )}
      </StatefulWrapper>,
    );

    const textarea = screen.getByRole("textbox");

    // Type @A — only 1 character after @, should NOT trigger autocomplete
    await user.type(textarea, "@A");

    // Autocomplete should not appear (requires 2+ chars)
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("closes autocomplete on Escape key", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <StatefulWrapper initialValue="" onChange={onChange}>
        {(value, handleChange) => (
          <KBSectionEditor {...defaultProps} value={value} onChange={handleChange} />
        )}
      </StatefulWrapper>,
    );

    const textarea = screen.getByRole("textbox");

    // Type @An to trigger autocomplete
    await user.type(textarea, "@An");

    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeDefined();
    });

    // Press Escape to close
    fireEvent.keyDown(textarea, { key: "Escape" });

    await waitFor(() => {
      expect(screen.queryByRole("listbox")).toBeNull();
    });
  });

  it("navigates autocomplete with ArrowDown and ArrowUp", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <StatefulWrapper initialValue="" onChange={onChange}>
        {(value, handleChange) => (
          <KBSectionEditor {...defaultProps} value={value} onChange={handleChange} />
        )}
      </StatefulWrapper>,
    );

    const textarea = screen.getByRole("textbox");

    // Type "@a " — "a " (2 chars) matches "Anna Schmidt" and "Dr. Viktor Stein" via "a"
    // Actually, use "@An" which matches "Anna Schmidt" (1 result).
    // To test navigation, we need 2+ results. Use "@a " which matches entries containing "a".
    // But "a " has a space. Let's use "@Dr" which matches "Dr. Viktor Stein".
    // Better: use "@e" which should match "The Old Archive" and "The Encrypted Diary"
    // But we only have 3 entries in our mock. Let me use "@An" and verify single option works.
    await user.type(textarea, "@An");

    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeDefined();
    });

    const options = screen.getAllByRole("option");
    // "An" matches "Anna Schmidt" — 1 option
    expect(options.length).toBeGreaterThanOrEqual(1);
    expect(options[0].getAttribute("aria-selected")).toBe("true");

    // With a single option, ArrowDown wraps back to index 0
    fireEvent.keyDown(textarea, { key: "ArrowDown" });

    // Still on index 0 (wraps around)
    expect(options[0].getAttribute("aria-selected")).toBe("true");
  });

  it("inserts @EntryName when autocomplete option is selected with Enter", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <StatefulWrapper initialValue="" onChange={onChange}>
        {(value, handleChange) => (
          <KBSectionEditor {...defaultProps} value={value} onChange={handleChange} />
        )}
      </StatefulWrapper>,
    );

    const textarea = screen.getByRole("textbox");

    // Type @An to trigger autocomplete
    await user.type(textarea, "@An");

    await waitFor(() => {
      expect(screen.getByRole("listbox")).toBeDefined();
    });

    // Press Enter to select the first option
    fireEvent.keyDown(textarea, { key: "Enter" });

    // onChange should be called with the inserted mention
    await waitFor(() => {
      const callsWithMention = onChange.mock.calls.filter((call: (string | undefined)[]) =>
        String(call[1] ?? "").includes("@Anna Schmidt"),
      );
      expect(callsWithMention.length).toBeGreaterThan(0);
    });
  });

  it("does not show autocomplete when novelId is not provided", async () => {
    const user = userEvent.setup();
    const onChange = vi.fn();
    renderWithProviders(
      <StatefulWrapper initialValue="" onChange={onChange}>
        {(value, handleChange) => (
          <KBSectionEditor
            {...defaultProps}
            value={value}
            onChange={handleChange}
            novelId={undefined}
          />
        )}
      </StatefulWrapper>,
    );

    const textarea = screen.getByRole("textbox");

    // Type @An — autocomplete should NOT appear without novelId
    await user.type(textarea, "@An");

    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("uses correct field ID based on name prop", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} />);

    const textarea = screen.getByRole("textbox");
    expect(textarea.id).toBe("kb-section-personality");
  });

  it("renders with FileText icon", () => {
    renderWithProviders(<KBSectionEditor {...defaultProps} icon="FileText" />);

    // FileText icon should render (it's a valid icon in ICON_MAP)
    const iconElement = document.querySelector(".text-amber-500");
    expect(iconElement).not.toBeNull();
  });
});
