"use client";

import { useEffect, useRef, useState } from "react";

const COMPARE_TOKENS = [
  { name: "Background", cssVar: "--background" },
  { name: "Foreground", cssVar: "--foreground" },
  { name: "Card", cssVar: "--card" },
  { name: "Card Foreground", cssVar: "--card-foreground" },
  { name: "Primary", cssVar: "--primary" },
  { name: "Primary Foreground", cssVar: "--primary-foreground" },
  { name: "Secondary", cssVar: "--secondary" },
  { name: "Muted", cssVar: "--muted" },
  { name: "Muted Foreground", cssVar: "--muted-foreground" },
  { name: "Accent", cssVar: "--accent" },
  { name: "Border", cssVar: "--border" },
  { name: "Destructive", cssVar: "--destructive" },
  { name: "Ring", cssVar: "--ring" },
  { name: "Radius", cssVar: "--radius" },
  { name: "Editor Max Width", cssVar: "--editor-max-width" },
  { name: "Editor Font Size", cssVar: "--editor-font-size" },
];

function ThemePanel({
  label,
  theme,
  values,
}: {
  label: string;
  theme: "neutral" | "narrare";
  values: Record<string, string>;
}) {
  return (
    <div className="rounded-lg border border-border overflow-hidden" data-theme={theme}>
      {/* Mini themed preview header */}
      <div className="bg-background px-4 py-2.5 border-b border-border">
        <p className="text-sm font-medium text-foreground">
          {theme === "neutral" ? "Neutral" : "Narrare"}
        </p>
        <p className="text-[11px] text-muted-foreground font-mono">{`data-theme="${theme}"`}</p>
      </div>
      {/* Token rows */}
      <div className="bg-card p-3 space-y-1">
        {COMPARE_TOKENS.map((t) => (
          <div
            key={t.cssVar}
            className="flex items-center justify-between gap-2 py-1.5 px-2 rounded hover:bg-accent/50 transition-colors"
          >
            <div className="flex items-center gap-2 min-w-0">
              {/* Mini swatch */}
              <span
                className="shrink-0 w-4 h-4 rounded border border-border"
                style={{ backgroundColor: `var(${t.cssVar})` }}
              />
              <span className="text-xs text-foreground truncate">{t.name}</span>
            </div>
            <span className="shrink-0 text-[11px] text-muted-foreground font-mono">
              {values[t.cssVar] ?? "—"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

function ThemePanelWrapper({ label, theme }: { label: string; theme: "neutral" | "narrare" }) {
  const ref = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!ref.current) return;
    const style = getComputedStyle(ref.current);
    setValues(
      Object.fromEntries(
        COMPARE_TOKENS.map((t) => [t.cssVar, style.getPropertyValue(t.cssVar).trim()]),
      ),
    );
  }, []);

  return (
    <div ref={ref} data-theme={theme}>
      <ThemePanel label={label} theme={theme} values={values} />
    </div>
  );
}

export function ThemeComparison() {
  return (
    <div className="space-y-4">
      <h2 className="text-xl font-medium flex items-center gap-2">
        Theme Comparison
        <span className="text-xs text-muted-foreground font-normal">
          — Neutral vs Narrare side-by-side (light mode)
        </span>
      </h2>
      <p className="text-sm text-muted-foreground -mt-2">
        Each panel is rendered within its own{" "}
        <code className="bg-accent px-1 rounded text-[11px]">data-theme</code> context. Values are
        read from the computed style of elements inside each panel.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <ThemePanelWrapper label="Neutral (Default)" theme="neutral" />
        <ThemePanelWrapper label="Narrare (Premium)" theme="narrare" />
      </div>
    </div>
  );
}
