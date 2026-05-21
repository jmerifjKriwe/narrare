"use client";

import { Check, ChevronDown, ChevronRight, Circle, Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { cn } from "@/lib/utils";

export type WritingStep =
  | "plan_outline"
  | "write_draft"
  | "review_draft"
  | "revise_draft"
  | "finalize"
  | "generate_summary";

export type StepStatus = "completed" | "current" | "pending";

interface WritingGraphStatusProps {
  steps: Array<{ id: WritingStep; status: StepStatus }>;
  currentStepLabel?: string;
}

const STEP_ORDER: WritingStep[] = [
  "plan_outline",
  "write_draft",
  "review_draft",
  "revise_draft",
  "finalize",
  "generate_summary",
];

export function WritingGraphStatus({ steps, currentStepLabel }: WritingGraphStatusProps) {
  const [expanded, setExpanded] = useState(true);
  const t = useTranslations("studio");

  const statusMap = new Map(steps.map((s) => [s.id, s.status]));
  const currentIdx = steps.findIndex((s) => s.status === "current");
  const hasCurrent = currentIdx >= 0;
  const completedCount = steps.filter((s) => s.status === "completed").length;

  // Derive a label for the collapsed summary
  const currentLabel =
    currentStepLabel || (hasCurrent ? t(`writingGraph.steps.${steps[currentIdx].id}`) : "");

  return (
    <div className="border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900">
      {/* Collapse/expand toggle */}
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full px-4 py-2 text-xs font-medium text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="w-3 h-3" aria-hidden />
        ) : (
          <ChevronRight className="w-3 h-3" aria-hidden />
        )}
        {completedCount === STEP_ORDER.length
          ? t("writingGraph.allComplete")
          : t("writingGraph.progress", {
              current: hasCurrent ? String(currentIdx + 1) : "—",
              total: String(STEP_ORDER.length),
              label: currentLabel,
            })}
      </button>

      {/* Expanded pipeline */}
      {expanded && (
        <ul className="flex items-center gap-0 px-4 pb-3 overflow-x-auto">
          {STEP_ORDER.map((stepId, idx) => {
            const status = statusMap.get(stepId) || "pending";
            const isLast = idx === STEP_ORDER.length - 1;

            return (
              <li key={stepId} className="flex items-center gap-0">
                <div className="flex items-center gap-1.5">
                  {/* Step indicator dot */}
                  <div
                    className={cn(
                      "flex items-center justify-center w-6 h-6 rounded-full text-[10px] font-bold transition-colors",
                      status === "completed" &&
                        "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/40 dark:text-emerald-400",
                      status === "current" &&
                        "bg-blue-100 text-blue-600 dark:bg-blue-900/40 dark:text-blue-400 ring-2 ring-blue-300 dark:ring-blue-700",
                      status === "pending" &&
                        "bg-gray-100 text-gray-400 dark:bg-gray-800 dark:text-gray-500",
                    )}
                    title={t(`writingGraph.steps.${stepId}`)}
                  >
                    {status === "completed" ? (
                      <Check className="w-3.5 h-3.5" aria-hidden />
                    ) : status === "current" ? (
                      <Loader2 className="w-3 h-3 animate-spin" aria-hidden />
                    ) : (
                      <Circle className="w-3 h-3" aria-hidden />
                    )}
                  </div>
                  {/* Step label */}
                  <span
                    className={cn(
                      "text-[11px] font-medium whitespace-nowrap",
                      status === "completed" && "text-emerald-600 dark:text-emerald-400",
                      status === "current" && "text-blue-600 dark:text-blue-400",
                      status === "pending" && "text-gray-400 dark:text-gray-500",
                    )}
                  >
                    {t(`writingGraph.steps.${stepId}`)}
                  </span>
                </div>
                {/* Connector line between steps */}
                {!isLast && (
                  <div
                    className={cn(
                      "w-6 h-px mx-1.5",
                      status === "completed"
                        ? "bg-emerald-300 dark:bg-emerald-700"
                        : "bg-gray-200 dark:bg-gray-700",
                    )}
                    aria-hidden
                  />
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
