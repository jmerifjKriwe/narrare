"use client";

import { useEffect, useState } from "react";

interface TokenDef {
  name: string;
  cssVar: string;
  tailwind: string;
}

interface ColorCategory {
  name: string;
  tokens: TokenDef[];
}

const CATEGORIES: ColorCategory[] = [
  {
    name: "Surface",
    tokens: [
      { name: "Background", cssVar: "--background", tailwind: "bg-background" },
      { name: "Foreground", cssVar: "--foreground", tailwind: "text-foreground" },
      { name: "Card", cssVar: "--card", tailwind: "bg-card" },
      { name: "Card Foreground", cssVar: "--card-foreground", tailwind: "text-card-foreground" },
      { name: "Popover", cssVar: "--popover", tailwind: "bg-popover" },
      {
        name: "Popover Foreground",
        cssVar: "--popover-foreground",
        tailwind: "text-popover-foreground",
      },
    ],
  },
  {
    name: "Brand",
    tokens: [
      { name: "Primary", cssVar: "--primary", tailwind: "bg-primary" },
      {
        name: "Primary Foreground",
        cssVar: "--primary-foreground",
        tailwind: "text-primary-foreground",
      },
      { name: "Secondary", cssVar: "--secondary", tailwind: "bg-secondary" },
      {
        name: "Secondary Foreground",
        cssVar: "--secondary-foreground",
        tailwind: "text-secondary-foreground",
      },
      { name: "Accent", cssVar: "--accent", tailwind: "bg-accent" },
      {
        name: "Accent Foreground",
        cssVar: "--accent-foreground",
        tailwind: "text-accent-foreground",
      },
    ],
  },
  {
    name: "States & Feedback",
    tokens: [
      { name: "Muted", cssVar: "--muted", tailwind: "bg-muted" },
      { name: "Muted Foreground", cssVar: "--muted-foreground", tailwind: "text-muted-foreground" },
      { name: "Destructive", cssVar: "--destructive", tailwind: "bg-destructive" },
      {
        name: "Destructive Foreground",
        cssVar: "--destructive-foreground",
        tailwind: "text-destructive-foreground",
      },
    ],
  },
  {
    name: "Borders & Inputs",
    tokens: [
      { name: "Border", cssVar: "--border", tailwind: "border-border" },
      { name: "Input", cssVar: "--input", tailwind: "border-input" },
      { name: "Input Background", cssVar: "--input-background", tailwind: "bg-input-background" },
      {
        name: "Switch Background",
        cssVar: "--switch-background",
        tailwind: "bg-switch-background",
      },
      { name: "Ring", cssVar: "--ring", tailwind: "ring-ring" },
    ],
  },
  {
    name: "Charts",
    tokens: [
      { name: "Chart 1", cssVar: "--chart-1", tailwind: "bg-chart-1" },
      { name: "Chart 2", cssVar: "--chart-2", tailwind: "bg-chart-2" },
      { name: "Chart 3", cssVar: "--chart-3", tailwind: "bg-chart-3" },
      { name: "Chart 4", cssVar: "--chart-4", tailwind: "bg-chart-4" },
      { name: "Chart 5", cssVar: "--chart-5", tailwind: "bg-chart-5" },
    ],
  },
  {
    name: "Sidebar",
    tokens: [
      { name: "Sidebar", cssVar: "--sidebar", tailwind: "bg-sidebar" },
      {
        name: "Sidebar Foreground",
        cssVar: "--sidebar-foreground",
        tailwind: "text-sidebar-foreground",
      },
      { name: "Sidebar Primary", cssVar: "--sidebar-primary", tailwind: "bg-sidebar-primary" },
      {
        name: "Sidebar Primary Foreground",
        cssVar: "--sidebar-primary-foreground",
        tailwind: "text-sidebar-primary-foreground",
      },
      { name: "Sidebar Accent", cssVar: "--sidebar-accent", tailwind: "bg-sidebar-accent" },
      {
        name: "Sidebar Accent Foreground",
        cssVar: "--sidebar-accent-foreground",
        tailwind: "text-sidebar-accent-foreground",
      },
      { name: "Sidebar Border", cssVar: "--sidebar-border", tailwind: "border-sidebar-border" },
      { name: "Sidebar Ring", cssVar: "--sidebar-ring", tailwind: "ring-sidebar-ring" },
    ],
  },
];

function useTokenValues(dark: boolean): Record<string, string> {
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    const allVars = CATEGORIES.flatMap((c) => c.tokens.map((t) => t.cssVar));
    setValues(Object.fromEntries(allVars.map((v) => [v, style.getPropertyValue(v).trim()])));
  }, [dark]);

  return values;
}

function ColorSwatch({ token, value }: { token: TokenDef; value: string }) {
  const isText = token.name.includes("Foreground");

  return (
    <div className="rounded-lg border border-border overflow-hidden bg-card">
      {isText ? (
        <div className="h-12 w-full flex items-center justify-center bg-background">
          <span className="text-base font-medium" style={{ color: `var(${token.cssVar})` }}>
            Aa
          </span>
        </div>
      ) : (
        <div className="h-12 w-full" style={{ backgroundColor: `var(${token.cssVar})` }} />
      )}
      <div className="p-2.5 space-y-0.5">
        <p className="text-xs font-medium text-foreground">{token.name}</p>
        <p className="text-[11px] text-muted-foreground font-mono">{token.tailwind}</p>
        <p className="text-[11px] text-muted-foreground font-mono truncate" title={value}>
          {value || "—"}
        </p>
      </div>
    </div>
  );
}

export function ColorPalette({ previewDark }: { previewDark: boolean }) {
  const values = useTokenValues(previewDark);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-medium flex items-center gap-2">
        Color Palette
        <span className="text-xs text-muted-foreground font-normal">
          — all <code className="bg-accent px-1 rounded text-[11px]">--color-*</code> semantic
          tokens
        </span>
      </h2>
      <p className="text-sm text-muted-foreground -mt-2">
        Values shown reflect the current theme and color mode. Toggle dark mode above to see dark
        values.
      </p>
      <div className="space-y-6">
        {CATEGORIES.map((cat) => (
          <div key={cat.name}>
            <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2.5">
              {cat.name}
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2.5">
              {cat.tokens.map((token) => (
                <ColorSwatch key={token.cssVar} token={token} value={values[token.cssVar] ?? ""} />
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
