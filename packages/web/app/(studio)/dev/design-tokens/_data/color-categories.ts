export interface TokenDef {
  name: string;
  cssVar: string;
  tailwind: string;
}

export interface ColorCategory {
  name: string;
  tokens: TokenDef[];
}

export const CATEGORIES: ColorCategory[] = [
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
