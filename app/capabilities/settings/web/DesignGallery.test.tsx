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
