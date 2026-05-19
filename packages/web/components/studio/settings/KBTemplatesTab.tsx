"use client";

import { useQuery } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { ENTITY_TYPES, TYPE_LABEL_KEYS } from "@/components/studio/kb/constants";
import { templatesApi } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import type { KBTemplateUpdateInfo } from "@/types";
import { KBTemplateEditor } from "./KBTemplateEditor";

// --- Helpers ---

function formatTemplateName(type: string, t: (key: string) => string): string {
  const labelKey = TYPE_LABEL_KEYS[type as keyof typeof TYPE_LABEL_KEYS];
  return labelKey ? t(labelKey) : type.charAt(0).toUpperCase() + type.slice(1);
}

// --- Component ---

interface KBTemplatesTabProps {
  novelId: string;
}

export function KBTemplatesTab({ novelId }: KBTemplatesTabProps) {
  const t = useTranslations("studio");
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>("all");

  const { data: templates, isLoading } = useQuery({
    queryKey: ["kb-templates", novelId],
    queryFn: () => templatesApi.list(novelId),
  });

  const { data: updates } = useQuery({
    queryKey: ["kb-templates-updates", novelId],
    queryFn: () => templatesApi.updates(novelId),
  });

  const updateMap = new Map<string, KBTemplateUpdateInfo>(
    (updates ?? []).map((u) => [u.entity_type, u]),
  );

  // Editor view
  if (selectedType) {
    return (
      <KBTemplateEditor
        novelId={novelId}
        entityType={selectedType}
        hasUpdate={updateMap.has(selectedType)}
        onBack={() => setSelectedType(null)}
      />
    );
  }

  const filtered = templates?.filter(
    (tpl) => filterType === "all" || tpl.entity_type === filterType,
  );

  return (
    <div>
      <div className="mb-6">
        <h2 className="text-xl font-medium mb-1">{t("kb.kbTemplates")}</h2>
        <p className="text-sm text-muted-foreground">{t("kb.kbTemplatesDescription")}</p>
      </div>

      <div className="space-y-4">
        {/* Type filter */}
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex gap-2 flex-wrap mb-4">
            <button
              type="button"
              onClick={() => setFilterType("all")}
              className={cn(
                "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                filterType === "all"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-accent",
              )}
            >
              {t("kb.allTypes")}
            </button>
            {ENTITY_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                onClick={() => setFilterType(type)}
                className={cn(
                  "px-3 py-1.5 rounded-md text-sm font-medium transition-colors",
                  filterType === type
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-accent",
                )}
              >
                {t(TYPE_LABEL_KEYS[type])}
              </button>
            ))}
          </div>

          {/* Loading state */}
          {isLoading && (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">{t("kb.loadingTemplates")}</span>
            </div>
          )}

          {/* Empty state */}
          {!isLoading && filtered && filtered.length === 0 && (
            <div className="text-center py-8">
              <p className="text-sm text-muted-foreground">{t("kb.noTemplates")}</p>
            </div>
          )}

          {/* Template list */}
          {filtered && filtered.length > 0 && (
            <div className="space-y-1">
              {filtered.map((tpl) => {
                const hasUpdate = updateMap.has(tpl.entity_type);
                return (
                  <button
                    key={tpl.entity_type}
                    type="button"
                    onClick={() => setSelectedType(tpl.entity_type)}
                    className={cn(
                      "w-full flex items-center justify-between px-4 py-3 rounded-md text-left transition-colors hover:bg-accent/30",
                      tpl.has_override && "border border-primary/20",
                    )}
                  >
                    <div>
                      <span className="text-sm font-medium">
                        {formatTemplateName(tpl.entity_type, t)}
                      </span>
                      <span className="block text-xs text-muted-foreground">
                        {t("kb.templateVersion", {
                          version: tpl.schema_version,
                          lang: tpl.language,
                        })}
                        {tpl.has_override ? ` · ${t("kb.custom")}` : ` · ${t("kb.defaultLabel")}`}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      {hasUpdate && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-semibold bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                          {t("kb.update")}
                        </span>
                      )}
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
