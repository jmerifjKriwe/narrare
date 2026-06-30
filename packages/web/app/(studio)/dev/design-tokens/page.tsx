"use client";

import { Contrast, Palette, Ruler, Table2, Type } from "lucide-react";
import { useEffect, useState } from "react";
import { ColorPalette } from "./_components/color-palette";
import { RadiiTypography } from "./_components/radii-typography";
import { TailwindMapping } from "./_components/tailwind-mapping";
import { ThemeComparison } from "./_components/theme-comparison";

const SECTIONS = [
  { id: "colors", label: "Color Palette", icon: Palette },
  { id: "radii-typo", label: "Radii & Typography", icon: Type },
  { id: "theme-comparison", label: "Theme Comparison", icon: Contrast },
  { id: "mapping", label: "Tailwind Mapping", icon: Table2 },
] as const;

export default function DesignTokensPage() {
  const [previewDark, setPreviewDark] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    const wasDark = root.classList.contains("dark");
    root.classList.toggle("dark", previewDark);
    return () => {
      root.classList.toggle("dark", wasDark);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [previewDark]);

  if (process.env.NODE_ENV !== "development") return null;

  return (
    <div className="mx-auto max-w-6xl px-8 py-10 space-y-16">
      {/* ── Header ── */}
      <header className="space-y-4">
        <div className="flex items-start justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <Ruler className="w-5 h-5 text-muted-foreground" />
              <h1 className="text-2xl font-medium">Design Tokens</h1>
            </div>
            <p className="text-sm text-muted-foreground">
              Reference for all CSS custom properties, theme values, and Tailwind utility mappings.
              This page is only visible in development mode.
            </p>
          </div>
          <button
            type="button"
            onClick={() => setPreviewDark((p) => !p)}
            className="shrink-0 inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-border bg-card text-sm font-medium hover:bg-accent transition-colors"
          >
            {previewDark ? "☀️" : "🌙"}
            {previewDark ? "Light Mode" : "Dark Mode"}
          </button>
        </div>

        {/* Quick-nav */}
        <nav className="flex gap-1 flex-wrap border-b border-border pb-3">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-accent transition-colors"
            >
              <s.icon className="w-3.5 h-3.5" />
              {s.label}
            </a>
          ))}
        </nav>
      </header>

      {/* ── Sections ── */}
      <section id="colors">
        <ColorPalette previewDark={previewDark} />
      </section>

      <section id="radii-typo">
        <RadiiTypography previewDark={previewDark} />
      </section>

      <section id="theme-comparison">
        <ThemeComparison />
      </section>

      <section id="mapping">
        <TailwindMapping previewDark={previewDark} />
      </section>
    </div>
  );
}
