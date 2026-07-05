"use client";

import { useEffect, useRef, useState } from "react";
import { EDITOR_TOKENS, HEADINGS, type HeadingValue, RADII } from "../_data/typography-tokens";

function RadiusPreview({ dark }: { dark: boolean }) {
  const [values, setValues] = useState<Record<string, string>>({});

  // biome-ignore lint/correctness/useExhaustiveDependencies: dark is a valid dep (prop change triggers re-render)
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

function TypographyPreview({ dark }: { dark: boolean }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [values, setValues] = useState<Record<string, HeadingValue>>({});

  // biome-ignore lint/correctness/useExhaustiveDependencies: dark is a valid dep (prop change triggers re-render)
  useEffect(() => {
    if (!containerRef.current) return;
    const els = containerRef.current.querySelectorAll("h1, h2, h3, h4");
    const newValues: Record<string, HeadingValue> = {};
    els.forEach((el) => {
      const tag = el.tagName.toLowerCase();
      const style = getComputedStyle(el);
      newValues[tag] = {
        fontSize: style.fontSize,
        lineHeight: style.lineHeight,
        fontWeight: style.fontWeight,
      };
    });
    setValues(newValues);
  }, [dark]);

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-medium flex items-center gap-2">
        Type Scale
        <span className="text-xs text-muted-foreground font-normal">
          — heading scale with{" "}
          <code className="bg-accent px-1 rounded text-[11px]">font-weight-medium</code>
        </span>
      </h3>
      <div ref={containerRef} className="space-y-4 bg-card border border-border rounded-lg p-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-xs text-muted-foreground border-b border-border">
              <th className="text-left font-medium pb-2 pr-4">Tag</th>
              <th className="text-left font-medium pb-2 pr-4">Sample</th>
              <th className="text-left font-medium pb-2 pr-4">Font Size</th>
              <th className="text-left font-medium pb-2 pr-4">Line Height</th>
              <th className="text-left font-medium pb-2">Weight</th>
            </tr>
          </thead>
          <tbody>
            {HEADINGS.map(({ tag: Tag, label }) => (
              <tr key={label}>
                <td className="font-mono text-xs text-muted-foreground py-2 pr-4 align-baseline">
                  {label}
                </td>
                <td className="py-2 pr-4 align-baseline">
                  <Tag className="font-medium">
                    {label}. The quick brown fox jumps over the lazy dog.
                  </Tag>
                </td>
                <td className="font-mono text-xs text-muted-foreground py-2 pr-4 align-baseline whitespace-nowrap">
                  {values[label]?.fontSize ?? "—"}
                </td>
                <td className="font-mono text-xs text-muted-foreground py-2 pr-4 align-baseline whitespace-nowrap">
                  {values[label]?.lineHeight ?? "—"}
                </td>
                <td className="font-mono text-xs text-muted-foreground py-2 align-baseline whitespace-nowrap">
                  {values[label]?.fontWeight ?? "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
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

function EditorTokenPreview({ dark }: { dark: boolean }) {
  const [values, setValues] = useState<Record<string, string>>({});

  // biome-ignore lint/correctness/useExhaustiveDependencies: dark is a valid dep (prop change triggers re-render)
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
      <TypographyPreview dark={previewDark} />
      <EditorTokenPreview dark={previewDark} />
    </div>
  );
}
