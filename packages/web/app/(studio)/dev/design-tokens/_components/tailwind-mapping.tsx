"use client";

import { useEffect, useState } from "react";

interface Mapping {
  tailwind: string;
  cssVar: string;
  description: string;
}

const MAPPINGS: Mapping[] = [
  { tailwind: "bg-background", cssVar: "--background", description: "Page background" },
  { tailwind: "text-foreground", cssVar: "--foreground", description: "Default text" },
  { tailwind: "bg-card", cssVar: "--card", description: "Card background" },
  { tailwind: "text-card-foreground", cssVar: "--card-foreground", description: "Card text" },
  { tailwind: "bg-popover", cssVar: "--popover", description: "Popover background" },
  {
    tailwind: "text-popover-foreground",
    cssVar: "--popover-foreground",
    description: "Popover text",
  },
  { tailwind: "bg-primary", cssVar: "--primary", description: "Primary button bg" },
  {
    tailwind: "text-primary-foreground",
    cssVar: "--primary-foreground",
    description: "Primary button text",
  },
  { tailwind: "bg-secondary", cssVar: "--secondary", description: "Secondary button bg" },
  {
    tailwind: "text-secondary-foreground",
    cssVar: "--secondary-foreground",
    description: "Secondary button text",
  },
  { tailwind: "bg-muted", cssVar: "--muted", description: "Muted background" },
  {
    tailwind: "text-muted-foreground",
    cssVar: "--muted-foreground",
    description: "Muted/secondary text",
  },
  { tailwind: "bg-accent", cssVar: "--accent", description: "Accent/hover bg" },
  { tailwind: "text-accent-foreground", cssVar: "--accent-foreground", description: "Accent text" },
  { tailwind: "bg-destructive", cssVar: "--destructive", description: "Destructive bg" },
  {
    tailwind: "text-destructive-foreground",
    cssVar: "--destructive-foreground",
    description: "Destructive text",
  },
  { tailwind: "border-border", cssVar: "--border", description: "Default border" },
  { tailwind: "border-input", cssVar: "--input", description: "Input border" },
  {
    tailwind: "bg-input-background",
    cssVar: "--input-background",
    description: "Input background",
  },
  { tailwind: "ring-ring", cssVar: "--ring", description: "Focus ring" },
  { tailwind: "bg-chart-1", cssVar: "--chart-1", description: "Chart color 1" },
  { tailwind: "bg-chart-2", cssVar: "--chart-2", description: "Chart color 2" },
  { tailwind: "bg-chart-3", cssVar: "--chart-3", description: "Chart color 3" },
  { tailwind: "bg-chart-4", cssVar: "--chart-4", description: "Chart color 4" },
  { tailwind: "bg-chart-5", cssVar: "--chart-5", description: "Chart color 5" },
  { tailwind: "bg-sidebar", cssVar: "--sidebar", description: "Sidebar background" },
  {
    tailwind: "text-sidebar-foreground",
    cssVar: "--sidebar-foreground",
    description: "Sidebar text",
  },
  { tailwind: "bg-sidebar-primary", cssVar: "--sidebar-primary", description: "Sidebar primary" },
  {
    tailwind: "text-sidebar-primary-foreground",
    cssVar: "--sidebar-primary-foreground",
    description: "Sidebar primary text",
  },
  { tailwind: "bg-sidebar-accent", cssVar: "--sidebar-accent", description: "Sidebar accent" },
  {
    tailwind: "text-sidebar-accent-foreground",
    cssVar: "--sidebar-accent-foreground",
    description: "Sidebar accent text",
  },
  { tailwind: "border-sidebar-border", cssVar: "--sidebar-border", description: "Sidebar border" },
  { tailwind: "ring-sidebar-ring", cssVar: "--sidebar-ring", description: "Sidebar ring" },
  { tailwind: "rounded-sm", cssVar: "--radius-sm", description: "Small radius" },
  { tailwind: "rounded-md", cssVar: "--radius-md", description: "Medium radius" },
  { tailwind: "rounded-lg", cssVar: "--radius-lg", description: "Default radius" },
  { tailwind: "rounded-xl", cssVar: "--radius-xl", description: "Large radius" },
];

export function TailwindMapping({ previewDark }: { previewDark: boolean }) {
  const [values, setValues] = useState<Record<string, string>>({});

  useEffect(() => {
    const style = getComputedStyle(document.documentElement);
    const allVars = [...new Set(MAPPINGS.map((m) => m.cssVar))];
    setValues(Object.fromEntries(allVars.map((v) => [v, style.getPropertyValue(v).trim()])));
  }, [previewDark]);

  return (
    <div className="space-y-4">
      <h2 className="text-xl font-medium flex items-center gap-2">
        Tailwind Utility Mapping
        <span className="text-xs text-muted-foreground font-normal">
          — how <code className="bg-accent px-1 rounded text-[11px]">@theme inline</code> maps CSS
          vars to utilities
        </span>
      </h2>
      <p className="text-sm text-muted-foreground -mt-2">
        Every Tailwind utility listed here is backed by a CSS custom property defined in{" "}
        <code className="bg-accent px-1 rounded text-[11px]">tokens.css</code>.
      </p>
      <div className="overflow-x-auto rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-muted/50 border-b border-border">
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider w-[30%]">
                Tailwind Utility
              </th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider w-[25%]">
                CSS Variable
              </th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider w-[20%]">
                Current Value
              </th>
              <th className="text-left px-4 py-2.5 text-xs font-medium text-muted-foreground uppercase tracking-wider w-[25%]">
                Usage
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {MAPPINGS.map((m) => (
              <tr key={m.tailwind} className="hover:bg-accent/30 transition-colors">
                <td className="px-4 py-2.5">
                  <code className="text-xs font-mono text-foreground bg-accent/50 px-1.5 py-0.5 rounded">
                    {m.tailwind}
                  </code>
                </td>
                <td className="px-4 py-2.5">
                  <code className="text-xs font-mono text-muted-foreground">{m.cssVar}</code>
                </td>
                <td className="px-4 py-2.5">
                  <span className="inline-flex items-center gap-2">
                    <span
                      className="shrink-0 w-3.5 h-3.5 rounded border border-border"
                      style={{
                        backgroundColor: m.cssVar.startsWith("--radius")
                          ? "transparent"
                          : `var(${m.cssVar})`,
                      }}
                    />
                    <span className="text-xs font-mono text-muted-foreground">
                      {values[m.cssVar] ?? "—"}
                    </span>
                  </span>
                </td>
                <td className="px-4 py-2.5 text-xs text-muted-foreground">{m.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
