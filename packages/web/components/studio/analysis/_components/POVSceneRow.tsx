/**
 * POVSceneRow — single scene row with POV character + confidence badge.
 */

import type { POVScene } from "@/lib/api/analysis";
import { getConfidenceColorClass } from "./pov-helpers";

interface POVSceneRowProps {
  scene: POVScene;
  t: (key: string) => string;
}

export function POVSceneRow({ scene, t }: POVSceneRowProps) {
  const confidencePercent = Math.round(scene.confidence * 100);

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border p-3 bg-background">
      <span className="text-xs text-muted-foreground flex-shrink-0">
        {t("pov.scene")} {scene.scene_index + 1}
      </span>
      <span className="text-sm font-medium truncate flex-1 min-w-0">
        {scene.pov_character ?? "—"}
      </span>
      <span
        className={`text-xs font-medium px-2 py-0.5 rounded flex-shrink-0 ${getConfidenceColorClass(scene.confidence)}`}
        title={`${t("pov.confidence")}: ${confidencePercent}%`}
      >
        {confidencePercent}%
      </span>
    </div>
  );
}
