// @vitest-environment jsdom
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DesignGallery } from "./DesignGallery";

describe("DesignGallery", () => {
  it("names its four sections", () => {
    render(<DesignGallery />);
    for (const name of ["Tokens", "Type", "Controls", "Surfaces"]) {
      expect(screen.getByRole("heading", { name })).toBeTruthy();
    }
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
