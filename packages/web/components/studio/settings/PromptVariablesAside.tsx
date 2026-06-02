"use client";

import { useTranslations } from "next-intl";

// --- Types ---

interface PromptVariablesAsideProps {
  readonly variables: readonly string[];
}

// --- Component ---

/** Displays the list of available {{variables}} for a prompt template. */
export function PromptVariablesAside({ variables }: PromptVariablesAsideProps) {
  const t = useTranslations("studio");

  return (
    <aside className="w-48 shrink-0">
      <h4 className="text-xs font-medium uppercase tracking-wider text-muted-foreground mb-3">
        {t("settings.prompts.variables")}
      </h4>
      <ul className="space-y-1.5">
        {variables.map((variable) => (
          <li
            key={variable}
            className="px-3 py-1.5 rounded-md bg-muted text-xs font-mono text-muted-foreground"
          >
            {`{{${variable}}}`}
          </li>
        ))}
      </ul>
    </aside>
  );
}
