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
  "storyboard.stage.all-is-lost",
  "storyboard.stage.approach",
  "storyboard.stage.b-story",
  "storyboard.stage.bad-guys-close-in",
  "storyboard.stage.break-into-three",
  "storyboard.stage.break-into-two",
  "storyboard.stage.call-to-adventure",
  "storyboard.stage.catalyst",
  "storyboard.stage.climax",
  "storyboard.stage.confrontation",
  "storyboard.stage.dark-night-of-the-soul",
  "storyboard.stage.debate",
  "storyboard.stage.exposition",
  "storyboard.stage.falling-action",
  "storyboard.stage.final-image",
  "storyboard.stage.finale",
  "storyboard.stage.fun-and-games",
  "storyboard.stage.hook",
  "storyboard.stage.mentor",
  "storyboard.stage.midpoint",
  "storyboard.stage.opening-image",
  "storyboard.stage.ordeal",
  "storyboard.stage.ordinary-world",
  "storyboard.stage.pinch-point-1",
  "storyboard.stage.pinch-point-2",
  "storyboard.stage.plot-turn-1",
  "storyboard.stage.plot-turn-2",
  "storyboard.stage.refusal",
  "storyboard.stage.resolution",
  "storyboard.stage.resurrection",
  "storyboard.stage.return",
  "storyboard.stage.reward",
  "storyboard.stage.rising-action",
  "storyboard.stage.road-back",
  "storyboard.stage.set-up",
  "storyboard.stage.setup",
  "storyboard.stage.tests-allies-enemies",
  "storyboard.stage.theme-stated",
  "storyboard.stage.threshold",
]);

export function stageName(t: typeof translate, titleKey: string, key: string): string {
  const candidate = titleKey !== "" ? titleKey : `storyboard.stage.${key}`;
  return KNOWN_STAGE_TITLES.has(candidate) ? t(candidate as MessageKey) : key;
}
