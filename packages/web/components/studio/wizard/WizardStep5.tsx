"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { useWizardStore } from "@/lib/stores/wizardStore";

// --- Summary row sub-component ---

interface SummaryRowProps {
  label: string;
  value: string;
}

function SummaryRow({ label, value }: SummaryRowProps) {
  return (
    <div className="flex justify-between items-baseline py-3 border-b border-border/50 text-[0.9375rem] gap-4 last:border-b-0">
      <span className="text-muted-foreground shrink-0">{label}</span>
      <span className="text-foreground font-medium text-right break-words">{value || "—"}</span>
    </div>
  );
}

// --- Step 5: Confirm & Create ---

interface WizardStep5Props {
  onComplete: () => Promise<void>;
  onBack: () => void;
}

export function WizardStep5({ onComplete, onBack }: WizardStep5Props) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const { state } = useWizardStore();
  const [isCreating, setIsCreating] = useState(false);

  const handleComplete = async () => {
    setIsCreating(true);
    try {
      await onComplete();
    } finally {
      setIsCreating(false);
    }
  };

  const starterLabel: Record<string, string> = {
    blank: t("wizard.step5.blankProject"),
    demo_fantasy: "Demo: Echoes of the Thornwall",
    demo_scifi: "Demo: Dead Signal",
    demo_german: "Demo: Im stillen Wald",
    import: t("wizard.step5.importFrom", { path: state.import_path || "—" }),
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">{t("wizard.step5.title")}</h2>
        <p className="text-muted-foreground text-[0.9375rem]">{t("wizard.step5.description")}</p>
      </div>

      <div className="flex flex-col gap-5">
        {/* Project summary */}
        <div className="bg-background border border-border/50 rounded-xl p-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 mb-3 flex items-center gap-2">
            <span className="w-6 h-[1px] bg-border inline-block" />
            {t("wizard.step5.project")}
          </h3>
          <SummaryRow label={t("wizard.step5.name")} value={state.project_name} />
          <SummaryRow
            label={t("wizard.step5.language")}
            value={state.writing_language.toUpperCase()}
          />
          <SummaryRow
            label={t("wizard.step5.autosave")}
            value={
              state.autosave_interval === 0
                ? t("wizard.step5.autosaveOff")
                : `${state.autosave_interval}s`
            }
          />
        </div>

        {/* Novel summary */}
        <div className="bg-background border border-border/50 rounded-xl p-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 mb-3 flex items-center gap-2">
            <span className="w-6 h-[1px] bg-border inline-block" />
            {t("wizard.step5.novel")}
          </h3>
          <SummaryRow label={t("wizard.step5.novelTitle")} value={state.title} />
          {state.author && <SummaryRow label={t("wizard.step5.author")} value={state.author} />}
          {state.genre && <SummaryRow label={t("wizard.step5.genre")} value={state.genre} />}
          <SummaryRow
            label={t("wizard.step5.structure")}
            value={t(`wizard.storyStructure.${state.story_structure}` as const)}
          />
          <SummaryRow
            label={t("wizard.step5.tone")}
            value={t(`wizard.tone.${state.tone}` as const)}
          />
        </div>

        {/* Starter content summary */}
        <div className="bg-background border border-border/50 rounded-xl p-6">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 mb-3 flex items-center gap-2">
            <span className="w-6 h-[1px] bg-border inline-block" />
            {t("wizard.step5.starter")}
          </h3>
          <SummaryRow
            label={t("wizard.step5.content")}
            value={starterLabel[state.starter] || state.starter}
          />
        </div>

        {/* Provider section — hidden when Step 4 was skipped */}
        {!state.skip_provider && (
          <div className="bg-background border border-border/50 rounded-xl p-6">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground/80 mb-3 flex items-center gap-2">
              <span className="w-6 h-[1px] bg-border inline-block" />
              {t("wizard.step5.provider")}
            </h3>
            <SummaryRow label={t("wizard.step4.provider")} value={state.provider} />
            <SummaryRow label={t("wizard.step5.model")} value={state.model} />
          </div>
        )}
      </div>

      {isCreating && (
        <p className="text-center text-muted-foreground text-[0.9375rem] p-2 animate-pulse">
          {t("wizard.step5.creating")}…
        </p>
      )}

      <div className="flex justify-end gap-3 mt-4">
        <button
          type="button"
          onClick={onBack}
          disabled={isCreating}
          data-testid="wizard-back"
          className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm disabled:opacity-50"
        >
          ← {tCommon("back")}
        </button>
        <button
          type="button"
          onClick={handleComplete}
          disabled={isCreating}
          data-testid="wizard-complete"
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {isCreating ? `${tCommon("finish")}…` : `${tCommon("finish")} ✓`}
        </button>
      </div>
    </div>
  );
}
