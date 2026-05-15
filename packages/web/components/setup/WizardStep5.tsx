"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { useWizardStore } from "@/lib/stores/wizardStore";
import type { StoryStructure, StoryTone } from "@/types";

interface SummaryRowProps {
  label: string;
  value: string;
}

function SummaryRow({ label, value }: SummaryRowProps) {
  return (
    <div className="flex justify-between items-baseline py-2 border-b border-[var(--color-border)] text-[0.9375rem] gap-4 last:border-b-0">
      <span className="text-[var(--color-text-secondary)] shrink-0">{label}</span>
      <span className="text-[var(--color-text-primary)] font-medium text-right break-words">
        {value || "—"}
      </span>
    </div>
  );
}

export function WizardStep5({
  onComplete,
  onBack,
}: {
  onComplete: () => Promise<void>;
  onBack: () => void;
}) {
  const t = useTranslations("wizard.step5");
  const tCommon = useTranslations("common");
  const tStructure = useTranslations("wizard.storyStructure");
  const tTone = useTranslations("wizard.tone");
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
    blank: "Blank project",
    demo_fantasy: "Demo: Echoes of the Thornwall",
    demo_scifi: "Demo: Dead Signal",
    demo_german: "Demo: Im stillen Wald",
    import: `Import from ${state.import_path || "—"}`,
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1" style={{ fontFamily: "var(--font-display)" }}>
          {t("title")}
        </h2>
        <p className="text-[var(--color-text-secondary)] text-[0.9375rem]">{t("description")}</p>
      </div>

      <div className="flex flex-col gap-5">
        <div className="bg-[var(--color-bg-secondary)] rounded-lg p-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2">
            {t("project")}
          </h3>
          <SummaryRow label="Name" value={state.project_name} />
          <SummaryRow label="Language" value={state.language.toUpperCase()} />
          <SummaryRow
            label="Autosave"
            value={state.autosave_interval === 0 ? "Off" : `${state.autosave_interval}s`}
          />
        </div>

        <div className="bg-[var(--color-bg-secondary)] rounded-lg p-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2">
            {t("novel")}
          </h3>
          <SummaryRow label="Title" value={state.title} />
          {state.author && <SummaryRow label="Author" value={state.author} />}
          {state.genre && <SummaryRow label="Genre" value={state.genre} />}
          <SummaryRow
            label="Structure"
            value={tStructure(state.story_structure as StoryStructure)}
          />
          <SummaryRow label="Tone" value={tTone(state.tone as StoryTone)} />
        </div>

        <div className="bg-[var(--color-bg-secondary)] rounded-lg p-5">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2">
            {t("starter")}
          </h3>
          <SummaryRow label="Content" value={starterLabel[state.starter] || state.starter} />
        </div>

        {/* Provider section — hidden when Step 4 was skipped */}
        {!state.skip_provider && (
          <div className="bg-[var(--color-bg-secondary)] rounded-lg p-5">
            <h3 className="text-xs font-semibold uppercase tracking-wider text-[var(--color-text-tertiary)] mb-2">
              {t("provider")}
            </h3>
            <SummaryRow label="Provider" value={state.provider} />
            <SummaryRow label="Model" value={state.model} />
          </div>
        )}
      </div>

      {isCreating && (
        <p className="text-center text-[var(--color-text-secondary)] text-[0.9375rem] p-2">
          {t("creating")}
        </p>
      )}

      <div className="flex justify-end gap-3 mt-4">
        <Button type="button" variant="secondary" onClick={onBack} disabled={isCreating}>
          ← {tCommon("back")}
        </Button>
        <Button onClick={handleComplete} loading={isCreating}>
          {tCommon("finish")} ✓
        </Button>
      </div>
    </div>
  );
}
