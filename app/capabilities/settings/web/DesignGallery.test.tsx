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
