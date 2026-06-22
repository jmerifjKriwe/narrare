"use client";

/**
 * VariableMetadataPanel — table of prompt variables with governance metadata.
 *
 * Renders the per-variable metadata surfaced by the provider-free preview
 * (PROMPT-003 / CR-AUFG-07-16). Each row shows the variable name, its
 * description, the cascade ``provenance`` label, the ``security``
 * classification, and a required indicator.
 *
 * The data is authoritative — it always comes from
 * :func:`promptsApi.preview` and is never fabricated locally.
 */

import { useTranslations } from "next-intl";
import type { PromptVariableMetadata } from "@/types";

interface VariableMetadataPanelProps {
  readonly variables: readonly PromptVariableMetadata[];
}

/** Per-variable provenance/security table — fed by the provider-free preview. */
export function VariableMetadataPanel({ variables }: VariableMetadataPanelProps) {
  const t = useTranslations("studio");

  if (variables.length === 0) {
    return (
      <p className="text-sm text-muted-foreground" role="status">
        {t("settings.prompts.promptCustomization.noVariables")}
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
          <th className="py-1 pr-3">{t("settings.prompts.promptCustomization.variableName")}</th>
          <th className="py-1 pr-3">
            {t("settings.prompts.promptCustomization.variableDescription")}
          </th>
          <th className="py-1 pr-3">
            {t("settings.prompts.promptCustomization.variableProvenance")}
          </th>
          <th className="py-1 pr-3">
            {t("settings.prompts.promptCustomization.variableSecurity")}
          </th>
        </tr>
      </thead>
      <tbody>
        {variables.map((v) => (
          <tr key={v.name} className="border-t border-border align-top">
            <td className="py-2 pr-3 font-mono">
              {`{{${v.name}}}`}
              {v.required && (
                <span
                  className="ml-1 text-destructive"
                  role="img"
                  aria-label={t("settings.prompts.promptCustomization.requiredIndicator")}
                >
                  *
                </span>
              )}
            </td>
            <td className="py-2 pr-3 text-muted-foreground">{v.description}</td>
            <td className="py-2 pr-3 font-mono">{v.provenance}</td>
            <td className="py-2 pr-3 font-mono">{v.security}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
