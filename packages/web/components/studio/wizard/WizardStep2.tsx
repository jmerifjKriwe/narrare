"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { cn } from "@/lib/utils";
import type { DemoProjectInfo, StarterContent } from "@/types";

const DEMO_OPTIONS: StarterContent[] = ["demo_fantasy", "demo_scifi", "demo_german"];

// --- Starter card sub-component ---

interface StarterCardProps {
  title: string;
  description: string;
  meta?: string;
  selected: boolean;
  onSelect: () => void;
}

function StarterCard({ title, description, meta, selected, onSelect }: StarterCardProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={cn(
        "text-left p-4 border-2 rounded-xl bg-card",
        "cursor-pointer transition-all duration-300 w-full",
        "hover:border-primary/50",
        selected ? "border-primary bg-primary/5 shadow-sm" : "border-border",
      )}
      aria-pressed={selected}
    >
      <div className="font-semibold mb-1 text-foreground">{title}</div>
      <div className="text-sm text-muted-foreground">{description}</div>
      {meta && <div className="text-xs text-muted-foreground/70 mt-2">{meta}</div>}
    </button>
  );
}

// --- Step 2: Starter Content Selection ---

interface WizardStep2Props {
  onNext: () => void;
  onBack: () => void;
}

export function WizardStep2({ onNext, onBack }: WizardStep2Props) {
  const t = useTranslations("studio");
  const tCommon = useTranslations("common");
  const { updateStep3, state } = useWizardStore();

  const [selected, setSelected] = useState<StarterContent>(state.starter);
  const [importPath, setImportPath] = useState(state.import_path || "");
  const [demoInfo, setDemoInfo] = useState<Record<string, DemoProjectInfo>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelectDemo = async (starter: StarterContent) => {
    setSelected(starter);
    setError(null);

    // Prefill wizard store with demo metadata for the next step (Novel Details)
    const prefillFromDemo = (info: DemoProjectInfo) => {
      if (!info.title) return;
      useWizardStore.getState().updateStep2({
        title: info.title,
        author: info.author || "",
        genre: info.genre || "",
        logline: info.logline || "",
        story_structure: useWizardStore.getState().state.story_structure,
        tone: useWizardStore.getState().state.tone,
      });
    };

    if (DEMO_OPTIONS.includes(starter) && !demoInfo[starter]) {
      try {
        const result = await setupApi.validateStep3({ starter });
        if (result.demo_info) {
          setDemoInfo((prev) => ({ ...prev, [starter]: result.demo_info! }));
          prefillFromDemo(result.demo_info);
        }
      } catch {
        // Non-critical — info is display-only
      }
    } else if (DEMO_OPTIONS.includes(starter) && demoInfo[starter]) {
      prefillFromDemo(demoInfo[starter]);
    }
    // "blank" and "import": don't overwrite existing store values
  };

  const handleNext = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      await setupApi.validateStep3({
        starter: selected,
        import_path: selected === "import" ? importPath : null,
      });
      updateStep3({
        starter: selected,
        import_path: selected === "import" ? importPath : null,
      });
      onNext();
    } catch (e: unknown) {
      const msg = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg || t("wizard.step2.validationFailed"));
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatMeta = (info: DemoProjectInfo) =>
    `${info.chapter_count} chapters · ${info.character_count} characters · ${info.word_count.toLocaleString()} words`;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1">{t("wizard.step2.title")}</h2>
        <p className="text-muted-foreground text-[0.9375rem]">{t("wizard.step2.description")}</p>
      </div>

      <div className="flex flex-col gap-3">
        <StarterCard
          title={t("wizard.step2.blank")}
          description={t("wizard.step2.blankDescription")}
          selected={selected === "blank"}
          onSelect={() => handleSelectDemo("blank")}
        />

        {DEMO_OPTIONS.map((id) => {
          const info = demoInfo[id];
          return (
            <StarterCard
              key={id}
              title={info?.title || id.replace("demo_", "Demo ")}
              description={info?.description || ""}
              meta={info ? formatMeta(info) : undefined}
              selected={selected === id}
              onSelect={() => handleSelectDemo(id)}
            />
          );
        })}

        <StarterCard
          title={t("wizard.step2.import")}
          description={t("wizard.step2.importDescription")}
          selected={selected === "import"}
          onSelect={() => handleSelectDemo("import")}
        />
      </div>

      {selected === "import" && (
        <div>
          <label htmlFor="import_path" className="block text-sm font-medium mb-1.5">
            {t("wizard.step2.importPath")}
          </label>
          <input
            id="import_path"
            type="text"
            value={importPath}
            onChange={(e) => setImportPath(e.target.value)}
            placeholder={t("wizard.step2.importPathPlaceholder")}
            className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
          />
        </div>
      )}

      {error && (
        <p className="bg-destructive/10 text-destructive rounded-lg p-3 text-sm">{error}</p>
      )}

      <div className="flex justify-end gap-3 mt-4">
        <button
          type="button"
          onClick={onBack}
          className="px-6 py-2 bg-muted rounded-md hover:bg-accent transition-colors text-sm"
        >
          ← {tCommon("back")}
        </button>
        <button
          type="button"
          onClick={handleNext}
          disabled={isSubmitting}
          className="px-6 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 transition-opacity text-sm disabled:opacity-50"
        >
          {isSubmitting ? `${tCommon("next")}…` : `${tCommon("next")} →`}
        </button>
      </div>
    </div>
  );
}
