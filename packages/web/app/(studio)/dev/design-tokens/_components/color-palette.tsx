"use client";

import { useEffect, useRef, useState } from "react";
import { CATEGORIES, type TokenDef } from "../_data/color-categories";

function useTokenValues(
  elementRef: React.RefObject<HTMLDivElement | null>,
  dark: boolean,
  theme: string,
): Record<string, string> {
  const [values, setValues] = useState<Record<string, string>>({});

  // biome-ignore lint/correctness/useExhaustiveDependencies: false positive — dark/theme ARE valid deps (props that trigger re-render)
  useEffect(() => {
    const el = elementRef.current;
    if (!el) return;
    const style = getComputedStyle(el);
    const allVars = CATEGORIES.flatMap((c) => c.tokens.map((t) => t.cssVar));
    setValues(Object.fromEntries(allVars.map((v) => [v, style.getPropertyValue(v).trim()])));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [dark, theme]);

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

export function ColorPalette({
  previewDark,
  theme,
  onThemeChange,
}: {
  previewDark: boolean;
  theme: "neutral" | "narrare";
  onThemeChange: (theme: "neutral" | "narrare") => void;
}) {
  const previewRef = useRef<HTMLDivElement>(null);
  const values = useTokenValues(previewRef, previewDark, theme);

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between gap-4">
        <h2 className="text-xl font-medium flex items-center gap-2">
          Color Palette
          <span className="text-xs text-muted-foreground font-normal">
            — all <code className="bg-accent px-1 rounded text-[11px]">--color-*</code> semantic
            tokens
          </span>
        </h2>
        <fieldset
          className="flex rounded-lg border border-border overflow-hidden shrink-0"
          aria-label="Theme selection"
        >
          <button
            type="button"
            onClick={() => onThemeChange("neutral")}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              theme === "neutral"
                ? "bg-primary text-primary-foreground"
                : "bg-card text-muted-foreground hover:bg-accent"
            }`}
            aria-pressed={theme === "neutral"}
          >
            Neutral
          </button>
          <button
            type="button"
            onClick={() => onThemeChange("narrare")}
            className={`px-3 py-1.5 text-xs font-medium transition-colors ${
              theme === "narrare"
                ? "bg-primary text-primary-foreground"
                : "bg-card text-muted-foreground hover:bg-accent"
            }`}
            aria-pressed={theme === "narrare"}
          >
            Narrare
          </button>
        </fieldset>
      </div>
      <p className="text-sm text-muted-foreground -mt-2">
        Values shown reflect the current theme and color mode. Toggle dark mode above to see dark
        values.
      </p>
      <div ref={previewRef} data-theme={theme} className={previewDark ? "dark" : ""}>
        <div className="space-y-6">
          {CATEGORIES.map((cat) => (
            <div key={cat.name}>
              <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2.5">
                {cat.name}
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-2.5">
                {cat.tokens.map((token) => (
                  <ColorSwatch
                    key={token.cssVar}
                    token={token}
                    value={values[token.cssVar] ?? ""}
                  />
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
