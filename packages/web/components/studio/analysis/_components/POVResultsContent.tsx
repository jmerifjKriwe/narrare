/**
 * POVResultsContent — renders the full results view:
 * summary stats, POV distribution, scene map, and issues list.
 */

import type { POVResult } from "@/lib/api/analysis";
import { POVDistributionBar } from "./POVDistributionBar";
import { POVIssueRow } from "./POVIssueRow";
import { POVSceneRow } from "./POVSceneRow";

interface POVResultsContentProps {
  result: POVResult;
  distributionEntries: [string, number][];
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function POVResultsContent({ result, distributionEntries, t }: POVResultsContentProps) {
  return (
    <>
      {/* Summary stats */}
      <section className="grid grid-cols-3 gap-2">
        <div className="rounded-lg border border-border p-3 bg-background text-center">
          <div className="text-xs text-muted-foreground mb-1">{t("pov.analysisType")}</div>
          <div className="text-sm font-medium capitalize">
            {result.analysis_type.replace(/_/g, " ")}
          </div>
        </div>
        <div className="rounded-lg border border-border p-3 bg-background text-center">
          <div className="text-xs text-muted-foreground mb-1">{t("pov.switchCount")}</div>
          <div className="text-sm font-medium">{result.switch_count}</div>
        </div>
        <div className="rounded-lg border border-border p-3 bg-background text-center">
          <div className="text-xs text-muted-foreground mb-1">{t("pov.issues")}</div>
          <div className="text-sm font-medium">{result.issues.length}</div>
        </div>
      </section>

      {/* POV Distribution */}
      {distributionEntries.length > 0 && (
        <section>
          <h4 className="text-sm font-medium mb-3">{t("pov.distribution")}</h4>
          <div className="space-y-2">
            {distributionEntries.map(([character, percentage]) => (
              <POVDistributionBar
                key={`dist-${character}`}
                character={character}
                percentage={percentage}
              />
            ))}
          </div>
        </section>
      )}

      {/* Scene Map */}
      {result.scenes.length > 0 && (
        <section>
          <h4 className="text-sm font-medium mb-3">{t("pov.scenes")}</h4>
          <div className="space-y-2">
            {result.scenes.map((scene) => (
              <POVSceneRow key={`scene-${scene.scene_index}`} scene={scene} t={t} />
            ))}
          </div>
        </section>
      )}

      {/* Issues */}
      <section>
        <h4 className="text-sm font-medium mb-2">
          {result.issues.length > 0 ? t("pov.issues") : t("pov.noIssues")}
        </h4>
        {result.issues.length > 0 && (
          <div className="space-y-2">
            {result.issues.map((issue) => (
              <POVIssueRow
                key={`issue-${issue.type}-${issue.location}-${issue.text.slice(0, 30)}`}
                issue={issue}
                t={t}
              />
            ))}
          </div>
        )}
      </section>
    </>
  );
}
