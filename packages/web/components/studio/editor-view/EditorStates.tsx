import { useTranslations } from "next-intl";

export function EditorEmptyState() {
  const t = useTranslations("studio");

  return (
    <div className="flex-1 flex items-center justify-center h-full text-muted-foreground">
      <p>{t("editor.selectChapter")}</p>
    </div>
  );
}

export function EditorLoadingState() {
  return (
    <div className="flex-1 flex items-center justify-center h-full">
      <div className="w-8 h-8 rounded-md bg-primary animate-pulse" />
    </div>
  );
}
