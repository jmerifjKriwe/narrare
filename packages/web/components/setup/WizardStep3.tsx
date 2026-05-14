"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { setupApi } from "@/lib/api/client";
import { useWizardStore } from "@/lib/stores/wizardStore";
import { cn } from "@/lib/utils";
import type { DemoProjectInfo, StarterContent } from "@/types";

const DEMO_OPTIONS: StarterContent[] = ["demo_fantasy", "demo_scifi", "demo_german"];

interface StarterCardProps {
  id: StarterContent;
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
        "text-left p-4 border-2 border-[var(--color-border)] rounded-lg bg-[var(--color-surface)]",
        "cursor-pointer transition-[border-color,background] duration-150 w-full",
        "hover:border-[var(--color-accent-muted)]",
        selected && "border-[var(--color-accent)] bg-[var(--color-accent-light)]",
      )}
      aria-pressed={selected}
    >
      <div className="font-semibold mb-1">{title}</div>
      <div className="text-sm text-[var(--color-text-secondary)]">{description}</div>
      {meta && <div className="text-xs text-[var(--color-text-tertiary)] mt-2">{meta}</div>}
    </button>
  );
}

export function WizardStep3({ onNext, onBack }: { onNext: () => void; onBack: () => void }) {
  const t = useTranslations("wizard.step3");
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
      // Demo already loaded — prefill from cache
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
      setError(msg || "Validation failed");
    } finally {
      setIsSubmitting(false);
    }
  };

  const formatMeta = (info: DemoProjectInfo) =>
    `${info.chapter_count} chapters · ${info.character_count} characters · ${info.word_count.toLocaleString()} words`;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h2 className="text-xl font-semibold mb-1" style={{ fontFamily: "var(--font-display)" }}>
          {t("title")}
        </h2>
        <p className="text-[var(--color-text-secondary)] text-[0.9375rem]">{t("description")}</p>
      </div>

      <div className="flex flex-col gap-3">
        <StarterCard
          id="blank"
          title={t("blank")}
          description={t("blankDescription")}
          selected={selected === "blank"}
          onSelect={() => handleSelectDemo("blank")}
        />

        {DEMO_OPTIONS.map((id) => {
          const info = demoInfo[id];
          return (
            <StarterCard
              key={id}
              id={id}
              title={info?.title || id.replace("demo_", "Demo ")}
              description={info?.description || ""}
              meta={info ? formatMeta(info) : undefined}
              selected={selected === id}
              onSelect={() => handleSelectDemo(id)}
            />
          );
        })}

        <StarterCard
          id="import"
          title={t("import")}
          description={t("importDescription")}
          selected={selected === "import"}
          onSelect={() => handleSelectDemo("import")}
        />
      </div>

      {selected === "import" && (
        <Input
          label={t("importPath")}
          value={importPath}
          onChange={(e) => setImportPath(e.target.value)}
          placeholder="/path/to/your/manuscript"
          autoFocus
        />
      )}

      {error && (
        <p className="bg-[var(--color-error-light)] text-[var(--color-error)] rounded-lg p-3 text-sm">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-3 mt-4">
        <Button type="button" variant="secondary" onClick={onBack}>
          ← {tCommon("back")}
        </Button>
        <Button onClick={handleNext} loading={isSubmitting}>
          {tCommon("next")} →
        </Button>
      </div>
    </div>
  );
}
