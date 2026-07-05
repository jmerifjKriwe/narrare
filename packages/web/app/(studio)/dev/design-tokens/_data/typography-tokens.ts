export interface HeadingValue {
  fontSize: string;
  lineHeight: string;
  fontWeight: string;
}

export const RADII = [
  { name: "sm", cssVar: "--radius-sm", tailwind: "rounded-sm" },
  { name: "md", cssVar: "--radius-md", tailwind: "rounded-md" },
  { name: "lg", cssVar: "--radius-lg", tailwind: "rounded-lg" },
  { name: "xl", cssVar: "--radius-xl", tailwind: "rounded-xl" },
];

export const HEADINGS = [
  { tag: "h1" as const, label: "h1", tailwind: "text-2xl" },
  { tag: "h2" as const, label: "h2", tailwind: "text-xl" },
  { tag: "h3" as const, label: "h3", tailwind: "text-lg" },
  { tag: "h4" as const, label: "h4", tailwind: "text-base" },
];

export const EDITOR_TOKENS = [
  { name: "Max Width", cssVar: "--editor-max-width", desc: "Maximum width of editor content area" },
  { name: "Line Height", cssVar: "--editor-line-height", desc: "Line height for editor prose" },
  { name: "Font Size", cssVar: "--editor-font-size", desc: "Base font size in the editor" },
  { name: "Base Font Size", cssVar: "--font-size", desc: "Root font size for the application" },
  {
    name: "Font Weight Medium",
    cssVar: "--font-weight-medium",
    desc: "Medium font weight (headings)",
  },
  { name: "Font Weight Normal", cssVar: "--font-weight-normal", desc: "Normal font weight (body)" },
  { name: "Sidebar Width", cssVar: "--sidebar-width", desc: "Width of the sidebar panel" },
  { name: "Panel Width", cssVar: "--panel-width", desc: "Width of secondary panels" },
  { name: "Base Radius", cssVar: "--radius", desc: "Default border radius" },
];
