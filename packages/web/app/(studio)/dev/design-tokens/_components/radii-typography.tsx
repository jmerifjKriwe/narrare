"use client";

import { useEffect, useState } from "react";

/* ─── Radius Section ─── */

const RADII = [
  { name: "sm", cssVar: "--radius-sm", tailwind: "rounded-sm" },
  { name: "md", cssVar: "--radius-md", tailwind: "rounded-md" },
  { name: "lg", cssVar: "--radius-lg", tailwind: "rounded-lg" },
  { name: "xl", cssVar: "--radius-xl", tailwind: "rounded-xl" },
];

function RadiusPreview({ dark }: { dark: boolean }) {
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    setValues(
      Object.fromEntries(RADII.map((r) => [r.cssVar, style.getPropertyValue(r.cssVar).trim()])),
    );
  }, [dark]);

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium flex items-center gap-2">
        Border Radii
        <span className="text-xs text-muted-foreground font-normal">
          — <code className="bg-accent px-1 rounded text-[11px]">--radius-*</code> tokens
        </span>
      </h3>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        {RADII.map((r) => (
          <div key={r.name} className="text-center">
            <div className={`h-16 w-full bg-accent border border-border ${r.tailwind}`} />
            <p className="text-xs font-medium text-foreground mt-2">{r.name}</p>
            <p className="text-[11px] text-muted-foreground font-mono">{r.cssVar}</p>
            <p className="text-[11px] text-muted-foreground font-mono">{values[r.cssVar] ?? "—"}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Typography Section ─── */

const HEADINGS = [
  { tag: "h1" as const, label: "h1", tailwind: "text-2xl" },
  { tag: "h2" as const, label: "h2", tailwind: "text-xl" },
  { tag: "h3" as const, label: "h3", tailwind: "text-lg" },
  { tag: "h4" as const, label: "h4", tailwind: "text-base" },
];

function TypographyPreview() {
  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium flex items-center gap-2">
        Type Scale
        <span className="text-xs text-muted-foreground font-normal">
          — heading scale with{" "}
          <code className="bg-accent px-1 rounded text-[11px]">font-weight-medium</code>
        </span>
      </h3>
      <div className="space-y-4 bg-card border border-border rounded-lg p-4">
        {HEADINGS.map(({ tag: Tag, label, tailwind }) => (
          <div key={label} className="flex items-baseline justify-between gap-4">
            <Tag className="font-medium">{label}. The quick brown fox jumps over the lazy dog.</Tag>
            <span className="shrink-0 text-[11px] text-muted-foreground font-mono">{tailwind}</span>
          </div>
        ))}
        <div className="pt-3 border-t border-border">
          <p className="text-xs text-muted-foreground">
            Body copy uses the system font stack at{" "}
            <code className="bg-accent px-1 rounded">var(--font-size)</code> ({/* font-size */}
            <code className="bg-accent px-1 rounded">16px</code> default) with{" "}
            <code className="bg-accent px-1 rounded">font-weight-normal</code>.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ─── Editor Tokens Section ─── */

const EDITOR_TOKENS = [
  { name: "Max Width", cssVar: "--editor-max-width", desc: "Maximum width of editor content area" },
  { name: "Line Height", cssVar: "--editor-line-height", desc: "Line height for editor prose" },
  { name: "Font Size", cssVar: "--editor-font-size", desc: "Base font size in the editor" },
];

function EditorTokenPreview({ dark }: { dark: boolean }) {
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    setValues(
      Object.fromEntries(
        EDITOR_TOKENS.map((t) => [t.cssVar, style.getPropertyValue(t.cssVar).trim()]),
      ),
    );
  }, [dark]);

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium flex items-center gap-2">
        Editor Tokens
        <span className="text-xs text-muted-foreground font-normal">
          — <code className="bg-accent px-1 rounded text-[11px]">--editor-*</code> custom properties
        </span>
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
        {EDITOR_TOKENS.map((t) => (
          <div key={t.cssVar} className="rounded-lg border border-border bg-card p-3 space-y-1">
            <p className="text-xs font-medium text-foreground">{t.name}</p>
            <p className="text-sm font-mono text-foreground">{values[t.cssVar] ?? "—"}</p>
            <p className="text-[11px] text-muted-foreground">{t.desc}</p>
            <p className="text-[11px] text-muted-foreground font-mono">{t.cssVar}</p>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Compound Section ─── */

export function RadiiTypography({ previewDark }: { previewDark: boolean }) {
  return (
    <div className="space-y-8">
      <h2 className="text-xl font-medium">Radii &amp; Typography</h2>
      <RadiusPreview dark={previewDark} />
      <TypographyPreview />
      <EditorTokenPreview dark={previewDark} />
    </div>
  );
}
