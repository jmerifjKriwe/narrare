import { t as translate, type MessageKey } from "@shell/lib/i18n";

/**
 * The stage's name in the writer's language. The server sends `title_key`
 * (the backend contract: `storyboard.stage.<key>`); a key the catalog
 * does not hold falls back to the raw stage key instead of crashing the
 * render — the registry may grow a stage before the catalogs do. Shared by
 * the storyboard and structure canvases, whose columns and bands name the
 * same stages.
 */
export const KNOWN_STAGE_TITLES: ReadonlySet<string> = new Set([
  "storyboard.stage.setup",
  "storyboard.stage.confrontation",
  "storyboard.stage.resolution",
  "storyboard.stage.ordinary-world",
  "storyboard.stage.call-to-adventure",
  "storyboard.stage.refusal",
  "storyboard.stage.mentor",
  "storyboard.stage.threshold",
  "storyboard.stage.tests-allies-enemies",
  "storyboard.stage.approach",
  "storyboard.stage.ordeal",
  "storyboard.stage.reward",
  "storyboard.stage.road-back",
  "storyboard.stage.resurrection",
  "storyboard.stage.return",
]);

export function stageName(t: typeof translate, titleKey: string, key: string): string {
  const candidate = titleKey !== "" ? titleKey : `storyboard.stage.${key}`;
  return KNOWN_STAGE_TITLES.has(candidate) ? t(candidate as MessageKey) : key;
}
