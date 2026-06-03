"use client";

/**
 * POVIssueRow — expandable issue row with severity icon, type badge,
 * quoted excerpt, explanation, and suggestion.
 */

import { ChevronDown, ChevronUp } from "lucide-react";
import { useState } from "react";
import type { POVIssue } from "@/lib/api/analysis";
import { getIssueTypeBadgeClass, SeverityIcon } from "./pov-helpers";

interface POVIssueRowProps {
  issue: POVIssue;
  t: (key: string, values?: Record<string, string | number | Date>) => string;
}

export function POVIssueRow({ issue, t }: POVIssueRowProps) {
  const [expanded, setExpanded] = useState(false);

  const typeLabel: Record<POVIssue["type"], string> = {
    head_hop: t("pov.headHop"),
    knowledge_leak: t("pov.knowledgeLeak"),
    emotional_leak: t("pov.emotionalLeak"),
    physical_impossibility: t("pov.physicalImpossibility"),
  };

  return (
    <div className="rounded-lg border border-border p-3">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-start gap-2 text-left"
        aria-expanded={expanded}
      >
        <SeverityIcon severity={issue.severity} />
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span
              className={`text-xs font-medium px-2 py-0.5 rounded ${getIssueTypeBadgeClass(issue.type)}`}
            >
              {typeLabel[issue.type]}
            </span>
            <span className="text-xs text-muted-foreground">{issue.location}</span>
          </div>
          <p className="text-xs text-muted-foreground italic truncate">
            {t("pov.quotedExcerpt", { text: issue.text })}
          </p>
        </div>
        <span className="text-muted-foreground flex-shrink-0 mt-0.5">
          {expanded ? (
            <ChevronUp className="w-3.5 h-3.5" />
          ) : (
            <ChevronDown className="w-3.5 h-3.5" />
          )}
        </span>
      </button>
      {expanded && (
        <div className="mt-3 ml-6 space-y-2 text-xs border-t border-border pt-2">
          <div>
            <span className="font-medium">{t("pov.explanation")}</span>
            <p className="text-muted-foreground mt-0.5">{issue.explanation}</p>
          </div>
          <div>
            <span className="font-medium">{t("pov.suggestion")}</span>
            <p className="text-muted-foreground mt-0.5">{issue.suggestion}</p>
          </div>
        </div>
      )}
    </div>
  );
}
