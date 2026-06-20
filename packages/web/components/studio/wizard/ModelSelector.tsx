"use client";

import { useTranslations } from "next-intl";

interface ModelSelectorProps {
  model: string;
  models: { value: string; label: string }[];
  modelsLoading: boolean;
  setModel: (model: string) => void;
}

/**
 * Three-state model picker for wizard step 4:
 * - loading: shows a transient "loading models" hint
 * - models available: a `<select>` populated from the catalog
 * - no models / fetch failed: a free-text `<input>` fallback
 */
export function ModelSelector({ model, models, modelsLoading, setModel }: ModelSelectorProps) {
  const t = useTranslations("studio");

  if (modelsLoading) {
    return <p className="text-sm text-muted-foreground p-2">{t("wizard.step4.modelLoading")}</p>;
  }

  if (models.length > 0) {
    return (
      <div>
        <label htmlFor="model" className="block text-sm font-medium mb-1.5">
          {t("wizard.step4.model")}
        </label>
        <select
          id="model"
          value={model}
          onChange={(e) => setModel(e.target.value)}
          className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
        >
          <option value="">{t("wizard.step4.modelPlaceholder")}</option>
          {models.map((m) => (
            <option key={m.value} value={m.value}>
              {m.label}
            </option>
          ))}
        </select>
      </div>
    );
  }

  return (
    <div>
      <label htmlFor="model_input" className="block text-sm font-medium mb-1.5">
        {t("wizard.step4.model")}
      </label>
      <input
        id="model_input"
        type="text"
        value={model}
        onChange={(e) => setModel(e.target.value)}
        placeholder={t("wizard.step4.modelPlaceholder")}
        className="w-full px-4 py-2 bg-background border border-border rounded-md text-sm"
      />
    </div>
  );
}
