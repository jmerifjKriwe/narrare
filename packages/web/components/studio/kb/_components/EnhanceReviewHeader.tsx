import { ArrowLeft, Wand2 } from "lucide-react";

interface EnhanceReviewHeaderProps {
  state: "idle" | "loading" | "review" | "error";
  selectedCount: number;
  totalCount: number;
  onBack: () => void;
  t: (key: string, params?: Record<string, string | number | Date>) => string;
}

export function EnhanceReviewHeader({
  state,
  selectedCount,
  totalCount,
  onBack,
  t,
}: EnhanceReviewHeaderProps) {
  return (
    <div className="flex items-center justify-between p-4 border-b border-border bg-card">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onBack}
          className="p-1.5 text-muted-foreground hover:text-foreground rounded-md hover:bg-muted transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
        </button>
        <div className="flex items-center gap-2">
          <Wand2 className="w-5 h-5 text-purple-500" />
          <h3 className="font-medium">{t("kb.enhanceReview") || "Enhance Review"}</h3>
        </div>
      </div>
      {state === "review" && (
        <div className="text-sm text-muted-foreground">
          {t("kb.enhanceSelected", { count: selectedCount, total: totalCount }) ||
            `${selectedCount} of ${totalCount} selected`}
        </div>
      )}
    </div>
  );
}
