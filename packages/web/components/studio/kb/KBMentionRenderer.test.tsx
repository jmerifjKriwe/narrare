import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ReferenceResolution } from "@/lib/api/kb";
import { KBMentionRenderer } from "./KBMentionRenderer";

const NOVEL_ID = "test-novel-id";

const makeResolved = (overrides: Partial<ReferenceResolution> = {}): ReferenceResolution[] => [
  {
    mention: "Anna Müller",
    entry_id: "entry-1",
    entry_name: "Anna Müller",
    entity_type: "character",
    slug: "anna-muller",
    ...overrides,
  },
];

describe("KBMentionRenderer", () => {
  it("renders resolved HTML when provided", () => {
    const html =
      '<a href="/studio/test-novel-id/kb/anna-muller" class="kb-mention">@Anna Müller</a>';
    render(
      <KBMentionRenderer
        html={html}
        body="@Anna Müller"
        novelId={NOVEL_ID}
        resolved={makeResolved()}
      />,
    );

    const link = screen.getByText("@Anna Müller");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/studio/test-novel-id/kb/anna-muller");
  });

  it("falls back to plain text when html is null", () => {
    render(
      <KBMentionRenderer
        html={null}
        body="Hello @Anna Müller"
        novelId={NOVEL_ID}
        resolved={makeResolved()}
      />,
    );

    const link = screen.getByText("@Anna Müller");
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute("href", "/studio/test-novel-id/kb/anna-muller");
  });

  it("renders unresolved mention as muted text", () => {
    render(
      <KBMentionRenderer
        html={null}
        body="Hello @UnknownPerson"
        novelId={NOVEL_ID}
        resolved={[]}
      />,
    );

    const text = screen.getByText("@UnknownPerson");
    expect(text).toBeInTheDocument();
    // Unresolved mentions should not be links
    expect(text.tagName).not.toBe("A");
  });

  it("renders plain text without mentions", () => {
    render(
      <KBMentionRenderer
        html={null}
        body="Just some plain text."
        novelId={NOVEL_ID}
        resolved={[]}
      />,
    );

    expect(screen.getByText("Just some plain text.")).toBeInTheDocument();
  });

  it("renders mixed resolved and unresolved mentions", () => {
    const resolved: ReferenceResolution[] = [
      {
        mention: "Anna",
        entry_id: "entry-1",
        entry_name: "Anna",
        entity_type: "character",
        slug: "anna",
      },
    ];

    render(
      <KBMentionRenderer
        html={null}
        body="@Anna and @Max"
        novelId={NOVEL_ID}
        resolved={resolved}
      />,
    );

    // Anna should be a link
    const annaLink = screen.getByText("@Anna");
    expect(annaLink).toBeInTheDocument();
    expect(annaLink.tagName).toBe("A");

    // Max should be a span (not a link)
    const maxText = screen.getByText("@Max");
    expect(maxText).toBeInTheDocument();
    expect(maxText.tagName).not.toBe("A");
  });

  it("renders empty body without crashing", () => {
    render(<KBMentionRenderer html={null} body="" novelId={NOVEL_ID} resolved={[]} />);

    // Should render empty div without errors
    expect(document.querySelector(".prose")).toBeInTheDocument();
  });
});
