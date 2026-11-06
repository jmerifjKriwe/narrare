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
