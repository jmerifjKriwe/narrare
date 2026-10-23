// The notices file is the compliance artifact for the built app: the bundle
// inlines this code, the minifier strips the license comments, so the file is
// the only place the bundled libraries' terms reach the recipient. These
// tests pin the contract `pnpm build` depends on: deterministic rows, the
// full license text for every listed license, and a loud failure when a
// license joins the closure whose text is not embedded.

import { describe, expect, it } from "vitest";

import { formatNotices } from "./generate-notices.mjs";

type Entry = {
  name: string;
  versions: string[];
  license?: string;
  author?: string;
  homepage?: string;
};

const pkg = (name: string, versions: string[], extra: Partial<Entry> = {}): Entry => ({
  name,
  versions,
  license: "MIT",
  ...extra,
});

describe("formatNotices", () => {
  it("lists each package under its license, groups and rows sorted", () => {
    const notices = formatNotices({
      MIT: [pkg("react", ["19.3.0"]), pkg("@tiptap/core", ["3.31.3"], { author: "ueberdosis" })],
      "BSD-3-Clause": [pkg("intl-messageformat", ["12.1.4"], { homepage: "https://formatjs.io" })],
    });

    // Groups sort by license id, rows inside a group by package name.
    const bsd = notices.indexOf("intl-messageformat");
    const tiptap = notices.indexOf("@tiptap/core");
    const react = notices.indexOf("react");
    expect(bsd).toBeGreaterThan(-1);
    expect(bsd).toBeLessThan(tiptap);
    expect(tiptap).toBeLessThan(react);

    // A row names the package, its version(s) and the metadata attribution.
    expect(notices).toContain("react 19.3.0");
    expect(notices).toContain("@tiptap/core 3.31.3 — ueberdosis");
    expect(notices).toContain("intl-messageformat 12.1.4 (https://formatjs.io)");
  });

  it("embeds the full text of every license it lists", () => {
    const notices = formatNotices({ Unlicense: [pkg("isbot", ["5.2.2"], { license: "Unlicense" })] });

    expect(notices).toContain("This is free and unencumbered software released into the public domain.");
  });

  it("fails on a license whose text is not embedded", () => {
    // A notice without its terms would be worse than a red build: a new
    // license in the closure must be added to LICENSE_TEXTS deliberately.
    expect(() => formatNotices({ "GPL-3.0-only": [pkg("surprise", ["1.0.0"])] })).toThrow(
      /no embedded license text/,
    );
  });
});
