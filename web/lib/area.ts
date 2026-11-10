/** The four areas and the one utility each may wear: an identity mark on
 *  the icon, never a fill, a text colour, a cover or a notice. The hues are
 *  measured ≥ 3:1 against `--panel` in both themes. The map lives here, beside
 *  the tokens — worn only on rail icons and the gallery's rail-icon-sized
 *  swatches — so documentation pixels never pull the rail's module graph. */
export const AREA_ICON = {
  writing: "text-area-writing",
  knowledge: "text-area-knowledge",
  chat: "text-area-chat",
  settings: "text-area-settings",
} as const;
