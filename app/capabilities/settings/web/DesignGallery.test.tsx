// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { DesignGallery } from "./DesignGallery";

describe("DesignGallery", () => {
  it("names its four sections", () => {
    render(<DesignGallery />);
    for (const name of ["Tokens", "Type", "Controls", "Surfaces"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
  });

  it("shows the target drafts", () => {
    cleanup();
    render(<DesignGallery />);
    expect(screen.getByRole("heading", { name: "Target" })).toBeTruthy();
    for (const name of [
      /Timeline-Landing/,
      /Szenen-Outline/,
      /Beta-Reader-Landing/,
      /geteilter Tab/,
      /Multi-Draft-Sitzung/,
      /Knowledge-Graph/,
      /Graph-Linse/,
      /Paletten-Zeile/,
      /Regeln \+ Sync/,
      /Rail \+ Dock/,
      /Literarische Suite/,
      /Serien-Verwaltung/,
      /Auswertung \+ Kosten-Reiter/,
    ]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    expect(screen.getAllByText(/ENTWURF/).length).toBe(13);
  });

  it("pins the dock and palette specimens", () => {
    cleanup();
    render(<DesignGallery />);
    expect(screen.getByRole("heading", { name: "Specimens" })).toBeTruthy();
    for (const name of [
      /Gesprächsrunde/,
      /Konsistenzkarte/,
      /Entitätszeile/,
      /Dialogzeile/,
    ]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
    // The turn's chips wear their documents' titles; one stands open on
    // its quoted passage.
    expect(screen.getByRole("button", { name: "Zeitstrahl" })).toBeTruthy();
    // The finding is the dock's own surface: a named region, not a bare card.
    expect(screen.getByRole("region", { name: "Consistency finding" })).toBeTruthy();
    // The wrapped row is the shell's selection list with the wrap the dock
    // owns, named for its heading.
    expect(screen.getByRole("grid", { name: "Entities" })).toBeTruthy();
    // The palette's consistency row opens the dialog whose resting state is
    // this trigger beside its cancel — the modal itself cannot stand inline.
    expect(screen.getByRole("button", { name: "Check the whole book" })).toBeTruthy();
  });

  it("pins the planning dock specimen", () => {
    cleanup();
    render(<DesignGallery />);
    expect(screen.getByRole("heading", { name: /Szenenliste/ })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Ankommen" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "Lücke" })).toBeTruthy();
    expect(screen.getByText("Planned")).toBeTruthy();
    expect(screen.getByText("In progress")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Advance to In progress" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Advance to Complete" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save scenes" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add scene" })).toBeTruthy();
  });

  it("pins the built graph-canvas specimen beside the Target draft", () => {
    cleanup();
    render(<DesignGallery />);
    // The specimen's own heading names the built state — the Target draft
    // above keeps the ENTWURF stamp as the fork record, the specimen never
    // wears it.
    const heading = screen.getByRole("heading", { name: /Graph-Canvas/ });
    expect(heading.textContent).toMatch(/gebaut/);
    const block = heading.parentElement as HTMLElement;
    expect(block.textContent).not.toMatch(/ENTWURF/);
    // The mini canvas: three named nodes, two drawn edges, one selected.
    expect(block.textContent).toMatch(/Maya Chen/);
    expect(block.textContent).toMatch(/Horizon Station/);
    const canvas = block.querySelector("svg");
    expect(canvas).not.toBeNull();
    expect(canvas?.querySelectorAll("line")).toHaveLength(2);
    // The selected node's glance: its type chip and the edge in words.
    expect(block.textContent).toMatch(/Figur/);
  });

  it("pins the built timeline-canvas specimen beside the Target draft", () => {
    cleanup();
    render(<DesignGallery />);
    // The specimen's own heading names the built state — the Target draft
    // above keeps the ENTWURF stamp as the fork record, the specimen never
    // wears it.
    const heading = screen.getByRole("heading", { name: /Timeline-Canvas/ });
    expect(heading.textContent).toMatch(/gebaut/);
    const block = heading.parentElement as HTMLElement;
    expect(block.textContent).not.toMatch(/ENTWURF/);
    // The dated row carries its garnish, characters and chapter; the
    // undated row renders its position instead of a date.
    expect(screen.getByRole("group", { name: "Das Signal" })).toBeTruthy();
    expect(block.textContent).toMatch(/#1/);
    expect(block.textContent).toMatch(/Im Frühling/);
    expect(block.textContent).toMatch(/Maya Chen/);
    expect(screen.getByRole("group", { name: "Der stille Winter" })).toBeTruthy();
    expect(block.textContent).toMatch(/Unordered/);
    // The view switch and the row actions stand inert: pressed marks and
    // plain buttons, no dialogs, no handlers.
    expect(screen.getByRole("button", { name: "Chronological" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(2);
  });

  it("pins the built storyboard-canvas specimen beside the Target draft", () => {
    cleanup();
    render(<DesignGallery />);
    // The specimen's own heading names the built state — the Target draft
    // above keeps the ENTWURF stamp as the fork record, the specimen never
    // wears it.
    const heading = screen.getByRole("heading", { name: /Storyboard-Canvas/ });
    expect(heading.textContent).toMatch(/gebaut/);
    const block = heading.parentElement as HTMLElement;
    // Honest scope: the gallery root holds both the Target drafts and the
    // specimens, so the presence check proves the matcher sees the stamps
    // the freedom check below must not find among the specimens. The
    // freedom scope is the whole Specimens section, not the widest
    // (document) scope and not the specimen's own div, which could never
    // see the drafts and passed vacuously.
    const gallery = heading.closest("div.mx-auto") as HTMLElement;
    expect(gallery.textContent).toMatch(/ENTWURF/);
    const specimens = heading.closest("section") as HTMLElement;
    expect(specimens.textContent).not.toMatch(/ENTWURF/);
    // Stage columns miniaturized: the moved card stands in its new column,
    // with its size and sync badge beside the move it offers.
    expect(screen.getByRole("group", { name: "Ankunft" })).toBeTruthy();
    expect(block.textContent).toMatch(/words/);
    expect(screen.getByRole("button", { name: "Preview structure change" })).toBeTruthy();
    // One remap row: the chapter's before and after in one line.
    expect(block.textContent).toMatch(/→/);
  });

  it("shows the parchment surface ladder and the hairlines", () => {
    cleanup();
    const { container } = render(<DesignGallery />);
    for (const step of [
      "bg-background",
      "bg-panel",
      "bg-card",
      "bg-surface",
      "bg-surface-container-lowest",
      "bg-surface-container-low",
      "bg-surface-container",
      "bg-surface-container-high",
      "bg-surface-container-highest",
      "bg-surface-variant",
      "bg-soft",
    ]) {
      expect(screen.getByText(step)).toBeTruthy();
      expect(container.querySelector(`.${step}`)).not.toBeNull();
    }
    for (const hairline of ["border", "rule", "outline", "outline-variant"]) {
      expect(screen.getByText(hairline)).toBeTruthy();
      expect(container.querySelector(`.bg-${hairline}`)).not.toBeNull();
    }
  });

  it("shows the four cover pairs on their own inks", () => {
    cleanup();
    const { container } = render(<DesignGallery />);
    for (const tone of ["pale", "sepia", "ink", "slate"]) {
      expect(screen.getByText(`cover-${tone}`)).toBeTruthy();
      expect(container.querySelector(`.bg-cover-${tone}`)).not.toBeNull();
      expect(container.querySelector(`.text-cover-${tone}-ink`)).not.toBeNull();
    }
    // The compositions themselves: every cover bends on its spine, and the
    // sepia tile alone wears the gold inset frame.
    const tones = new Set(
      Array.from(container.querySelectorAll("[data-cover-tone]")).map((tile) =>
        tile.getAttribute("data-cover-tone"),
      ),
    );
    expect(Array.from(tones).sort()).toEqual(["ink", "pale", "sepia", "slate"]);
    expect(container.querySelectorAll("[data-cover-spine]").length).toBeGreaterThanOrEqual(4);
    // Only sepia frames: the long-title pin hashes to its own tone, so the
    // invariant is the tone that owns the frame, not a count of specimens.
    const framed = Array.from(container.querySelectorAll("[data-cover-frame]")).map((frame) =>
      frame.closest("[data-cover-tone]")?.getAttribute("data-cover-tone"),
    );
    expect(framed.length).toBeGreaterThanOrEqual(1);
    expect(new Set(framed)).toEqual(new Set(["sepia"]));
  });

  it("shows the radius ladder's three steps", () => {
    cleanup();
    const { container } = render(<DesignGallery />);
    for (const [step, token] of [
      ["4", "--radius-sm"],
      ["8", "--radius-control"],
      ["12", "--radius-surface"],
    ]) {
      const specimen = container.querySelector(`[data-radius="${step}"]`) as HTMLElement;
      expect(specimen).not.toBeNull();
      expect(specimen.className).toContain(`rounded-[var(${token})]`);
      expect(screen.getByText(new RegExp(`${step} px`))).toBeTruthy();
    }
  });

  it("shows the eyebrow as a type step, in its uppercase usage", () => {
    cleanup();
    render(<DesignGallery />);
    expect(screen.getByText("text-eyebrow").className).toContain("uppercase");
    for (const step of [
      "text-eyebrow",
      "text-meta",
      "text-label",
      "text-body",
      "text-emph",
      "text-title",
      "text-hero",
    ]) {
      expect(screen.getByText(step)).toBeTruthy();
    }
  });

  it("shows the button ladder's three sizes and the focus ring", () => {
    cleanup();
    render(<DesignGallery />);
    expect(screen.getByRole("button", { name: "sm" }).className).toContain("h-7");
    expect(screen.getByRole("button", { name: "md" }).className).toContain("h-9");
    expect(screen.getByRole("button", { name: "lg" }).className).toContain("h-10");
    // The ring specimen draws the same 2 px amber ring with its 1 px gap
    // every interactive element wears when the keyboard reaches it.
    const ring = screen.getByRole("button", { name: "Focus ring" });
    expect(ring.className).toContain("ring-2");
    expect(ring.className).toContain("ring-focus");
    expect(ring.className).toContain("ring-offset-1");
  });

  it("shows the severity rules at 2 px", () => {
    cleanup();
    render(<DesignGallery />);
    const warning = screen.getByText("The embedding model changed. Re-embed the documents.");
    expect(warning.className).toContain("border-t-2");
    expect(warning.className).toContain("border-t-warning");
    const danger = screen.getByText("The theme could not be saved.");
    expect(danger.className).toContain("border-t-2");
    expect(danger.className).toContain("border-t-danger");
  });

  it("clamps a 120-character cover title", () => {
    const { container } = render(<DesignGallery />);
    const tile = container.querySelector('[data-cover-tone][data-long-title]');
    expect(tile).not.toBeNull();
    expect(getComputedStyle(tile as Element).overflow).toBe("hidden");
  });

  it("survives a corrupt theme hint", () => {
    localStorage.setItem("narrare.theme", "sepia");
    render(<DesignGallery />);
    expect(document.documentElement.dataset.theme).not.toBe("sepia");
    localStorage.clear();
  });
});
