"use client";

import type { useTranslations } from "next-intl";

type StudioTranslator = ReturnType<typeof useTranslations>;

interface KnowledgeGraphOverlaysProps {
  isLoading: boolean;
  isEmpty: boolean;
  t: StudioTranslator;
}

export function KnowledgeGraphOverlays({ isLoading, isEmpty, t }: KnowledgeGraphOverlaysProps) {
  if (isLoading) {
    return (
      <div className="absolute inset-0 flex items-center justify-center bg-background/80 z-20">
        <div className="flex flex-col items-center gap-2">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
          <p className="text-sm text-muted-foreground">{t("graph.loading")}</p>
        </div>
      </div>
    );
  }

  if (!isEmpty) return null;
  return (
    <div className="absolute inset-0 flex items-center justify-center z-20">
      <p className="text-muted-foreground">{t("graph.noEntities")}</p>
    </div>
  );
}
